/**
 * Tests for RuleEngine — Deterministic action engine
 *
 * Run: node tests/test-rule-engine.js
 */

const assert = require('assert');

// Mock callS10 that records calls
function createMockCallS10() {
  const calls = [];
  const fn = async (endpoint, params) => {
    calls.push({ endpoint, params });
    return { ok: true };
  };
  fn.calls = calls;
  return fn;
}

// Import RuleEngine (adjust path since we run from openclaw/)
const RuleEngine = require('../lib/rule-engine');

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    failed++;
    console.log(`  ✗ ${name}`);
    console.log(`    ${err.message}`);
  }
}

async function testAsync(name, fn) {
  try {
    await fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    failed++;
    console.log(`  ✗ ${name}`);
    console.log(`    ${err.message}`);
  }
}

async function run() {
  console.log('\n=== RuleEngine Tests ===\n');

  // ── Constructor ──
  test('creates with correct rule count', () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    assert.strictEqual(engine.rules.length, 7);
    assert.strictEqual(engine.totalExecutions, 0);
  });

  // ── Stagnation rule ──
  await testAsync('triggers diversify on stagnation >= 3', async () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const state = { stagnation: 4, mutationRate: 0.08 };
    const actions = await engine.evaluate(state);
    assert.ok(actions.length > 0, 'Should trigger at least one action');
    assert.ok(actions.some(a => a.ruleId === 'stagnation_diversify'));
    assert.ok(callS10.calls.some(c => c.endpoint === '/api/config'));
  });

  await testAsync('triggers diversify command on stagnation >= 6', async () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const state = { stagnation: 7, mutationRate: 0.08 };
    await engine.evaluate(state);
    assert.ok(callS10.calls.some(c => c.endpoint === '/api/command' && c.params.command === 'diversify'));
  });

  await testAsync('does NOT trigger on stagnation < 3', async () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const state = { stagnation: 2, mutationRate: 0.10 };
    const actions = await engine.evaluate(state);
    assert.ok(!actions.some(a => a.ruleId === 'stagnation_diversify'));
  });

  // ── Critical stagnation ──
  await testAsync('triggers full reset on stagnation >= 10', async () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const state = { stagnation: 11, mutationRate: 0.10 };
    const actions = await engine.evaluate(state);
    assert.ok(actions.some(a => a.ruleId === 'critical_stagnation_reset'));
    assert.ok(callS10.calls.some(c => c.endpoint === '/api/reset'));
  });

  // ── Mutation floor ──
  await testAsync('bumps mutation when too low', async () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const state = { stagnation: 0, mutationRate: 0.02 };
    const actions = await engine.evaluate(state);
    assert.ok(actions.some(a => a.ruleId === 'mutation_floor'));
    const configCall = callS10.calls.find(c => c.params?.mutation_rate === 0.08);
    assert.ok(configCall, 'Should bump mutation to 0.08');
  });

  await testAsync('does NOT bump mutation when already adequate', async () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const state = { stagnation: 0, mutationRate: 0.10 };
    const actions = await engine.evaluate(state);
    assert.ok(!actions.some(a => a.ruleId === 'mutation_floor'));
  });

  // ── Population expand ──
  await testAsync('expands population when too small', async () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const state = { stagnation: 0, mutationRate: 0.10, population: 40 };
    const actions = await engine.evaluate(state);
    assert.ok(actions.some(a => a.ruleId === 'population_expand'));
  });

  await testAsync('does NOT expand when population adequate', async () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const state = { stagnation: 0, mutationRate: 0.10, population: 150 };
    const actions = await engine.evaluate(state);
    assert.ok(!actions.some(a => a.ruleId === 'population_expand'));
  });

  // ── Features expand ──
  await testAsync('expands features when too few', async () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const state = { stagnation: 0, mutationRate: 0.10, population: 100, features: 30 };
    const actions = await engine.evaluate(state);
    assert.ok(actions.some(a => a.ruleId === 'features_expand'));
  });

  // ── Brier degrading ──
  await testAsync('reacts to Brier degradation', async () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const state = { stagnation: 0, mutationRate: 0.08, population: 100, features: 100, brierTrend: 0.005 };
    const actions = await engine.evaluate(state);
    assert.ok(actions.some(a => a.ruleId === 'brier_degrading'));
  });

  // ── Cooldown ──
  await testAsync('respects cooldown — does NOT re-trigger immediately', async () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const state = { stagnation: 5, mutationRate: 0.08 };

    const actions1 = await engine.evaluate(state);
    assert.ok(actions1.length > 0);

    // Immediately re-evaluate — should be blocked by cooldown
    const actions2 = await engine.evaluate(state);
    const stagnationActions = actions2.filter(a => a.ruleId === 'stagnation_diversify');
    assert.strictEqual(stagnationActions.length, 0, 'Should be blocked by cooldown');
  });

  // ── LLM failure tracking ──
  test('tracks LLM failures and takes over after 2', () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });

    assert.strictEqual(engine.shouldTakeOver(), false);
    engine.recordLLMFailure();
    assert.strictEqual(engine.shouldTakeOver(), false);
    engine.recordLLMFailure();
    assert.strictEqual(engine.shouldTakeOver(), true);
  });

  test('resets LLM failure count', () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    engine.recordLLMFailure();
    engine.recordLLMFailure();
    assert.strictEqual(engine.shouldTakeOver(), true);
    engine.resetLLMFailures();
    assert.strictEqual(engine.shouldTakeOver(), false);
  });

  // ── Status ──
  test('returns correct status', () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const status = engine.getStatus();
    assert.strictEqual(status.rulesCount, 7);
    assert.strictEqual(status.totalExecutions, 0);
    assert.strictEqual(status.takingOver, false);
    assert.ok(Array.isArray(status.recentActions));
  });

  // ── Null state ──
  await testAsync('handles null/undefined state gracefully', async () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const actions = await engine.evaluate(null);
    assert.deepStrictEqual(actions, []);
  });

  await testAsync('handles empty state object', async () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const actions = await engine.evaluate({});
    assert.deepStrictEqual(actions, []);
  });

  // ── Mutation cap ──
  await testAsync('caps mutation rate at 0.22', async () => {
    const callS10 = createMockCallS10();
    const engine = new RuleEngine({ callS10 });
    const state = { stagnation: 5, mutationRate: 0.20 };
    await engine.evaluate(state);
    const configCalls = callS10.calls.filter(c => c.endpoint === '/api/config' && c.params.mutation_rate);
    if (configCalls.length > 0) {
      assert.ok(configCalls[0].params.mutation_rate <= 0.22, `Mutation should cap at 0.22, got ${configCalls[0].params.mutation_rate}`);
    }
  });

  // ── Summary ──
  console.log(`\n${passed} passed, ${failed} failed, ${passed + failed} total\n`);
  process.exit(failed > 0 ? 1 : 0);
}

run().catch(err => {
  console.error('Test runner error:', err);
  process.exit(1);
});
