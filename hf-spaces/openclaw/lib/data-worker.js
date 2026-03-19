/**
 * Data Worker — Real NBA Data Collection
 *
 * Fetches REAL data from external APIs and stores in Supabase:
 *   1. Live NBA odds — The Odds API (dormant until quota resets April 1)
 *   2. NBA scores — ESPN free API (no auth, unlimited)
 *   3. Line movement tracking — computes CLV for past predictions
 *   4. Injuries — ESPN free API
 *   5. Box scores — NBA.com CDN
 *   6. Lineups — RotoWire (via Chromium scraping)
 *   7. Referee assignments — NBA.com (via Chromium scraping)
 *   8. Basketball Reference — advanced stats (via Chromium scraping)
 *
 * NO LLM NEEDED. Pure data work.
 */

const logger = require('./logger');
let browser; // lazy-loaded

const ODDS_API_BASE = 'https://api.the-odds-api.com/v4';
const NBA_SPORT = 'basketball_nba';
const ESPN_SCOREBOARD = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard';
const ESPN_INJURIES = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries';
const NBA_CDN_BOXSCORE = 'https://cdn.nba.com/static/json/liveData/boxscore/boxscore_';
const NBA_CDN_SCOREBOARD = 'https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json';
const NBA_CDN_HEADERS = { 'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.nba.com' };

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
    this.lastInjuriesFetch = null;
    this.lastBoxScoresFetch = null;
    this.oddsHistory = [];       // Ring buffer of recent fetches
    this.lineMovements = [];     // Detected line movements
    this.stats = {
      oddsFetches: 0,
      scoresFetches: 0,
      injuriesFetches: 0,
      boxScoresFetches: 0,
      todaysGamesFetches: 0,
      gamesTracked: 0,
      oddsStored: 0,
      injuriesStored: 0,
      playerStatsStored: 0,
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
  //  INJURIES FETCHER — ESPN free API (no auth)
  // ══════════════════════════════════════════

  /**
   * Fetch NBA injuries from ESPN free API.
   * Parses player name, team, status (Out/Day-to-Day/Questionable), injury type.
   * Stores in Supabase nba_injuries table.
   */
  async fetchInjuries() {
    try {
      const resp = await fetch(ESPN_INJURIES, { signal: AbortSignal.timeout(15000) });

      if (!resp.ok) {
        throw new Error(`ESPN Injuries ${resp.status}: ${await resp.text()}`);
      }

      const data = await resp.json();
      const injuries = [];

      for (const team of (data.items || [])) {
        const teamName = team.team?.displayName || team.team?.name || 'Unknown';
        const teamAbbr = team.team?.abbreviation || '';

        for (const entry of (team.injuries || [])) {
          injuries.push({
            player_name: entry.athlete?.displayName || entry.athlete?.fullName || 'Unknown',
            player_id: entry.athlete?.id || null,
            team: teamName,
            team_abbr: teamAbbr,
            status: entry.status || 'Unknown',
            injury_type: entry.type?.description || entry.details?.type || entry.description || 'Unknown',
            detail: entry.details?.detail || entry.longComment || null,
            updated_at: new Date().toISOString(),
          });
        }
      }

      this.stats.injuriesFetches++;
      this.lastInjuriesFetch = new Date().toISOString();

      logger.info(`[DATA-WORKER] ESPN injuries: ${injuries.length} players across ${(data.items || []).length} teams`);

      // Store in Supabase
      let stored = 0;
      if (injuries.length > 0 && this.infra?.pgPool) {
        stored = await this._storeInjuries(injuries);
      }

      this.stats.injuriesStored += stored;

      return {
        source: 'espn',
        total: injuries.length,
        stored,
        injuries,
      };
    } catch (err) {
      this.stats.errors++;
      this.stats.lastError = `injuries: ${err.message} @ ${new Date().toISOString()}`;
      logger.error(`[DATA-WORKER] ESPN injuries fetch failed: ${err.message}`);
      return null;
    }
  }

  /**
   * Store injuries in Supabase nba_injuries table
   */
  async _storeInjuries(injuries) {
    if (!this.infra?.pgPool) return 0;
    let stored = 0;

    try {
      const client = await this.infra.pgPool.connect();
      try {
        await client.query('SET search_path TO public');

        await client.query(`
          CREATE TABLE IF NOT EXISTS nba_injuries (
            id SERIAL PRIMARY KEY,
            player_name TEXT NOT NULL,
            player_id TEXT,
            team TEXT NOT NULL,
            team_abbr TEXT,
            status TEXT NOT NULL,
            injury_type TEXT,
            detail TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(player_name, team)
          )
        `);

        for (const inj of injuries) {
          try {
            await client.query(`
              INSERT INTO nba_injuries (player_name, player_id, team, team_abbr, status, injury_type, detail, updated_at)
              VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
              ON CONFLICT (player_name, team) DO UPDATE SET
                player_id = EXCLUDED.player_id,
                team_abbr = EXCLUDED.team_abbr,
                status = EXCLUDED.status,
                injury_type = EXCLUDED.injury_type,
                detail = EXCLUDED.detail,
                updated_at = EXCLUDED.updated_at,
                recorded_at = NOW()
            `, [
              inj.player_name,
              inj.player_id,
              inj.team,
              inj.team_abbr,
              inj.status,
              inj.injury_type,
              inj.detail,
              inj.updated_at,
            ]);
            stored++;
          } catch (e) {
            if (!e.message.includes('duplicate')) {
              logger.warn(`[DATA-WORKER] Store injury error: ${e.message}`);
            }
          }
        }
      } finally {
        client.release();
      }
    } catch (err) {
      logger.error(`[DATA-WORKER] Injuries storage failed: ${err.message}`);
    }

    return stored;
  }

  // ══════════════════════════════════════════
  //  BOX SCORES FETCHER — NBA.com CDN (free, no auth)
  // ══════════════════════════════════════════

  /**
   * Fetch box score for a specific game from NBA.com CDN.
   * Extracts per-player stats: minutes, points, rebounds, assists, plus_minus, etc.
   * Stores in Supabase nba_player_stats table.
   * @param {string} gameId — NBA game ID (e.g. "0022300123")
   */
  async fetchBoxScores(gameId) {
    if (!gameId) {
      logger.warn('[DATA-WORKER] fetchBoxScores called without gameId');
      return null;
    }

    try {
      const url = `${NBA_CDN_BOXSCORE}${gameId}.json`;
      const resp = await fetch(url, {
        signal: AbortSignal.timeout(15000),
        headers: NBA_CDN_HEADERS,
      });

      if (!resp.ok) {
        throw new Error(`NBA CDN BoxScore ${resp.status} for game ${gameId}`);
      }

      const data = await resp.json();
      const game = data.game;
      if (!game) {
        throw new Error(`No game data in response for ${gameId}`);
      }

      const playerStats = [];
      const gameStatus = game.gameStatus || 0;
      const gameStatusText = game.gameStatusText || '';
      const gameDateUTC = game.gameTimeUTC || new Date().toISOString();

      // Process both home and away teams
      for (const side of ['homeTeam', 'awayTeam']) {
        const team = game[side];
        if (!team) continue;

        const teamName = team.teamName || '';
        const teamAbbr = team.teamTricode || '';
        const teamCity = team.teamCity || '';
        const isHome = side === 'homeTeam';

        for (const player of (team.players || [])) {
          const stats = player.statistics || {};
          playerStats.push({
            game_id: gameId,
            game_date: gameDateUTC,
            player_name: player.name || `${player.firstName || ''} ${player.familyName || ''}`.trim(),
            player_id: String(player.personId || ''),
            team: `${teamCity} ${teamName}`.trim(),
            team_abbr: teamAbbr,
            is_home: isHome,
            starter: player.starter === '1' || player.starter === true,
            minutes: stats.minutes || stats.minutesCalculated || '0:00',
            points: parseInt(stats.points) || 0,
            rebounds: parseInt(stats.reboundsTotal) || 0,
            offensive_rebounds: parseInt(stats.reboundsOffensive) || 0,
            defensive_rebounds: parseInt(stats.reboundsDefensive) || 0,
            assists: parseInt(stats.assists) || 0,
            steals: parseInt(stats.steals) || 0,
            blocks: parseInt(stats.blocks) || 0,
            turnovers: parseInt(stats.turnovers) || 0,
            personal_fouls: parseInt(stats.foulsPersonal) || 0,
            fg_made: parseInt(stats.fieldGoalsMade) || 0,
            fg_attempted: parseInt(stats.fieldGoalsAttempted) || 0,
            fg_pct: parseFloat(stats.fieldGoalsPercentage) || 0,
            three_made: parseInt(stats.threePointersMade) || 0,
            three_attempted: parseInt(stats.threePointersAttempted) || 0,
            three_pct: parseFloat(stats.threePointersPercentage) || 0,
            ft_made: parseInt(stats.freeThrowsMade) || 0,
            ft_attempted: parseInt(stats.freeThrowsAttempted) || 0,
            ft_pct: parseFloat(stats.freeThrowsPercentage) || 0,
            plus_minus: parseFloat(stats.plusMinusPoints) || 0,
            game_status: gameStatus,
            game_status_text: gameStatusText,
          });
        }
      }

      this.stats.boxScoresFetches++;
      this.lastBoxScoresFetch = new Date().toISOString();

      logger.info(`[DATA-WORKER] NBA CDN box score: game ${gameId}, ${playerStats.length} players, status: ${gameStatusText}`);

      // Store in Supabase
      let stored = 0;
      if (playerStats.length > 0 && this.infra?.pgPool) {
        stored = await this._storePlayerStats(playerStats);
      }

      this.stats.playerStatsStored += stored;

      return {
        source: 'nba-cdn',
        gameId,
        gameStatus,
        gameStatusText,
        playerCount: playerStats.length,
        stored,
        players: playerStats,
      };
    } catch (err) {
      this.stats.errors++;
      this.stats.lastError = `boxscore: ${err.message} @ ${new Date().toISOString()}`;
      logger.error(`[DATA-WORKER] NBA CDN box score failed (${gameId}): ${err.message}`);
      return null;
    }
  }

  /**
   * Store player stats in Supabase nba_player_stats table
   */
  async _storePlayerStats(playerStats) {
    if (!this.infra?.pgPool) return 0;
    let stored = 0;

    try {
      const client = await this.infra.pgPool.connect();
      try {
        await client.query('SET search_path TO public');

        await client.query(`
          CREATE TABLE IF NOT EXISTS nba_player_stats (
            id SERIAL PRIMARY KEY,
            game_id TEXT NOT NULL,
            game_date TIMESTAMPTZ,
            player_name TEXT NOT NULL,
            player_id TEXT,
            team TEXT NOT NULL,
            team_abbr TEXT,
            is_home BOOLEAN,
            starter BOOLEAN DEFAULT FALSE,
            minutes TEXT,
            points INT DEFAULT 0,
            rebounds INT DEFAULT 0,
            offensive_rebounds INT DEFAULT 0,
            defensive_rebounds INT DEFAULT 0,
            assists INT DEFAULT 0,
            steals INT DEFAULT 0,
            blocks INT DEFAULT 0,
            turnovers INT DEFAULT 0,
            personal_fouls INT DEFAULT 0,
            fg_made INT DEFAULT 0,
            fg_attempted INT DEFAULT 0,
            fg_pct REAL DEFAULT 0,
            three_made INT DEFAULT 0,
            three_attempted INT DEFAULT 0,
            three_pct REAL DEFAULT 0,
            ft_made INT DEFAULT 0,
            ft_attempted INT DEFAULT 0,
            ft_pct REAL DEFAULT 0,
            plus_minus REAL DEFAULT 0,
            game_status INT DEFAULT 0,
            game_status_text TEXT,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(game_id, player_id)
          )
        `);

        for (const ps of playerStats) {
          try {
            await client.query(`
              INSERT INTO nba_player_stats (
                game_id, game_date, player_name, player_id, team, team_abbr, is_home, starter,
                minutes, points, rebounds, offensive_rebounds, defensive_rebounds,
                assists, steals, blocks, turnovers, personal_fouls,
                fg_made, fg_attempted, fg_pct, three_made, three_attempted, three_pct,
                ft_made, ft_attempted, ft_pct, plus_minus, game_status, game_status_text
              )
              VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30)
              ON CONFLICT (game_id, player_id) DO UPDATE SET
                player_name = EXCLUDED.player_name,
                team = EXCLUDED.team,
                team_abbr = EXCLUDED.team_abbr,
                minutes = EXCLUDED.minutes,
                points = EXCLUDED.points,
                rebounds = EXCLUDED.rebounds,
                offensive_rebounds = EXCLUDED.offensive_rebounds,
                defensive_rebounds = EXCLUDED.defensive_rebounds,
                assists = EXCLUDED.assists,
                steals = EXCLUDED.steals,
                blocks = EXCLUDED.blocks,
                turnovers = EXCLUDED.turnovers,
                personal_fouls = EXCLUDED.personal_fouls,
                fg_made = EXCLUDED.fg_made,
                fg_attempted = EXCLUDED.fg_attempted,
                fg_pct = EXCLUDED.fg_pct,
                three_made = EXCLUDED.three_made,
                three_attempted = EXCLUDED.three_attempted,
                three_pct = EXCLUDED.three_pct,
                ft_made = EXCLUDED.ft_made,
                ft_attempted = EXCLUDED.ft_attempted,
                ft_pct = EXCLUDED.ft_pct,
                plus_minus = EXCLUDED.plus_minus,
                game_status = EXCLUDED.game_status,
                game_status_text = EXCLUDED.game_status_text,
                recorded_at = NOW()
            `, [
              ps.game_id, ps.game_date, ps.player_name, ps.player_id,
              ps.team, ps.team_abbr, ps.is_home, ps.starter,
              ps.minutes, ps.points, ps.rebounds, ps.offensive_rebounds, ps.defensive_rebounds,
              ps.assists, ps.steals, ps.blocks, ps.turnovers, ps.personal_fouls,
              ps.fg_made, ps.fg_attempted, ps.fg_pct,
              ps.three_made, ps.three_attempted, ps.three_pct,
              ps.ft_made, ps.ft_attempted, ps.ft_pct,
              ps.plus_minus, ps.game_status, ps.game_status_text,
            ]);
            stored++;
          } catch (e) {
            if (!e.message.includes('duplicate')) {
              logger.warn(`[DATA-WORKER] Store player stats error: ${e.message}`);
            }
          }
        }
      } finally {
        client.release();
      }
    } catch (err) {
      logger.error(`[DATA-WORKER] Player stats storage failed: ${err.message}`);
    }

    return stored;
  }

  // ══════════════════════════════════════════
  //  TODAY'S GAMES — NBA.com CDN Scoreboard (free, no auth)
  // ══════════════════════════════════════════

  /**
   * Fetch today's NBA games from NBA.com CDN.
   * Returns game IDs that can be passed to fetchBoxScores().
   * Stores game IDs and statuses.
   */
  async fetchTodaysGames() {
    try {
      const resp = await fetch(NBA_CDN_SCOREBOARD, {
        signal: AbortSignal.timeout(15000),
        headers: NBA_CDN_HEADERS,
      });

      if (!resp.ok) {
        throw new Error(`NBA CDN Scoreboard ${resp.status}: ${await resp.text()}`);
      }

      const data = await resp.json();
      const scoreboard = data.scoreboard;
      if (!scoreboard) {
        throw new Error('No scoreboard data in response');
      }

      const games = [];
      for (const game of (scoreboard.games || [])) {
        const homeTeam = game.homeTeam || {};
        const awayTeam = game.awayTeam || {};

        games.push({
          game_id: game.gameId,
          game_code: game.gameCode || '',
          game_status: game.gameStatus || 0,
          game_status_text: game.gameStatusText || '',
          game_time_utc: game.gameTimeUTC || '',
          period: game.period || 0,
          game_clock: game.gameClock || '',
          home_team: `${homeTeam.teamCity || ''} ${homeTeam.teamName || ''}`.trim(),
          home_abbr: homeTeam.teamTricode || '',
          home_score: parseInt(homeTeam.score) || 0,
          away_team: `${awayTeam.teamCity || ''} ${awayTeam.teamName || ''}`.trim(),
          away_abbr: awayTeam.teamTricode || '',
          away_score: parseInt(awayTeam.score) || 0,
        });
      }

      this.stats.todaysGamesFetches++;

      const completed = games.filter(g => g.game_status === 3);
      const live = games.filter(g => g.game_status === 2);
      const scheduled = games.filter(g => g.game_status === 1);

      logger.info(`[DATA-WORKER] NBA CDN scoreboard: ${games.length} games (${completed.length} final, ${live.length} live, ${scheduled.length} scheduled)`);

      return {
        source: 'nba-cdn',
        date: scoreboard.gameDate || new Date().toISOString().slice(0, 10),
        total: games.length,
        completed: completed.length,
        live: live.length,
        scheduled: scheduled.length,
        games,
        gameIds: games.map(g => g.game_id),
      };
    } catch (err) {
      this.stats.errors++;
      this.stats.lastError = `todaysGames: ${err.message} @ ${new Date().toISOString()}`;
      logger.error(`[DATA-WORKER] NBA CDN scoreboard failed: ${err.message}`);
      return null;
    }
  }

  // ══════════════════════════════════════════
  //  BROWSER-BASED SCRAPING (Chromium headless)
  // ══════════════════════════════════════════

  async _getBrowser() {
    if (!browser) {
      try {
        browser = require('./browser');
        // Test if chromium is actually available
        await browser.getBrowser();
      } catch (err) {
        logger.warn(`[DATA-WORKER] Local browser not available, using Jina Reader: ${err.message}`);
        browser = null;
        return null;
      }
    }
    return browser;
  }

  /**
   * Fetch rendered HTML via Jina Reader API (free, no browser needed).
   * Falls back from local Chromium → Jina Reader → raw fetch.
   */
  async _fetchRendered(url, options = {}) {
    // Try local browser first
    const b = await this._getBrowser();
    if (b) {
      try {
        return await b.scrape(url, options);
      } catch (err) {
        logger.warn(`[DATA-WORKER] Local browser failed, falling back to Jina: ${err.message}`);
      }
    }

    // Fallback: Jina Reader API (renders JS, returns clean HTML/text)
    try {
      const jinaUrl = `https://r.jina.ai/${url}`;
      const headers = { 'Accept': 'text/html' };
      if (process.env.JINA_API_KEY) {
        headers['Authorization'] = `Bearer ${process.env.JINA_API_KEY}`;
      }
      const resp = await fetch(jinaUrl, {
        headers,
        signal: AbortSignal.timeout(options.timeout || 20000),
      });
      if (!resp.ok) throw new Error(`Jina ${resp.status}`);
      return await resp.text();
    } catch (err) {
      logger.warn(`[DATA-WORKER] Jina Reader failed for ${url}: ${err.message}`);
    }

    // Last resort: raw fetch (won't render JS)
    try {
      const resp = await fetch(url, {
        headers: { 'User-Agent': 'Mozilla/5.0' },
        signal: AbortSignal.timeout(options.timeout || 15000),
      });
      if (!resp.ok) throw new Error(`Raw fetch ${resp.status}`);
      return await resp.text();
    } catch (err) {
      logger.error(`[DATA-WORKER] All fetch methods failed for ${url}: ${err.message}`);
      return null;
    }
  }

  /**
   * Scrape RotoWire for today's NBA lineups (starting 5 + injury status).
   * Requires Chromium — page is JS-rendered.
   */
  async fetchLineups() {
    try {
      const html = await this._fetchRendered('https://www.rotowire.com/basketball/nba-lineups.php', {
        waitFor: '.lineup__main',
        timeout: 20000,
      });

      if (!html || typeof html !== 'string') {
        logger.warn('[DATA-WORKER] RotoWire returned no HTML');
        return null;
      }

      // Parse lineups from HTML — extract game cards
      const cheerio = require('cheerio');
      const $ = cheerio.load(html);
      const lineups = [];

      $('.lineup__main .lineup__matchup, .lineup').each((_, el) => {
        const teams = $(el).find('.lineup__team');
        if (teams.length < 2) return;

        const awayTeam = $(teams[0]).find('.lineup__abbr').text().trim();
        const homeTeam = $(teams[1]).find('.lineup__abbr').text().trim();
        const awayPlayers = [];
        const homePlayers = [];

        $(teams[0]).closest('.lineup').find('.lineup__player').each((i, p) => {
          awayPlayers.push({
            name: $(p).find('a').text().trim(),
            position: $(p).find('.lineup__pos').text().trim(),
            status: $(p).find('.lineup__inj').text().trim() || 'Active',
          });
        });

        $(teams[1]).closest('.lineup').find('.lineup__player').each((i, p) => {
          homePlayers.push({
            name: $(p).find('a').text().trim(),
            position: $(p).find('.lineup__pos').text().trim(),
            status: $(p).find('.lineup__inj').text().trim() || 'Active',
          });
        });

        if (awayTeam && homeTeam) {
          lineups.push({
            away_team: awayTeam,
            home_team: homeTeam,
            away_players: awayPlayers.slice(0, 8),
            home_players: homePlayers.slice(0, 8),
          });
        }
      });

      logger.info(`[DATA-WORKER] RotoWire lineups: ${lineups.length} games scraped`);

      // Store in Supabase
      if (lineups.length > 0 && this.infra?.pgPool) {
        await this._storeLineups(lineups);
      }

      return { source: 'rotowire', games: lineups.length, lineups };
    } catch (err) {
      this.stats.errors++;
      logger.error(`[DATA-WORKER] RotoWire lineups scrape failed: ${err.message}`);
      return null;
    }
  }

  async _storeLineups(lineups) {
    if (!this.infra?.pgPool) return;
    try {
      const client = await this.infra.pgPool.connect();
      try {
        await client.query('SET search_path TO public');
        await client.query(`
          CREATE TABLE IF NOT EXISTS nba_lineups (
            id SERIAL PRIMARY KEY,
            game_date DATE NOT NULL DEFAULT CURRENT_DATE,
            away_team TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_players JSONB,
            home_players JSONB,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(game_date, away_team, home_team)
          )
        `);

        for (const lu of lineups) {
          await client.query(`
            INSERT INTO nba_lineups (away_team, home_team, away_players, home_players)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (game_date, away_team, home_team) DO UPDATE SET
              away_players = EXCLUDED.away_players,
              home_players = EXCLUDED.home_players,
              recorded_at = NOW()
          `, [lu.away_team, lu.home_team, JSON.stringify(lu.away_players), JSON.stringify(lu.home_players)]);
        }
      } finally { client.release(); }
    } catch (err) {
      logger.error(`[DATA-WORKER] Lineups storage failed: ${err.message}`);
    }
  }

  /**
   * Scrape referee assignments for today's NBA games.
   * Source: official NBA or basketballinsiders.
   */
  async fetchReferees() {
    try {
      const html = await this._fetchRendered('https://official.nba.com/referee-assignments/', {
        waitFor: 'table',
        timeout: 20000,
      });

      if (!html || typeof html !== 'string') return null;

      const cheerio = require('cheerio');
      const $ = cheerio.load(html);
      const assignments = [];

      $('table tbody tr').each((_, row) => {
        const cells = $(row).find('td');
        if (cells.length < 4) return;

        assignments.push({
          game_date: new Date().toISOString().slice(0, 10),
          matchup: $(cells[0]).text().trim(),
          crew_chief: $(cells[1]).text().trim(),
          referee: $(cells[2]).text().trim(),
          umpire: $(cells[3]).text().trim(),
        });
      });

      logger.info(`[DATA-WORKER] Referee assignments: ${assignments.length} games`);

      if (assignments.length > 0 && this.infra?.pgPool) {
        await this._storeReferees(assignments);
      }

      return { source: 'nba-official', count: assignments.length, assignments };
    } catch (err) {
      this.stats.errors++;
      logger.error(`[DATA-WORKER] Referee scrape failed: ${err.message}`);
      return null;
    }
  }

  async _storeReferees(assignments) {
    if (!this.infra?.pgPool) return;
    try {
      const client = await this.infra.pgPool.connect();
      try {
        await client.query('SET search_path TO public');
        await client.query(`
          CREATE TABLE IF NOT EXISTS nba_referees (
            id SERIAL PRIMARY KEY,
            game_date DATE NOT NULL,
            matchup TEXT NOT NULL,
            crew_chief TEXT,
            referee TEXT,
            umpire TEXT,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(game_date, matchup)
          )
        `);

        for (const ref of assignments) {
          await client.query(`
            INSERT INTO nba_referees (game_date, matchup, crew_chief, referee, umpire)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (game_date, matchup) DO UPDATE SET
              crew_chief = EXCLUDED.crew_chief,
              referee = EXCLUDED.referee,
              umpire = EXCLUDED.umpire,
              recorded_at = NOW()
          `, [ref.game_date, ref.matchup, ref.crew_chief, ref.referee, ref.umpire]);
        }
      } finally { client.release(); }
    } catch (err) {
      logger.error(`[DATA-WORKER] Referees storage failed: ${err.message}`);
    }
  }

  /**
   * Scrape Basketball Reference for team advanced stats.
   * Gets: ORtg, DRtg, Pace, eFG%, TOV%, FTr, etc.
   */
  async fetchAdvancedStats() {
    try {
      const html = await this._fetchRendered('https://www.basketball-reference.com/leagues/NBA_2026.html', {
        waitFor: '#advanced-team',
        timeout: 25000,
      });

      if (!html || typeof html !== 'string') return null;

      const cheerio = require('cheerio');
      const $ = cheerio.load(html);
      const teams = [];

      $('#advanced-team tbody tr:not(.thead)').each((_, row) => {
        const cells = $(row).find('td');
        if (cells.length < 15) return;

        const teamLink = $(row).find('td[data-stat="team_name"] a');
        teams.push({
          team: teamLink.text().trim() || $(cells[0]).text().trim(),
          age: parseFloat($(row).find('td[data-stat="age"]').text()) || 0,
          wins: parseInt($(row).find('td[data-stat="wins"]').text()) || 0,
          losses: parseInt($(row).find('td[data-stat="losses"]').text()) || 0,
          pace: parseFloat($(row).find('td[data-stat="pace"]').text()) || 0,
          off_rtg: parseFloat($(row).find('td[data-stat="off_rtg"]').text()) || 0,
          def_rtg: parseFloat($(row).find('td[data-stat="def_rtg"]').text()) || 0,
          net_rtg: parseFloat($(row).find('td[data-stat="net_rtg"]').text()) || 0,
          efg_pct: parseFloat($(row).find('td[data-stat="efg_pct"]').text()) || 0,
          tov_pct: parseFloat($(row).find('td[data-stat="tov_pct"]').text()) || 0,
          orb_pct: parseFloat($(row).find('td[data-stat="orb_pct"]').text()) || 0,
          ft_rate: parseFloat($(row).find('td[data-stat="ft_rate"]').text()) || 0,
          opp_efg_pct: parseFloat($(row).find('td[data-stat="opp_efg_pct"]').text()) || 0,
          opp_tov_pct: parseFloat($(row).find('td[data-stat="opp_tov_pct"]').text()) || 0,
          updated_at: new Date().toISOString(),
        });
      });

      logger.info(`[DATA-WORKER] Basketball Reference advanced stats: ${teams.length} teams`);

      if (teams.length > 0 && this.infra?.pgPool) {
        await this._storeAdvancedStats(teams);
      }

      return { source: 'basketball-reference', teams: teams.length, data: teams };
    } catch (err) {
      this.stats.errors++;
      logger.error(`[DATA-WORKER] Basketball Reference scrape failed: ${err.message}`);
      return null;
    }
  }

  async _storeAdvancedStats(teams) {
    if (!this.infra?.pgPool) return;
    try {
      const client = await this.infra.pgPool.connect();
      try {
        await client.query('SET search_path TO public');
        await client.query(`
          CREATE TABLE IF NOT EXISTS nba_advanced_stats (
            id SERIAL PRIMARY KEY,
            team TEXT NOT NULL,
            season TEXT NOT NULL DEFAULT '2025-26',
            wins INT, losses INT,
            pace REAL, off_rtg REAL, def_rtg REAL, net_rtg REAL,
            efg_pct REAL, tov_pct REAL, orb_pct REAL, ft_rate REAL,
            opp_efg_pct REAL, opp_tov_pct REAL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(team, season)
          )
        `);

        for (const t of teams) {
          await client.query(`
            INSERT INTO nba_advanced_stats (team, wins, losses, pace, off_rtg, def_rtg, net_rtg, efg_pct, tov_pct, orb_pct, ft_rate, opp_efg_pct, opp_tov_pct, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            ON CONFLICT (team, season) DO UPDATE SET
              wins=EXCLUDED.wins, losses=EXCLUDED.losses, pace=EXCLUDED.pace,
              off_rtg=EXCLUDED.off_rtg, def_rtg=EXCLUDED.def_rtg, net_rtg=EXCLUDED.net_rtg,
              efg_pct=EXCLUDED.efg_pct, tov_pct=EXCLUDED.tov_pct, orb_pct=EXCLUDED.orb_pct,
              ft_rate=EXCLUDED.ft_rate, opp_efg_pct=EXCLUDED.opp_efg_pct, opp_tov_pct=EXCLUDED.opp_tov_pct,
              updated_at=EXCLUDED.updated_at
          `, [t.team, t.wins, t.losses, t.pace, t.off_rtg, t.def_rtg, t.net_rtg, t.efg_pct, t.tov_pct, t.orb_pct, t.ft_rate, t.opp_efg_pct, t.opp_tov_pct, t.updated_at]);
        }
      } finally { client.release(); }
    } catch (err) {
      logger.error(`[DATA-WORKER] Advanced stats storage failed: ${err.message}`);
    }
  }

  /**
   * Scrape generic web page — for RGWA or any agent to fetch arbitrary data.
   * @param {string} url — URL to scrape
   * @param {object} options — { waitFor, timeout, extractText }
   */
  async scrapePage(url, options = {}) {
    try {
      const result = await this._fetchRendered(url, {
        waitFor: options.waitFor,
        timeout: options.timeout || 20000,
      });

      logger.info(`[DATA-WORKER] Scraped: ${url} (${typeof result === 'string' ? result.length : 0} chars)`);
      return { source: url, content: result };
    } catch (err) {
      logger.error(`[DATA-WORKER] Scrape failed (${url}): ${err.message}`);
      return null;
    }
  }

  // ══════════════════════════════════════════
  //  BROWSER AUTOMATION — Navigate, fill forms, click
  // ══════════════════════════════════════════

  /**
   * Execute browser actions via Jina Reader with instruction prompts.
   * Jina Reader supports a special mode where you can ask it to interact.
   * For complex form filling, falls back to the Code Agent (which can
   * generate automation scripts).
   *
   * @param {string} url — Target URL
   * @param {Array} actions — [{type: 'fill', selector: '#email', value: 'test@test.com'},
   *                           {type: 'click', selector: '#submit'}]
   * @returns {object} — { success, content, error }
   */
  async browserAction(url, actions = []) {
    // Strategy 1: For simple reads with JS rendering, use Jina
    if (actions.length === 0) {
      const content = await this._fetchRendered(url);
      return { success: !!content, content, method: 'jina-reader' };
    }

    // Strategy 2: For form filling, use VM SSH + curl/python
    // This works because our VM has a real browser environment
    if (this.infra?.vmBridge) {
      try {
        const actionsJson = JSON.stringify(actions).replace(/'/g, "\\'");
        // Generate a Python script that uses requests + beautifulsoup for simple forms
        // or selenium for complex JS forms
        const script = `
import json, sys
try:
    import requests
    from urllib.parse import urljoin
    s = requests.Session()
    s.headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'
    resp = s.get('${url}', timeout=15)
    actions = json.loads('${actionsJson}')
    # For POST-based forms, extract form action and submit
    form_data = {}
    for a in actions:
        if a.get('type') == 'fill':
            name = a.get('name') or a.get('selector', '').replace('#', '')
            form_data[name] = a.get('value', '')
    if form_data:
        resp = s.post('${url}', data=form_data, timeout=15)
    print(json.dumps({'success': True, 'status': resp.status_code, 'length': len(resp.text), 'content': resp.text[:3000]}))
except Exception as e:
    print(json.dumps({'success': False, 'error': str(e)}))
`;
        const result = await this.infra.vmBridge.exec(`python3 -c "${script.replace(/"/g, '\\"').replace(/\n/g, '\\n')}"`);
        if (result.stdout) {
          const parsed = JSON.parse(result.stdout.trim());
          return { ...parsed, method: 'vm-python' };
        }
        return { success: false, error: result.stderr || 'No output', method: 'vm-python' };
      } catch (err) {
        logger.error(`[DATA-WORKER] VM browser action failed: ${err.message}`);
      }
    }

    // Strategy 3: Fallback — describe what we need and let Code Agent handle it
    return {
      success: false,
      error: 'Browser form filling requires VM SSH bridge (not available)',
      suggestion: 'Use !code to create an automation script',
      method: 'none',
    };
  }

  // ══════════════════════════════════════════
  //  STATUS
  // ══════════════════════════════════════════

  getStatus() {
    return {
      lastOddsFetch: this.lastOddsFetch,
      lastScoresFetch: this.lastScoresFetch,
      lastInjuriesFetch: this.lastInjuriesFetch,
      lastBoxScoresFetch: this.lastBoxScoresFetch,
      oddsApiKey: this.oddsApiKey ? 'configured' : 'MISSING',
      supabase: this.infra?.pgPool ? 'connected' : 'not connected',
      stats: this.stats,
      recentOdds: this.oddsHistory.slice(-5),
      recentMovements: this.lineMovements.slice(-10),
    };
  }
}

module.exports = DataWorker;
