/**
 * Feedback Loop — Prediction vs Reality Evaluation
 *
 * THE critical missing piece that transforms Eve from a reporter into an evaluator.
 *
 * Data flow:
 *   1. Predictions stored in Supabase `nba_predictions` (from live-odds.json)
 *   2. After games complete (~10:00 UTC next day), evaluateDay() fetches ESPN scores
 *   3. Joins predictions to outcomes, computes: daily Brier, accuracy, ROI
 *   4. Stores in Supabase `nba_daily_eval` table
 *   5. Posts eval report to A2A + Telegram
 *
 * ESPN API (free, no auth):
 *   GET https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD
 */

const logger = require('./logger');

// ESPN uses full team names. Our predictions may use abbreviations or full names.
// This map covers edge cases where names don't match exactly.
const TEAM_ALIASES = {
  // ESPN name → normalized
  'LA Clippers': 'Los Angeles Clippers',
  'LA Lakers': 'Los Angeles Lakers',
  // Common abbreviation → full name
  'PHX': 'Phoenix Suns',
  'PHI': 'Philadelphia 76ers',
  'NYK': 'New York Knicks',
  'GSW': 'Golden State Warriors',
  'SAS': 'San Antonio Spurs',
  'NOP': 'New Orleans Pelicans',
  'OKC': 'Oklahoma City Thunder',
  'MIN': 'Minnesota Timberwolves',
  'POR': 'Portland Trail Blazers',
};

function normalizeTeam(name) {
  if (!name) return '';
  return TEAM_ALIASES[name] || name.trim();
}

class FeedbackLoop {
  constructor({ infraBridge, bot, adminId, a2a }) {
    this.infra = infraBridge;
    this.bot = bot;
    this.adminId = adminId;
    this.a2a = a2a;

    this.lastEval = null;
    this.evalHistory = [];  // In-memory cache of recent evals
    this.stats = {
      evalsRun: 0,
      predictionsStored: 0,
      lastEvalDate: null,
      lastError: null,
    };

    this._ensureTables().catch(e => logger.warn(`[FEEDBACK] Table init: ${e.message}`));
  }

  // ══════════════════════════════════════════
  //  TABLE SETUP
  // ══════════════════════════════════════════

  async _ensureTables() {
    if (!this.infra?.pgPool) return;

    const client = await this.infra.pgPool.connect();
    try {
      await client.query('SET search_path TO public');

      await client.query(`
        CREATE TABLE IF NOT EXISTS nba_predictions (
          id SERIAL PRIMARY KEY,
          game_date DATE NOT NULL,
          home_team TEXT NOT NULL,
          away_team TEXT NOT NULL,
          predicted_home_prob REAL NOT NULL,
          model_version TEXT,
          created_at TIMESTAMPTZ DEFAULT NOW(),
          UNIQUE(game_date, home_team, away_team)
        )
      `);

      await client.query(`
        CREATE TABLE IF NOT EXISTS nba_daily_eval (
          id SERIAL PRIMARY KEY,
          eval_date DATE UNIQUE NOT NULL,
          total_games INT,
          correct INT,
          accuracy REAL,
          brier_score REAL,
          roi REAL,
          details JSONB,
          created_at TIMESTAMPTZ DEFAULT NOW()
        )
      `);

      logger.info('[FEEDBACK] Tables ensured: nba_predictions, nba_daily_eval');
    } finally {
      client.release();
    }
  }

  // ══════════════════════════════════════════
  //  STORE PREDICTIONS
  // ══════════════════════════════════════════

  /**
   * Store a batch of predictions for a given date.
   * @param {Array} predictions - [{home_team, away_team, predicted_home_prob, model_version}]
   * @param {string} gameDate - YYYY-MM-DD
   */
  async storePredictions(predictions, gameDate) {
    if (!this.infra?.pgPool || !predictions?.length) return 0;

    const client = await this.infra.pgPool.connect();
    let stored = 0;
    try {
      await client.query('SET search_path TO public');

      for (const pred of predictions) {
        try {
          await client.query(`
            INSERT INTO nba_predictions (game_date, home_team, away_team, predicted_home_prob, model_version)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (game_date, home_team, away_team) DO UPDATE SET
              predicted_home_prob = EXCLUDED.predicted_home_prob,
              model_version = EXCLUDED.model_version,
              created_at = NOW()
          `, [
            gameDate,
            normalizeTeam(pred.home_team),
            normalizeTeam(pred.away_team),
            pred.predicted_home_prob,
            pred.model_version || 'unknown',
          ]);
          stored++;
        } catch (e) {
          logger.warn(`[FEEDBACK] Store prediction: ${e.message}`);
        }
      }
      this.stats.predictionsStored += stored;
      logger.info(`[FEEDBACK] Stored ${stored}/${predictions.length} predictions for ${gameDate}`);
    } finally {
      client.release();
    }
    return stored;
  }

  // ══════════════════════════════════════════
  //  FETCH ESPN SCORES (FREE, NO AUTH)
  // ══════════════════════════════════════════

  async fetchESPNScores(dateStr) {
    // dateStr: YYYY-MM-DD → YYYYMMDD for ESPN
    const espnDate = dateStr.replace(/-/g, '');
    const url = `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=${espnDate}`;

    try {
      const resp = await fetch(url, { signal: AbortSignal.timeout(15000) });
      if (!resp.ok) throw new Error(`ESPN ${resp.status}`);

      const data = await resp.json();
      const games = [];

      for (const event of (data.events || [])) {
        const competition = event.competitions?.[0];
        if (!competition) continue;

        const competitors = competition.competitors || [];
        const home = competitors.find(c => c.homeAway === 'home');
        const away = competitors.find(c => c.homeAway === 'away');

        if (!home || !away) continue;

        const completed = competition.status?.type?.completed || false;
        games.push({
          home_team: normalizeTeam(home.team?.displayName || home.team?.name),
          away_team: normalizeTeam(away.team?.displayName || away.team?.name),
          home_score: parseInt(home.score) || 0,
          away_score: parseInt(away.score) || 0,
          completed,
          status: competition.status?.type?.description || 'Unknown',
        });
      }

      logger.info(`[FEEDBACK] ESPN scores for ${dateStr}: ${games.length} games (${games.filter(g => g.completed).length} completed)`);
      return games;
    } catch (err) {
      logger.error(`[FEEDBACK] ESPN fetch failed for ${dateStr}: ${err.message}`);
      this.stats.lastError = `ESPN: ${err.message} @ ${new Date().toISOString()}`;
      return null;
    }
  }

  // ══════════════════════════════════════════
  //  EVALUATE DAY — Core feedback loop
  // ══════════════════════════════════════════

  async evaluateDay(dateStr) {
    if (!this.infra?.pgPool) {
      return { error: 'No database connection' };
    }

    // 1. Fetch predictions for this date from Supabase
    const predResult = await this.infra.querySupabase(
      `SELECT * FROM nba_predictions WHERE game_date = '${dateStr}' ORDER BY home_team`
    );
    const predictions = predResult.rows || [];

    if (predictions.length === 0) {
      logger.info(`[FEEDBACK] No predictions for ${dateStr} — skipping eval`);
      return { date: dateStr, error: 'No predictions found', total: 0 };
    }

    // 2. Fetch real scores from ESPN
    const scores = await this.fetchESPNScores(dateStr);
    if (!scores || scores.length === 0) {
      return { date: dateStr, error: 'No ESPN scores available', total: 0 };
    }

    const completedScores = scores.filter(g => g.completed);
    if (completedScores.length === 0) {
      return { date: dateStr, error: 'Games not yet completed', total: scores.length };
    }

    // 3. Match predictions to outcomes
    const details = [];
    let totalBrier = 0;
    let correct = 0;
    let matched = 0;

    for (const pred of predictions) {
      const homeNorm = normalizeTeam(pred.home_team);
      const awayNorm = normalizeTeam(pred.away_team);

      // Find matching score
      const score = completedScores.find(s =>
        s.home_team === homeNorm && s.away_team === awayNorm
      );

      if (!score) {
        details.push({
          home: pred.home_team,
          away: pred.away_team,
          status: 'no_score_match',
        });
        continue;
      }

      matched++;
      const homeWon = score.home_score > score.away_score;
      const predHomeProb = pred.predicted_home_prob;

      // Brier score: (predicted_prob - actual_outcome)^2
      const outcome = homeWon ? 1 : 0;
      const brier = Math.pow(predHomeProb - outcome, 2);
      totalBrier += brier;

      // Did we predict correctly? (>0.5 means we predicted home win)
      const predictedHome = predHomeProb > 0.5;
      const isCorrect = predictedHome === homeWon;
      if (isCorrect) correct++;

      details.push({
        home: pred.home_team,
        away: pred.away_team,
        predicted_home_prob: predHomeProb,
        home_score: score.home_score,
        away_score: score.away_score,
        home_won: homeWon,
        correct: isCorrect,
        brier,
      });
    }

    if (matched === 0) {
      return { date: dateStr, error: 'No predictions matched to scores', predictions: predictions.length, scores: completedScores.length };
    }

    const avgBrier = totalBrier / matched;
    const accuracy = correct / matched;

    const evalResult = {
      date: dateStr,
      total_games: matched,
      correct,
      accuracy: +accuracy.toFixed(4),
      brier_score: +avgBrier.toFixed(4),
      predictions_total: predictions.length,
      scores_total: completedScores.length,
      details,
    };

    // 4. Store in Supabase
    await this._storeEval(evalResult);

    // 5. Post to A2A + Telegram
    await this._reportEval(evalResult);

    this.lastEval = evalResult;
    this.evalHistory.push({ date: dateStr, brier: avgBrier, accuracy, correct, total: matched });
    if (this.evalHistory.length > 90) this.evalHistory = this.evalHistory.slice(-90);
    this.stats.evalsRun++;
    this.stats.lastEvalDate = dateStr;

    // ── Live regression detection ──
    await this._checkLiveRegression(avgBrier, dateStr);

    logger.info(`[FEEDBACK] Eval ${dateStr}: ${correct}/${matched} correct (${(accuracy * 100).toFixed(1)}%), Brier ${avgBrier.toFixed(4)}`);
    return evalResult;
  }

  // ══════════════════════════════════════════
  //  LIVE REGRESSION DETECTION
  // ══════════════════════════════════════════

  async _checkLiveRegression(avgBrier, dateStr) {
    try {
      // Compare to historical best from recent evals
      const recent = this.evalHistory.slice(-14);  // 2 weeks
      if (recent.length < 3) return;

      const bestHistorical = Math.min(...recent.map(e => e.brier));
      const last3 = this.evalHistory.slice(-3);
      const allWorse = last3.every(e => e.brier > bestHistorical + 0.02);

      if (allWorse) {
        const msg = `Live regression: last 3 days Brier avg ${(last3.reduce((s, e) => s + e.brier, 0) / 3).toFixed(4)} > best ${bestHistorical.toFixed(4)} + 0.02`;
        logger.warn(`[FEEDBACK] ${msg}`);

        if (this.a2a) {
          this.a2a.postReport({
            type: 'live_regression',
            level: 'WARNING',
            message: msg,
            data: {
              last3: last3.map(e => ({ date: e.date, brier: e.brier })),
              bestHistorical,
              recommendedAction: 'rollback',
            },
          });
        }

        if (this.bot && this.adminId) {
          await this.bot.sendMessage(this.adminId,
            `⚠️ *LIVE REGRESSION*\n${msg}\nRecommend: rollback to best checkpoint`,
            { parse_mode: 'Markdown' }
          ).catch(() => {});
        }
      }
    } catch (err) {
      logger.debug(`[FEEDBACK] Regression check error: ${err.message}`);
    }
  }

  // ══════════════════════════════════════════
  //  STORE EVAL
  // ══════════════════════════════════════════

  async _storeEval(evalResult) {
    if (!this.infra?.pgPool) return;

    try {
      const client = await this.infra.pgPool.connect();
      try {
        await client.query('SET search_path TO public');
        await client.query(`
          INSERT INTO nba_daily_eval (eval_date, total_games, correct, accuracy, brier_score, details)
          VALUES ($1, $2, $3, $4, $5, $6)
          ON CONFLICT (eval_date) DO UPDATE SET
            total_games = EXCLUDED.total_games,
            correct = EXCLUDED.correct,
            accuracy = EXCLUDED.accuracy,
            brier_score = EXCLUDED.brier_score,
            details = EXCLUDED.details
        `, [
          evalResult.date,
          evalResult.total_games,
          evalResult.correct,
          evalResult.accuracy,
          evalResult.brier_score,
          JSON.stringify(evalResult.details),
        ]);
      } finally {
        client.release();
      }
    } catch (e) {
      logger.error(`[FEEDBACK] Store eval failed: ${e.message}`);
    }
  }

  // ══════════════════════════════════════════
  //  REPORT EVAL
  // ══════════════════════════════════════════

  async _reportEval(evalResult) {
    const { date, correct, total_games, accuracy, brier_score, details } = evalResult;
    const pct = (accuracy * 100).toFixed(1);
    const brierEmoji = brier_score < 0.22 ? '🟢' : brier_score < 0.25 ? '🟡' : '🔴';

    // A2A
    if (this.a2a) {
      this.a2a.postReport({
        type: 'daily_eval',
        level: 'INFO',
        message: `Eval ${date}: ${correct}/${total_games} (${pct}%) | Brier ${brier_score.toFixed(4)}`,
        data: evalResult,
      });
    }

    // Telegram
    if (this.bot) {
      const lines = [
        `📊 *DAILY EVAL — ${date}*`,
        '',
        `${brierEmoji} Brier: *${brier_score.toFixed(4)}* (target < 0.20)`,
        `🎯 Accuracy: *${pct}%* (${correct}/${total_games})`,
        '',
        '*Game Details:*',
      ];

      for (const d of details.filter(d => d.brier !== undefined).slice(0, 8)) {
        const icon = d.correct ? '✅' : '❌';
        lines.push(`${icon} ${d.away} @ ${d.home}: ${d.away_score}-${d.home_score} (pred: ${(d.predicted_home_prob * 100).toFixed(0)}% home)`);
      }

      try {
        await this.bot.sendMessage(this.adminId, lines.join('\n'), { parse_mode: 'Markdown' });
      } catch (e) {
        logger.warn(`[FEEDBACK] Telegram send failed: ${e.message}`);
      }
    }
  }

  // ══════════════════════════════════════════
  //  QUERIES
  // ══════════════════════════════════════════

  async getHistory(days = 30) {
    if (!this.infra?.pgPool) return this.evalHistory.slice(-days);

    try {
      const result = await this.infra.querySupabase(`
        SELECT eval_date, total_games, correct, accuracy, brier_score
        FROM nba_daily_eval
        ORDER BY eval_date DESC
        LIMIT ${days}
      `);
      return result.rows || [];
    } catch (e) {
      logger.warn(`[FEEDBACK] getHistory: ${e.message}`);
      return this.evalHistory.slice(-days);
    }
  }

  async getTrend() {
    const history = await this.getHistory(7);
    if (history.length === 0) return null;

    const brierArr = history.filter(h => h.brier_score != null).map(h => h.brier_score);
    const accArr = history.filter(h => h.accuracy != null).map(h => h.accuracy);

    const avg = arr => arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : null;

    return {
      days: history.length,
      avg_brier_7d: avg(brierArr) ? +avg(brierArr).toFixed(4) : null,
      avg_accuracy_7d: avg(accArr) ? +avg(accArr).toFixed(4) : null,
      latest: history[0] || null,
      improving: brierArr.length >= 2 ? brierArr[0] < brierArr[brierArr.length - 1] : null,
    };
  }

  async getLatest() {
    if (!this.infra?.pgPool) return this.lastEval;

    try {
      const result = await this.infra.querySupabase(`
        SELECT * FROM nba_daily_eval ORDER BY eval_date DESC LIMIT 1
      `);
      return result.rows?.[0] || this.lastEval;
    } catch {
      return this.lastEval;
    }
  }

  // ══════════════════════════════════════════
  //  STATUS
  // ══════════════════════════════════════════

  getStatus() {
    return {
      lastEval: this.lastEval ? {
        date: this.lastEval.date,
        brier: this.lastEval.brier_score,
        accuracy: this.lastEval.accuracy,
        correct: this.lastEval.correct,
        total: this.lastEval.total_games,
      } : null,
      stats: this.stats,
      historyCount: this.evalHistory.length,
    };
  }
}

module.exports = FeedbackLoop;
