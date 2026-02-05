#!/usr/bin/env node

/**
 * Runner for Multi-RAG Sub-Agents via Claude Code CLI
 *
 * Usage:
 *   node run-agent.mjs <agent-name> [--dry-run] [--verbose]
 *   node run-agent.mjs orchestrator
 *   node run-agent.mjs workflow-analyzer
 *   node run-agent.mjs all
 *
 * Each agent is launched as a Claude Code subprocess with:
 * - The correct model (haiku vs opus-4.5)
 * - The agent's system prompt from its YAML definition
 * - Access to MCP servers via --mcp-config
 * - The correct input files
 */

import { readFileSync, existsSync, writeFileSync, mkdirSync } from "fs";
import { execSync, spawn } from "child_process";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");
const AGENTS_DIR = join(__dirname, "..", "agents");
const CONFIG_DIR = join(__dirname, "..", "config");
const MCP_CONFIG = join(CONFIG_DIR, "claude-mcp-config.json");
const OUTPUTS_DIR = join(ROOT, "outputs");

// Simple YAML parser for our agent files (no external deps needed)
function parseYaml(content) {
  const result = {};
  let currentKey = null;
  let multilineValue = "";
  let inMultiline = false;
  let indent = 0;

  for (const line of content.split("\n")) {
    if (line.trim().startsWith("#") || line.trim() === "") continue;

    if (inMultiline) {
      const lineIndent = line.search(/\S/);
      if (lineIndent > indent) {
        multilineValue += line.trim() + "\n";
        continue;
      } else {
        result[currentKey] = multilineValue.trim();
        inMultiline = false;
      }
    }

    const match = line.match(/^(\w[\w-]*):\s*(.*)/);
    if (match) {
      const [, key, value] = match;
      if (value === "|") {
        currentKey = key;
        multilineValue = "";
        inMultiline = true;
        indent = line.search(/\S/);
      } else if (value) {
        result[key] = value.replace(/^["']|["']$/g, "");
      }
    }
  }

  if (inMultiline && currentKey) {
    result[currentKey] = multilineValue.trim();
  }

  return result;
}

// Load agent definition
function loadAgent(agentName) {
  const yamlPath = join(AGENTS_DIR, `${agentName}.yaml`);
  if (!existsSync(yamlPath)) {
    console.error(`Agent not found: ${yamlPath}`);
    process.exit(1);
  }
  const content = readFileSync(yamlPath, "utf-8");
  return { ...parseYaml(content), _raw: content };
}

// Map agent model to Claude CLI model flag
function getModelFlag(model) {
  if (!model) return "";
  const m = model.toLowerCase().replace(/[^a-z0-9.-]/g, "");
  if (m.includes("haiku")) return "--model haiku";
  if (m.includes("opus")) return "--model opus";
  if (m.includes("sonnet")) return "--model sonnet";
  return "";
}

// Build the prompt for an agent
function buildPrompt(agent, agentName) {
  const systemPrompt = agent.system_prompt || agent.description || "";

  // List available workflow files
  const workflowFiles = execSync(`ls "${ROOT}"/TEST*.json "${ROOT}"/V10*.json 2>/dev/null || true`, {
    encoding: "utf-8",
  })
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((f) => f.split("/").pop());

  const prompt = `
You are the ${agentName} agent in a Multi-RAG orchestrator pipeline.

=== SYSTEM PROMPT ===
${systemPrompt}

=== AVAILABLE WORKFLOWS ===
${workflowFiles.join("\n")}

=== AVAILABLE MCP TOOLS ===
You have access to MCP servers for: Pinecone, Neo4j, Supabase, N8N Enhanced.
Use these tools to interact with the databases and n8n instance.

=== OUTPUT DIRECTORY ===
Write all outputs to: ${OUTPUTS_DIR}/

=== INSTRUCTIONS ===
Execute your role as defined above. Read the workflow JSON files, analyze them,
and produce the outputs specified in your agent definition.
When done, write a summary to ${OUTPUTS_DIR}/${agentName}-summary.json
`.trim();

  return prompt;
}

// Run a single agent
async function runAgent(agentName, options = {}) {
  console.log(`\n${"=".repeat(60)}`);
  console.log(`  Launching agent: ${agentName}`);
  console.log(`${"=".repeat(60)}\n`);

  const agent = loadAgent(agentName);
  const model = getModelFlag(agent.model);
  const prompt = buildPrompt(agent, agentName);

  // Ensure output directory exists
  if (!existsSync(OUTPUTS_DIR)) {
    mkdirSync(OUTPUTS_DIR, { recursive: true });
  }

  if (options.dryRun) {
    console.log("DRY RUN - Would execute:");
    console.log(`  Model: ${agent.model || "default"}`);
    console.log(`  MCP Config: ${MCP_CONFIG}`);
    console.log(`  Prompt length: ${prompt.length} chars`);
    console.log(`  System prompt preview:\n    ${(agent.system_prompt || "").substring(0, 200)}...`);
    return { status: "dry-run", agent: agentName };
  }

  // Build claude CLI command
  const args = [
    "--print",
    "--mcp-config",
    MCP_CONFIG,
    ...(model ? model.split(" ") : []),
    "--max-turns",
    "50",
    "-p",
    prompt,
  ];

  console.log(`Running: claude ${args.join(" ").substring(0, 200)}...`);
  console.log(`Model: ${agent.model || "default"}`);
  console.log("");

  return new Promise((resolve, reject) => {
    const proc = spawn("claude", args, {
      cwd: ROOT,
      stdio: options.verbose ? "inherit" : ["pipe", "pipe", "pipe"],
      env: { ...process.env },
    });

    let stdout = "";
    let stderr = "";

    if (!options.verbose) {
      proc.stdout?.on("data", (data) => {
        stdout += data.toString();
      });
      proc.stderr?.on("data", (data) => {
        stderr += data.toString();
      });
    }

    proc.on("close", (code) => {
      const result = {
        agent: agentName,
        model: agent.model,
        exitCode: code,
        stdout: stdout.substring(0, 5000),
        timestamp: new Date().toISOString(),
      };

      // Save result
      const resultPath = join(OUTPUTS_DIR, `${agentName}-result.json`);
      writeFileSync(resultPath, JSON.stringify(result, null, 2));

      if (code === 0) {
        console.log(`Agent ${agentName} completed successfully.`);
        resolve(result);
      } else {
        console.error(`Agent ${agentName} failed with code ${code}`);
        if (stderr) console.error(stderr.substring(0, 1000));
        reject(new Error(`Agent ${agentName} failed: exit code ${code}`));
      }
    });
  });
}

// Run the full pipeline
async function runPipeline(options = {}) {
  const sequence = [
    "workflow-analyzer",
    "db-reader",
    "patch-writer",
    "patch-applier",
    "n8n-tester",
  ];

  console.log("Starting Multi-RAG Pipeline");
  console.log(`Agents to run: ${sequence.join(" -> ")}\n`);

  const results = [];

  for (const agentName of sequence) {
    try {
      const result = await runAgent(agentName, options);
      results.push(result);
    } catch (error) {
      console.error(`Pipeline stopped at ${agentName}: ${error.message}`);
      results.push({ agent: agentName, status: "failed", error: error.message });

      // Check if this agent is required
      const agent = loadAgent(agentName);
      if (agent._raw.includes("required: true")) {
        console.error("Required agent failed. Stopping pipeline.");
        break;
      }
    }
  }

  // Save pipeline report
  const report = {
    pipeline: "multi-rag-orchestrator",
    timestamp: new Date().toISOString(),
    results,
    summary: {
      total: results.length,
      success: results.filter((r) => r.exitCode === 0).length,
      failed: results.filter((r) => r.status === "failed").length,
    },
  };

  const reportPath = join(OUTPUTS_DIR, "pipeline-report.json");
  if (!existsSync(OUTPUTS_DIR)) mkdirSync(OUTPUTS_DIR, { recursive: true });
  writeFileSync(reportPath, JSON.stringify(report, null, 2));

  console.log(`\nPipeline report saved to: ${reportPath}`);
  return report;
}

// CLI
const args = process.argv.slice(2);
const agentName = args[0];
const dryRun = args.includes("--dry-run");
const verbose = args.includes("--verbose");

if (!agentName) {
  console.log(`
Usage: node run-agent.mjs <agent-name> [--dry-run] [--verbose]

Available agents:
  orchestrator       - Pipeline coordinator (Haiku)
  workflow-analyzer  - Workflow analysis (Opus 4.5)
  db-reader          - Database extraction (Opus 4.5)
  patch-writer       - Patch generation (Opus 4.5)
  patch-applier      - Patch application (Haiku)
  n8n-tester         - Workflow testing (Opus 4.5)
  all                - Run full pipeline sequentially

Options:
  --dry-run   Show what would be executed without running
  --verbose   Show full agent output in terminal
  `);
  process.exit(0);
}

if (agentName === "all" || agentName === "orchestrator") {
  runPipeline({ dryRun, verbose }).catch(console.error);
} else {
  runAgent(agentName, { dryRun, verbose }).catch(console.error);
}
