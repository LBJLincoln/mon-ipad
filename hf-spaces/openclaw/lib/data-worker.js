/**
 * Data Worker — Real NBA Data Collection (Eve's primary job)
 *
 * Fetches REAL data from external APIs and stores in Supabase:
 *   1. Live NBA odds — The Odds API (dormant until quota resets April 1)
 *   2. NBA scores — ESPN free API (no auth, unlimited)
 *   3. Line movement tracking — computes CLV for past predictions
 *
 * ESPN API (free, no auth):
 *   GET https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD
 *
 * NO LLM NEEDED. Pure data work.
 */

const logger = require('./logger');

const ODDS_API_BASE = 'https://api.the-odds-api.com/v4';
const NBA_SPORT = 'basketball_nba';
const ESPN_SCOREBOARD = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard';

class DataWorker {
  constructor({ oddsApiKey, infraBridge, spaceExecutor, bot, adminId }) {
    this.oddsApiKey = oddsApiKey || process.env.ODDS_API_KEY;
    this.infra = infraBridge;
    this.spaces = spaceExecutor;
    this.bot = bot;
    this.adminId = adminId;

    // State
    this.lastOddsFetch = null;
    this.lastScoresFetch = null;
    this.oddsHistory = [];       // Ring buffer of recent fetches
    this.lineMovements = [];     // Detected line movements
    this.stats = {
      oddsFetches: 0,
      scoresFetches: 0,
      gamesTracked: 0,
      oddsStored: 0,
      errors: 0,
      lastError: null,
      apiQuotaUsed: null,
      apiQuotaRemaining: null,
    };
  }

  // ══════════════════════════════════════════
  //  ODDS FETCHER — The Odds API (dormant until quota resets)
  // ══════════════════════════════════════════

  async fetchOdds() {
    // Odds API only — OddsHarvester removed (Playwright can't build on HF Spaces)
    // Quota resets monthly. When exhausted, silently skip.
    return await this._fetchViaOddsAPI();
  }

  /**
   * Fetch odds via The Odds API (paid, quota limited)
   * Dormant when quota exhausted (returns null gracefully).
   */
  async _fetchViaOddsAPI() {
    if (!this.oddsApiKey) {
      logger.warn('[DATA-WORKER] No ODDS_API_KEY — skipping odds API fallback');
      return null;
    }

    try {
      const url = `${ODDS_API_BASE}/sports/${NBA_SPORT}/odds/?apiKey=${this.oddsApiKey}&regions=us,eu&markets=h2h,spreads,totals&oddsFormat=american&bookmakers=draftkings,fanduel,betmgm,pointsbet,bovada,pinnacle`;

      const resp = await fetch(url, { signal: AbortSignal.timeout(15000) });

      if (!resp.ok) {
        throw new Error(`Odds API ${resp.status}: ${await resp.text()}`);
      }

      // Track API quota
      this.stats.apiQuotaUsed = resp.headers.get('x-requests-used');
      this.stats.apiQuotaRemaining = resp.headers.get('x-requests-remaining');

      const games = await resp.json();
      this.stats.oddsFetches++;
      this.stats.oddsSource = 'odds-api';
      this.lastOddsFetch = new Date().toISOString();

      if (!games || games.length === 0) {
        logger.info('[DATA-WORKER] No upcoming NBA games found');
        return { games: [], stored: 0 };
      }

      logger.info(`[DATA-WORKER] Fetched odds for ${games.length} NBA games`);

      // Process and store
      const processed = this._processOdds(games);
      let stored = 0;

      if (this.infra?.pgPool) {
        stored = await this._storeOdds(processed);
      }

      // Detect line movements
      this._detectLineMovements(processed);

      // Add to ring buffer
      this.oddsHistory.push({
        timestamp: this.lastOddsFetch,
        gameCount: games.length,
        stored,
      });
      if (this.oddsHistory.length > 100) this.oddsHistory = this.oddsHistory.slice(-100);

      this.stats.oddsStored += stored;
      this.stats.gamesTracked = games.length;

      return { games: processed, stored, lineMovements: this.lineMovements.slice(-10) };
    } catch (err) {
      this.stats.errors++;
      this.stats.lastError = `${err.message} @ ${new Date().toISOString()}`;
      logger.error(`[DATA-WORKER] Odds fetch failed: ${err.message}`);
      return null;
    }
  }

  /**
   * Process raw Odds API response into structured records
   */
  _processOdds(games) {
    const now = new Date().toISOString();
    return games.map(game => {
      const record = {
        game_id: game.id,
        sport: game.sport_key,
        commence_time: game.commence_time,
        home_team: game.home_team,
        away_team: game.away_team,
        fetched_at: now,
        bookmakers: {},
      };

      for (const bk of (game.bookmakers || [])) {
        const bookmaker = {
          key: bk.key,
          title: bk.title,
          last_update: bk.last_update,
          markets: {},
        };

        for (const market of (bk.markets || [])) {
          bookmaker.markets[market.key] = market.outcomes.map(o => ({
            name: o.name,
            price: o.price,
            point: o.point,
          }));
        }

        record.bookmakers[bk.key] = bookmaker;
      }

      // Compute consensus odds (average across bookmakers)
      record.consensus = this._computeConsensus(record);

      return record;
    });
  }

  /**
   * Compute consensus odds across bookmakers
   */
  _computeConsensus(game) {
    const h2hPrices = { home: [], away: [] };
    const spreads = { home: [], away: [] };
    const totals = { over: [], under: [] };

    for (const bk of Object.values(game.bookmakers)) {
      // H2H (moneyline)
      const h2h = bk.markets.h2h;
      if (h2h) {
        for (const o of h2h) {
          if (o.name === game.home_team) h2hPrices.home.push(o.price);
          else h2hPrices.away.push(o.price);
        }
      }

      // Spreads
      const spread = bk.markets.spreads;
      if (spread) {
        for (const o of spread) {
          if (o.name === game.home_team) spreads.home.push({ price: o.price, point: o.point });
          else spreads.away.push({ price: o.price, point: o.point });
        }
      }

      // Totals
      const total = bk.markets.totals;
      if (total) {
        for (const o of total) {
          if (o.name === 'Over') totals.over.push({ price: o.price, point: o.point });
          else totals.under.push({ price: o.price, point: o.point });
        }
      }
    }

    const avg = arr => arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : null;
    const avgPoint = arr => arr.length > 0 ? arr.reduce((a, b) => a + b.point, 0) / arr.length : null;

    return {
      moneyline_home: avg(h2hPrices.home),
      moneyline_away: avg(h2hPrices.away),
      spread_home: avgPoint(spreads.home),
      spread_away: avgPoint(spreads.away),
      total_line: avgPoint(totals.over),
      implied_home_prob: h2hPrices.home.length > 0 ? this._americanToProb(avg(h2hPrices.home)) : null,
      implied_away_prob: h2hPrices.away.length > 0 ? this._americanToProb(avg(h2hPrices.away)) : null,
      bookmaker_count: Object.keys(game.bookmakers).length,
    };
  }

  /**
   * Convert American odds to implied probability
   */
  _americanToProb(american) {
    if (american >= 100) return 100 / (american + 100);
    if (american <= -100) return Math.abs(american) / (Math.abs(american) + 100);
    return 0.5;
  }

  /**
   * Detect significant line movements (comparing to previous fetch)
   */
  _detectLineMovements(currentGames) {
    if (this.oddsHistory.length < 2) return;

    // Compare with last stored odds in ring buffer
    // For now, track spread movements > 1 point
    for (const game of currentGames) {
      if (game.consensus.spread_home !== null) {
        const key = `${game.home_team}_${game.away_team}_${game.commence_time}`;
        const prev = this._previousSpread(key);

        if (prev !== null && Math.abs(game.consensus.spread_home - prev) >= 1.0) {
          const movement = {
            timestamp: new Date().toISOString(),
            game: `${game.away_team} @ ${game.home_team}`,
            commence: game.commence_time,
            prev_spread: prev,
            curr_spread: game.consensus.spread_home,
            delta: +(game.consensus.spread_home - prev).toFixed(1),
            steam: Math.abs(game.consensus.spread_home - prev) >= 2.0,
          };

          this.lineMovements.push(movement);
          if (this.lineMovements.length > 200) this.lineMovements = this.lineMovements.slice(-200);

          // Alert on steam moves (2+ points)
          if (movement.steam && this.bot) {
            const msg = `🔥 *STEAM MOVE*\n${movement.game}\nSpread: ${movement.prev_spread} → ${movement.curr_spread} (${movement.delta > 0 ? '+' : ''}${movement.delta})`;
            this.bot.sendMessage(this.adminId, msg, { parse_mode: 'Markdown' }).catch(() => {});
          }

          logger.info(`[DATA-WORKER] Line movement: ${movement.game} spread ${movement.prev_spread} → ${movement.curr_spread}`);
        }

        // Store for next comparison
        this._storeSpread(key, game.consensus.spread_home);
      }
    }
  }

  // Simple in-memory spread tracker for line movement detection
  _spreadCache = {};

  _previousSpread(key) {
    return this._spreadCache[key] ?? null;
  }

  _storeSpread(key, spread) {
    this._spreadCache[key] = spread;
  }

  // ══════════════════════════════════════════
  //  SCORES FETCHER — ESPN free API (no auth, unlimited)
  // ══════════════════════════════════════════

  async fetchScores(dateStr) {
    try {
      // Default to today if no date specified
      const d = dateStr ? dateStr.replace(/-/g, '') : new Date().toISOString().slice(0, 10).replace(/-/g, '');
      const url = `${ESPN_SCOREBOARD}?dates=${d}`;
      const resp = await fetch(url, { signal: AbortSignal.timeout(15000) });

      if (!resp.ok) {
        throw new Error(`ESPN ${resp.status}`);
      }

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
          id: event.id,
          home: home.team?.displayName || home.team?.name,
          away: away.team?.displayName || away.team?.name,
          home_score: parseInt(home.score) || 0,
          away_score: parseInt(away.score) || 0,
          commence: event.date,
          completed,
          status: competition.status?.type?.description || 'Unknown',
        });
      }

      this.stats.scoresFetches++;
      this.lastScoresFetch = new Date().toISOString();

      const completed = games.filter(g => g.completed);
      const live = games.filter(g => !g.completed && g.status !== 'Scheduled');
      const upcoming = games.length - completed.length - live.length;

      logger.info(`[DATA-WORKER] ESPN scores: ${completed.length} completed, ${live.length} live, ${upcoming} upcoming`);

      // Store completed game results in Supabase
      if (completed.length > 0 && this.infra?.pgPool) {
        await this._storeScoresESPN(completed);
      }

      return {
        source: 'espn',
        total: games.length,
        completed: completed.length,
        live: live.length,
        games,
      };
    } catch (err) {
      this.stats.errors++;
      logger.error(`[DATA-WORKER] ESPN scores failed: ${err.message}`);
      return null;
    }
  }

  /**
   * Store ESPN scores in Supabase nba_scores table
   */
  async _storeScoresESPN(completedGames) {
    if (!this.infra?.pgPool) return;

    try {
      const client = await this.infra.pgPool.connect();
      try {
        await client.query('SET search_path TO public');

        await client.query(`
          CREATE TABLE IF NOT EXISTS nba_scores (
            id SERIAL PRIMARY KEY,
            game_id TEXT UNIQUE NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            commence_time TIMESTAMPTZ,
            home_score INT,
            away_score INT,
            completed BOOLEAN DEFAULT FALSE,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
          )
        `);

        for (const game of completedGames) {
          try {
            await client.query(`
              INSERT INTO nba_scores (game_id, home_team, away_team, commence_time, home_score, away_score, completed)
              VALUES ($1, $2, $3, $4, $5, $6, TRUE)
              ON CONFLICT (game_id) DO UPDATE SET
                home_score = EXCLUDED.home_score,
                away_score = EXCLUDED.away_score,
                completed = TRUE
            `, [
              `espn_${game.id}`,
              game.home,
              game.away,
              game.commence || new Date().toISOString(),
              game.home_score,
              game.away_score,
            ]);
          } catch (e) {
            if (!e.message.includes('duplicate')) {
              logger.warn(`[DATA-WORKER] Store ESPN score error: ${e.message}`);
            }
          }
        }
      } finally {
        client.release();
      }
    } catch (err) {
      logger.error(`[DATA-WORKER] ESPN scores storage failed: ${err.message}`);
    }
  }

  // ══════════════════════════════════════════
  //  SUPABASE STORAGE
  // ══════════════════════════════════════════

  async _storeOdds(games) {
    if (!this.infra?.pgPool) return 0;
    let stored = 0;

    try {
      const client = await this.infra.pgPool.connect();
      try {
        await client.query('SET search_path TO public');

        // Ensure table exists
        await client.query(`
          CREATE TABLE IF NOT EXISTS nba_odds (
            id SERIAL PRIMARY KEY,
            game_id TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            commence_time TIMESTAMPTZ NOT NULL,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            consensus_ml_home REAL,
            consensus_ml_away REAL,
            consensus_spread_home REAL,
            consensus_total REAL,
            implied_home_prob REAL,
            implied_away_prob REAL,
            bookmaker_count INT,
            raw_bookmakers JSONB,
            UNIQUE(game_id, fetched_at)
          )
        `);

        for (const game of games) {
          try {
            await client.query(`
              INSERT INTO nba_odds (game_id, home_team, away_team, commence_time, fetched_at,
                consensus_ml_home, consensus_ml_away, consensus_spread_home, consensus_total,
                implied_home_prob, implied_away_prob, bookmaker_count, raw_bookmakers)
              VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
              ON CONFLICT (game_id, fetched_at) DO NOTHING
            `, [
              game.game_id, game.home_team, game.away_team, game.commence_time, game.fetched_at,
              game.consensus.moneyline_home, game.consensus.moneyline_away,
              game.consensus.spread_home, game.consensus.total_line,
              game.consensus.implied_home_prob, game.consensus.implied_away_prob,
              game.consensus.bookmaker_count,
              JSON.stringify(game.bookmakers),
            ]);
            stored++;
          } catch (e) {
            // Duplicate or constraint violation — skip
            if (!e.message.includes('duplicate') && !e.message.includes('unique')) {
              logger.warn(`[DATA-WORKER] Store odds error: ${e.message}`);
            }
          }
        }
      } finally {
        client.release();
      }
    } catch (err) {
      logger.error(`[DATA-WORKER] Supabase odds storage failed: ${err.message}`);
    }

    return stored;
  }

  // _storeScores removed — replaced by _storeScoresESPN above

  // ══════════════════════════════════════════
  //  CLV ANALYSIS — Closing Line Value
  // ══════════════════════════════════════════

  async computeCLV() {
    if (!this.infra?.pgPool) return null;

    try {
      const result = await this.infra.querySupabase(`
        WITH predictions AS (
          SELECT * FROM nba_predictions
          WHERE created_at > NOW() - INTERVAL '7 days'
          AND result IS NOT NULL
        ),
        closing_odds AS (
          SELECT DISTINCT ON (game_id)
            game_id, consensus_ml_home, consensus_ml_away,
            implied_home_prob, implied_away_prob
          FROM nba_odds
          ORDER BY game_id, fetched_at DESC
        )
        SELECT
          p.*,
          c.implied_home_prob AS closing_home_prob,
          c.implied_away_prob AS closing_away_prob
        FROM predictions p
        LEFT JOIN closing_odds c ON p.game_id = c.game_id
        WHERE c.game_id IS NOT NULL
        LIMIT 50
      `);

      if (!result.rows || result.rows.length === 0) {
        return { clv: null, message: 'No predictions with closing lines available' };
      }

      // CLV = our_predicted_prob - closing_prob (positive = we were right before the market)
      let totalCLV = 0;
      let count = 0;

      for (const row of result.rows) {
        const ourProb = row.predicted_prob;
        const closingProb = row.pick === 'home' ? row.closing_home_prob : row.closing_away_prob;

        if (ourProb && closingProb) {
          totalCLV += (ourProb - closingProb);
          count++;
        }
      }

      return {
        avgCLV: count > 0 ? +(totalCLV / count).toFixed(4) : null,
        sampleSize: count,
        totalPredictions: result.rows.length,
        positive: totalCLV > 0,
      };
    } catch (err) {
      logger.warn(`[DATA-WORKER] CLV computation failed: ${err.message}`);
      return null;
    }
  }

  // ══════════════════════════════════════════
  //  STATUS
  // ══════════════════════════════════════════

  getStatus() {
    return {
      lastOddsFetch: this.lastOddsFetch,
      lastScoresFetch: this.lastScoresFetch,
      oddsApiKey: this.oddsApiKey ? 'configured' : 'MISSING',
      supabase: this.infra?.pgPool ? 'connected' : 'not connected',
      stats: this.stats,
      recentOdds: this.oddsHistory.slice(-5),
      recentMovements: this.lineMovements.slice(-10),
    };
  }
}

module.exports = DataWorker;
