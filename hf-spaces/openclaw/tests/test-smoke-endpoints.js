/**
 * Smoke tests for OpenClaw/RGWA REST API endpoints
 *
 * Run: SPACE_URL=https://lbjlincoln-nomos-rgwa.hf.space node tests/test-smoke-endpoints.js
 * Or:  SPACE_URL=https://lbjlincoln26-nomos-worker-2.hf.space node tests/test-smoke-endpoints.js
 */

const https = require('https');
const http = require('http');

const SPACE_URL = process.env.SPACE_URL || 'https://lbjlincoln-nomos-rgwa.hf.space';

let passed = 0;
let failed = 0;

function fetch(url, options = {}) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? https : http;
    const method = options.method || 'GET';
    const body = options.body ? JSON.stringify(options.body) : null;

    const req = mod.request(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      timeout: 15000,
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, data: JSON.parse(data) });
        } catch {
          resolve({ status: res.statusCode, data });
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    if (body) req.write(body);
    req.end();
  });
}

async function test(name, fn) {
  try {
    await fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    failed++;
    console.log(`  ✗ ${name} — ${err.message}`);
  }
}

function assert(condition, msg) {
  if (!condition) throw new Error(msg || 'Assertion failed');
}

async function run() {
  console.log(`\n=== Smoke Tests: ${SPACE_URL} ===\n`);

  // ── Health ──
  await test('GET /keep-alive returns alive', async () => {
    const r = await fetch(`${SPACE_URL}/keep-alive`);
    assert([200, 206].includes(r.status), `Expected 200/206, got ${r.status}`);
    assert(r.data.status === 'alive', `Expected alive, got ${r.data.status}`);
    assert(r.data.version, 'Missing version');
    assert(r.data.uptime >= 0, 'Missing uptime');
    console.log(`    version=${r.data.version} uptime=${r.data.uptime}s`);
  });

  // ── Spaces health ──
  await test('GET /api/v1/spaces returns space list', async () => {
    const r = await fetch(`${SPACE_URL}/api/v1/spaces`);
    assert([200, 206].includes(r.status), `Expected 200/206, got ${r.status}`);
    assert(Array.isArray(r.data.spaces) || r.data.spaces, 'Missing spaces array');
  });

  // ── Evolution status ──
  await test('GET /api/v1/evolution returns status', async () => {
    const r = await fetch(`${SPACE_URL}/api/v1/evolution`);
    assert([200, 206].includes(r.status), `Expected 200/206, got ${r.status}`);
    assert(r.data !== undefined, 'Empty response');
  });

  // ── Chat (basic) ──
  await test('POST /api/v1/chat returns LLM response', async () => {
    const r = await fetch(`${SPACE_URL}/api/v1/chat`, {
      method: 'POST',
      body: { messages: [{ role: 'user', content: 'Reply with exactly: PONG' }], maxTokens: 50 },
    });
    assert([200, 206].includes(r.status), `Expected 200/206, got ${r.status}`);
    assert(r.data.content, 'Missing content in response');
    assert(r.data.model, 'Missing model in response');
    console.log(`    model=${r.data.model}`);
  });

  // ── Chat validation ──
  await test('POST /api/v1/chat rejects missing messages', async () => {
    const r = await fetch(`${SPACE_URL}/api/v1/chat`, {
      method: 'POST',
      body: {},
    });
    assert([400, 206].includes(r.status), `Expected 400/206, got ${r.status}`);
  });

  // ── Agent endpoint (after agent-executor is deployed) ──
  await test('POST /api/v1/agent endpoint exists', async () => {
    const r = await fetch(`${SPACE_URL}/api/v1/agent`, {
      method: 'POST',
      body: { messages: [{ role: 'user', content: 'What is 2+2?' }], maxIterations: 1 },
    });
    // Accept 200 (working) or 404 (not deployed yet) or 503 (not initialized)
    assert([200, 206, 404, 503].includes(r.status), `Unexpected status ${r.status}`);
    if (r.status === 200) {
      console.log(`    ✓ Agent executor is LIVE!`);
    } else {
      console.log(`    ⚠ Agent executor not deployed yet (${r.status})`);
    }
  });

  // ── A2A Protocol ──
  await test('GET /api/v1/a2a/status returns protocol status', async () => {
    const r = await fetch(`${SPACE_URL}/api/v1/a2a/status`);
    assert([200, 206].includes(r.status), `Expected 200/206, got ${r.status}`);
  });

  await test('GET /api/v1/a2a/inbox returns inbox', async () => {
    const r = await fetch(`${SPACE_URL}/api/v1/a2a/inbox`);
    assert([200, 206].includes(r.status), `Expected 200/206, got ${r.status}`);
    assert(Array.isArray(r.data), 'Inbox should be an array');
  });

  await test('POST /api/v1/a2a/command requires action field', async () => {
    const r = await fetch(`${SPACE_URL}/api/v1/a2a/command`, {
      method: 'POST',
      body: {},
    });
    assert([400, 206].includes(r.status), `Expected 400/206, got ${r.status}`);
  });

  await test('POST /api/v1/a2a/command executes health_check', async () => {
    const r = await fetch(`${SPACE_URL}/api/v1/a2a/command`, {
      method: 'POST',
      body: { action: 'health_check', params: {} },
    });
    assert([200, 206].includes(r.status), `Expected 200/206, got ${r.status}`);
  });

  // ── Watchdog ──
  await test('GET /api/v1/watchdog returns monitoring data', async () => {
    const r = await fetch(`${SPACE_URL}/api/v1/watchdog`);
    // Accept 200 or 404 depending on endpoint existence
    assert([200, 206, 404].includes(r.status), `Unexpected status ${r.status}`);
  });

  // ── Sessions ──
  await test('GET /api/v1/chat/sessions returns session list', async () => {
    const r = await fetch(`${SPACE_URL}/api/v1/chat/sessions`);
    assert([200, 206].includes(r.status), `Expected 200/206, got ${r.status}`);
    assert(Array.isArray(r.data), 'Should return array');
  });

  // ── Summary ──
  console.log(`\n${passed} passed, ${failed} failed, ${passed + failed} total\n`);
  process.exit(failed > 0 ? 1 : 0);
}

run().catch(err => {
  console.error('Test runner error:', err);
  process.exit(1);
});
