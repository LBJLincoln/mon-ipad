/**
 * NBA Quant Agent Extension for OpenClaw
 *
 * Provides NBA-specific tools for the agentic loop:
 *   - nba_evolution_status: Check genetic evolution progress on S10/S11
 *   - nba_games_today: Get today's NBA schedule
 *   - nba_predictions: Get current model predictions
 */

const S10_URL = 'https://lbjlincoln-nomos-nba-quant.hf.space';
const S11_URL = 'https://lbjlincoln-nomos-nba-quant-2.hf.space';
const ESPN_URL = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard';

function text(t) {
  return { content: [{ type: 'text', text: t }] };
}

export default function register(api) {
  const log = api.logger || console;

  // ── Tool: Evolution Status ──
  if (api.registerTool) {
    api.registerTool({
      name: 'nba_evolution_status',
      description: 'Check genetic algorithm evolution status on NBA Quant HF Spaces (S10 primary, S11 secondary)',
      label: 'NBA Evolution',
      parameters: {
        type: 'object',
        properties: {
          space: {
            type: 'string',
            enum: ['s10', 's11', 'both'],
            description: 'Which space to check',
            default: 'both',
          },
        },
      },
      execute: async (_toolCallId, params) => {
        const space = params.space || 'both';
        const results = [];

        const fetchStatus = async (url, name) => {
          try {
            const resp = await fetch(`${url}/api/status`, { signal: AbortSignal.timeout(10000) });
            const data = await resp.json();
            return `**${name}**: ${data.status} | Brier: ${data.best_brier} | Gen: ${data.generation} | Pop: ${data.pop_size} | Features: ${data.feature_candidates}`;
          } catch (e) {
            return `**${name}**: OFFLINE (${e.message})`;
          }
        };

        if (space === 's10' || space === 'both') results.push(await fetchStatus(S10_URL, 'S10'));
        if (space === 's11' || space === 'both') results.push(await fetchStatus(S11_URL, 'S11'));

        return text(results.join('\n'));
      },
    });

    // ── Tool: NBA Games Today ──
    api.registerTool({
      name: 'nba_games_today',
      description: 'Get today\'s NBA game schedule from ESPN',
      label: 'NBA Games',
      parameters: { type: 'object', properties: {} },
      execute: async () => {
        try {
          const resp = await fetch(ESPN_URL, { signal: AbortSignal.timeout(10000) });
          const data = await resp.json();
          const events = data.events || [];
          if (events.length === 0) return text('No NBA games scheduled today.');

          const lines = events.map(e => {
            const comp = e.competitions?.[0];
            const teams = comp?.competitors || [];
            const home = teams.find(t => t.homeAway === 'home');
            const away = teams.find(t => t.homeAway === 'away');
            const status = comp?.status?.type?.shortDetail || 'Scheduled';
            return `${away?.team?.displayName || '?'} @ ${home?.team?.displayName || '?'} — ${status}`;
          });

          return text(`**NBA Games Today (${events.length}):**\n${lines.join('\n')}`);
        } catch (e) {
          return text(`Error fetching games: ${e.message}`);
        }
      },
    });

    // ── Tool: Send Command to Evolution ──
    api.registerTool({
      name: 'nba_evolution_command',
      description: 'Send a command to the NBA evolution engine (boost mutation, expand population, etc.)',
      label: 'Evolution Command',
      parameters: {
        type: 'object',
        properties: {
          space: { type: 'string', enum: ['s10', 's11'], default: 's10' },
          command: { type: 'string', description: 'Command to send (e.g., boost_mutation, expand_pop, reset_stagnation)' },
          value: { type: 'number', description: 'Optional numeric value for the command' },
        },
        required: ['command'],
      },
      execute: async (_toolCallId, params) => {
        const url = params.space === 's11' ? S11_URL : S10_URL;
        try {
          const body = { command: params.command };
          if (params.value !== undefined) body.value = params.value;
          const resp = await fetch(`${url}/api/command`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal: AbortSignal.timeout(15000),
          });
          const data = await resp.json();
          return text(JSON.stringify(data, null, 2));
        } catch (e) {
          return text(`Command failed: ${e.message}`);
        }
      },
    });

    log.info('[NBA-AGENT] Registered 3 tools: nba_evolution_status, nba_games_today, nba_evolution_command');
  }
}
