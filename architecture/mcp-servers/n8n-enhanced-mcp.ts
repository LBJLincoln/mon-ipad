/**
 * MCP Server for N8N - ENHANCED VERSION
 * URL: https://amoret.app.n8n.cloud/
 *
 * Extensions beyond standard API:
 * - Read execution logs per node
 * - Patch individual nodes
 * - Validate workflows without import
 * - Run test cases with assertions
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const N8N_HOST = process.env.N8N_HOST || "https://amoret.app.n8n.cloud";
const N8N_API_KEY = process.env.N8N_API_KEY;

if (!N8N_API_KEY) {
  throw new Error("N8N_API_KEY environment variable is required");
}

const server = new Server(
  { name: "n8n-enhanced-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// Helper for N8N API calls
async function n8nRequest(
  endpoint: string,
  method: string = "GET",
  body?: object
): Promise<any> {
  const url = `${N8N_HOST}/api/v1${endpoint}`;

  const response = await fetch(url, {
    method,
    headers: {
      "X-N8N-API-KEY": N8N_API_KEY!,
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`N8N API error: ${response.status} - ${errorText}`);
  }

  return response.json();
}

// Parse workflow to index nodes
function indexWorkflowNodes(workflow: any): Map<string, any> {
  const nodeMap = new Map();
  if (workflow.nodes) {
    workflow.nodes.forEach((node: any, index: number) => {
      nodeMap.set(node.id, { node, index });
      nodeMap.set(node.name, { node, index });
    });
  }
  return nodeMap;
}

// Validate workflow structure
function validateWorkflowStructure(workflow: any): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  // Required fields
  if (!workflow.name) errors.push("Missing workflow name");
  if (!workflow.nodes || !Array.isArray(workflow.nodes)) {
    errors.push("Missing or invalid nodes array");
    return { valid: false, errors };
  }

  // Check node structure
  const nodeIds = new Set<string>();
  const nodeNames = new Set<string>();

  workflow.nodes.forEach((node: any, index: number) => {
    if (!node.id) errors.push(`Node at index ${index} missing id`);
    if (!node.name) errors.push(`Node at index ${index} missing name`);
    if (!node.type) errors.push(`Node at index ${index} missing type`);

    if (node.id && nodeIds.has(node.id)) {
      errors.push(`Duplicate node id: ${node.id}`);
    }
    nodeIds.add(node.id);

    if (node.name && nodeNames.has(node.name)) {
      errors.push(`Duplicate node name: ${node.name}`);
    }
    nodeNames.add(node.name);
  });

  // Check connections
  if (workflow.connections) {
    for (const [sourceName, outputs] of Object.entries(workflow.connections)) {
      if (!nodeNames.has(sourceName)) {
        errors.push(`Connection references non-existent node: ${sourceName}`);
      }

      if (Array.isArray(outputs)) {
        for (const outputGroup of outputs) {
          if (Array.isArray(outputGroup)) {
            for (const conn of outputGroup) {
              if (conn.node && !nodeNames.has(conn.node)) {
                errors.push(`Connection target non-existent: ${conn.node}`);
              }
            }
          }
        }
      }
    }
  }

  return { valid: errors.length === 0, errors };
}

// Tool definitions
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    // === STANDARD API TOOLS ===
    {
      name: "n8n_list_workflows",
      description: "List all workflows in the n8n instance",
      inputSchema: {
        type: "object",
        properties: {
          active: {
            type: "boolean",
            description: "Filter by active status",
          },
          limit: {
            type: "number",
            description: "Max results (default: 100)",
          },
        },
        required: [],
      },
    },
    {
      name: "n8n_get_workflow",
      description: "Get a specific workflow by ID",
      inputSchema: {
        type: "object",
        properties: {
          workflowId: {
            type: "string",
            description: "Workflow ID",
          },
        },
        required: ["workflowId"],
      },
    },
    {
      name: "n8n_create_workflow",
      description: "Create a new workflow from JSON",
      inputSchema: {
        type: "object",
        properties: {
          workflow: {
            type: "object",
            description: "Full workflow JSON",
          },
        },
        required: ["workflow"],
      },
    },
    {
      name: "n8n_update_workflow",
      description: "Update an existing workflow",
      inputSchema: {
        type: "object",
        properties: {
          workflowId: {
            type: "string",
            description: "Workflow ID",
          },
          workflow: {
            type: "object",
            description: "Updated workflow JSON",
          },
        },
        required: ["workflowId", "workflow"],
      },
    },
    {
      name: "n8n_delete_workflow",
      description: "Delete a workflow",
      inputSchema: {
        type: "object",
        properties: {
          workflowId: {
            type: "string",
            description: "Workflow ID",
          },
        },
        required: ["workflowId"],
      },
    },
    {
      name: "n8n_activate_workflow",
      description: "Activate a workflow",
      inputSchema: {
        type: "object",
        properties: {
          workflowId: {
            type: "string",
            description: "Workflow ID",
          },
        },
        required: ["workflowId"],
      },
    },
    {
      name: "n8n_deactivate_workflow",
      description: "Deactivate a workflow",
      inputSchema: {
        type: "object",
        properties: {
          workflowId: {
            type: "string",
            description: "Workflow ID",
          },
        },
        required: ["workflowId"],
      },
    },
    {
      name: "n8n_execute_workflow",
      description: "Execute a workflow with optional input data",
      inputSchema: {
        type: "object",
        properties: {
          workflowId: {
            type: "string",
            description: "Workflow ID",
          },
          inputData: {
            type: "object",
            description: "Input data for the workflow",
          },
        },
        required: ["workflowId"],
      },
    },
    {
      name: "n8n_list_executions",
      description: "List workflow executions",
      inputSchema: {
        type: "object",
        properties: {
          workflowId: {
            type: "string",
            description: "Filter by workflow ID",
          },
          status: {
            type: "string",
            enum: ["success", "error", "waiting"],
            description: "Filter by status",
          },
          limit: {
            type: "number",
            description: "Max results (default: 20)",
          },
        },
        required: [],
      },
    },
    {
      name: "n8n_get_execution",
      description: "Get detailed execution data including node outputs",
      inputSchema: {
        type: "object",
        properties: {
          executionId: {
            type: "string",
            description: "Execution ID",
          },
        },
        required: ["executionId"],
      },
    },

    // === ENHANCED TOOLS ===
    {
      name: "n8n_get_execution_logs",
      description: "[ENHANCED] Get detailed logs for each node in an execution",
      inputSchema: {
        type: "object",
        properties: {
          executionId: {
            type: "string",
            description: "Execution ID",
          },
          nodeFilter: {
            type: "string",
            description: "Filter logs by node name (optional)",
          },
        },
        required: ["executionId"],
      },
    },
    {
      name: "n8n_get_node_output",
      description: "[ENHANCED] Get the output of a specific node from an execution",
      inputSchema: {
        type: "object",
        properties: {
          executionId: {
            type: "string",
            description: "Execution ID",
          },
          nodeName: {
            type: "string",
            description: "Name of the node",
          },
        },
        required: ["executionId", "nodeName"],
      },
    },
    {
      name: "n8n_patch_node",
      description: "[ENHANCED] Patch a specific node in a workflow without touching others",
      inputSchema: {
        type: "object",
        properties: {
          workflowId: {
            type: "string",
            description: "Workflow ID",
          },
          nodeIdentifier: {
            type: "string",
            description: "Node ID or node name",
          },
          patch: {
            type: "object",
            description: "Partial node data to merge (parameters, position, etc.)",
          },
        },
        required: ["workflowId", "nodeIdentifier", "patch"],
      },
    },
    {
      name: "n8n_validate_workflow",
      description: "[ENHANCED] Validate a workflow JSON without importing it",
      inputSchema: {
        type: "object",
        properties: {
          workflow: {
            type: "object",
            description: "Workflow JSON to validate",
          },
        },
        required: ["workflow"],
      },
    },
    {
      name: "n8n_test_workflow",
      description: "[ENHANCED] Run test cases against a workflow with assertions",
      inputSchema: {
        type: "object",
        properties: {
          workflowId: {
            type: "string",
            description: "Workflow ID",
          },
          testCases: {
            type: "array",
            items: {
              type: "object",
              properties: {
                name: { type: "string" },
                input: { type: "object" },
                expectedOutput: { type: "object" },
                expectedNodes: {
                  type: "array",
                  items: { type: "string" },
                  description: "Nodes that should execute",
                },
              },
            },
            description: "Array of test cases",
          },
        },
        required: ["workflowId", "testCases"],
      },
    },
    {
      name: "n8n_get_credentials_info",
      description: "[ENHANCED] Get credential information (without secrets) used by a workflow",
      inputSchema: {
        type: "object",
        properties: {
          workflowId: {
            type: "string",
            description: "Workflow ID",
          },
        },
        required: ["workflowId"],
      },
    },
    {
      name: "n8n_check_connections",
      description: "[ENHANCED] Verify all node connections in a workflow are valid",
      inputSchema: {
        type: "object",
        properties: {
          workflowId: {
            type: "string",
            description: "Workflow ID",
          },
        },
        required: ["workflowId"],
      },
    },
    {
      name: "n8n_compare_workflows",
      description: "[ENHANCED] Compare two workflows and show differences",
      inputSchema: {
        type: "object",
        properties: {
          workflowId1: {
            type: "string",
            description: "First workflow ID",
          },
          workflowId2: {
            type: "string",
            description: "Second workflow ID",
          },
        },
        required: ["workflowId1", "workflowId2"],
      },
    },
  ],
}));

// Tool handlers
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      // === STANDARD API IMPLEMENTATIONS ===
      case "n8n_list_workflows": {
        const params = new URLSearchParams();
        if (args.active !== undefined) params.append("active", String(args.active));
        if (args.limit) params.append("limit", String(args.limit));
        const result = await n8nRequest(`/workflows?${params}`);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "n8n_get_workflow": {
        const result = await n8nRequest(`/workflows/${args.workflowId}`);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "n8n_create_workflow": {
        const result = await n8nRequest("/workflows", "POST", args.workflow);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "n8n_update_workflow": {
        const result = await n8nRequest(`/workflows/${args.workflowId}`, "PUT", args.workflow);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "n8n_delete_workflow": {
        await n8nRequest(`/workflows/${args.workflowId}`, "DELETE");
        return { content: [{ type: "text", text: `Workflow ${args.workflowId} deleted` }] };
      }

      case "n8n_activate_workflow": {
        const result = await n8nRequest(`/workflows/${args.workflowId}/activate`, "POST");
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "n8n_deactivate_workflow": {
        const result = await n8nRequest(`/workflows/${args.workflowId}/deactivate`, "POST");
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "n8n_execute_workflow": {
        const body = args.inputData ? { data: args.inputData } : undefined;
        const result = await n8nRequest(`/workflows/${args.workflowId}/execute`, "POST", body);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "n8n_list_executions": {
        const params = new URLSearchParams();
        if (args.workflowId) params.append("workflowId", args.workflowId);
        if (args.status) params.append("status", args.status);
        params.append("limit", String(args.limit || 20));
        const result = await n8nRequest(`/executions?${params}`);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "n8n_get_execution": {
        const result = await n8nRequest(`/executions/${args.executionId}`);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      // === ENHANCED IMPLEMENTATIONS ===
      case "n8n_get_execution_logs": {
        const execution = await n8nRequest(`/executions/${args.executionId}`);
        const logs: any[] = [];

        if (execution.data?.resultData?.runData) {
          for (const [nodeName, nodeRuns] of Object.entries(execution.data.resultData.runData)) {
            if (args.nodeFilter && !nodeName.includes(args.nodeFilter)) continue;

            const runs = nodeRuns as any[];
            for (const run of runs) {
              logs.push({
                nodeName,
                startTime: run.startTime,
                executionTime: run.executionTime,
                status: run.executionStatus,
                error: run.error?.message,
                itemsProcessed: run.data?.main?.[0]?.length || 0,
              });
            }
          }
        }

        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              executionId: args.executionId,
              status: execution.status,
              startedAt: execution.startedAt,
              stoppedAt: execution.stoppedAt,
              nodeLogs: logs,
            }, null, 2),
          }],
        };
      }

      case "n8n_get_node_output": {
        const execution = await n8nRequest(`/executions/${args.executionId}`);

        if (!execution.data?.resultData?.runData?.[args.nodeName]) {
          throw new Error(`Node "${args.nodeName}" not found in execution`);
        }

        const nodeData = execution.data.resultData.runData[args.nodeName];
        const lastRun = nodeData[nodeData.length - 1];

        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              nodeName: args.nodeName,
              status: lastRun.executionStatus,
              executionTime: lastRun.executionTime,
              output: lastRun.data?.main || [],
              error: lastRun.error,
            }, null, 2),
          }],
        };
      }

      case "n8n_patch_node": {
        // Get current workflow
        const workflow = await n8nRequest(`/workflows/${args.workflowId}`);
        const nodeMap = indexWorkflowNodes(workflow);

        const nodeInfo = nodeMap.get(args.nodeIdentifier);
        if (!nodeInfo) {
          throw new Error(`Node "${args.nodeIdentifier}" not found`);
        }

        // Apply patch
        const { index, node } = nodeInfo;
        workflow.nodes[index] = {
          ...node,
          ...args.patch,
          parameters: {
            ...node.parameters,
            ...(args.patch.parameters || {}),
          },
        };

        // Update workflow
        const result = await n8nRequest(`/workflows/${args.workflowId}`, "PUT", workflow);

        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              success: true,
              nodeName: node.name,
              nodeId: node.id,
              patchApplied: args.patch,
            }, null, 2),
          }],
        };
      }

      case "n8n_validate_workflow": {
        const validation = validateWorkflowStructure(args.workflow);

        // Additional checks
        const warnings: string[] = [];

        // Check for deprecated nodes
        const deprecatedTypes = ["n8n-nodes-base.function", "n8n-nodes-base.functionItem"];
        args.workflow.nodes?.forEach((node: any) => {
          if (deprecatedTypes.includes(node.type)) {
            warnings.push(`Node "${node.name}" uses deprecated type: ${node.type}`);
          }
        });

        // Check for missing credentials
        args.workflow.nodes?.forEach((node: any) => {
          if (node.credentials) {
            for (const [credType, credRef] of Object.entries(node.credentials)) {
              if (!(credRef as any).id) {
                warnings.push(`Node "${node.name}" has unconfigured credential: ${credType}`);
              }
            }
          }
        });

        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              valid: validation.valid,
              errors: validation.errors,
              warnings,
              nodeCount: args.workflow.nodes?.length || 0,
              connectionCount: Object.keys(args.workflow.connections || {}).length,
            }, null, 2),
          }],
        };
      }

      case "n8n_test_workflow": {
        const results: any[] = [];

        for (const testCase of args.testCases) {
          try {
            const execution = await n8nRequest(
              `/workflows/${args.workflowId}/execute`,
              "POST",
              { data: testCase.input }
            );

            // Wait a bit for execution to complete (simplified)
            await new Promise(resolve => setTimeout(resolve, 2000));

            // Get execution result
            const execResult = await n8nRequest(`/executions/${execution.id}`);

            const testResult: any = {
              name: testCase.name,
              executionId: execution.id,
              status: execResult.status,
              passed: true,
              assertions: [],
            };

            // Check expected nodes executed
            if (testCase.expectedNodes) {
              const executedNodes = Object.keys(execResult.data?.resultData?.runData || {});
              for (const expectedNode of testCase.expectedNodes) {
                const nodeExecuted = executedNodes.includes(expectedNode);
                testResult.assertions.push({
                  type: "nodeExecuted",
                  node: expectedNode,
                  passed: nodeExecuted,
                });
                if (!nodeExecuted) testResult.passed = false;
              }
            }

            // Check expected output (simplified comparison)
            if (testCase.expectedOutput) {
              const lastNode = execResult.data?.resultData?.lastNodeExecuted;
              const output = execResult.data?.resultData?.runData?.[lastNode]?.[0]?.data?.main?.[0];
              const outputMatches = JSON.stringify(output) === JSON.stringify(testCase.expectedOutput);
              testResult.assertions.push({
                type: "outputMatch",
                passed: outputMatches,
                expected: testCase.expectedOutput,
                actual: output,
              });
              if (!outputMatches) testResult.passed = false;
            }

            results.push(testResult);
          } catch (error) {
            results.push({
              name: testCase.name,
              passed: false,
              error: error instanceof Error ? error.message : String(error),
            });
          }
        }

        const summary = {
          totalTests: results.length,
          passed: results.filter(r => r.passed).length,
          failed: results.filter(r => !r.passed).length,
          results,
        };

        return { content: [{ type: "text", text: JSON.stringify(summary, null, 2) }] };
      }

      case "n8n_get_credentials_info": {
        const workflow = await n8nRequest(`/workflows/${args.workflowId}`);
        const credentials: any[] = [];

        workflow.nodes?.forEach((node: any) => {
          if (node.credentials) {
            for (const [credType, credRef] of Object.entries(node.credentials)) {
              const ref = credRef as any;
              credentials.push({
                nodeName: node.name,
                nodeType: node.type,
                credentialType: credType,
                credentialId: ref.id,
                credentialName: ref.name,
              });
            }
          }
        });

        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              workflowId: args.workflowId,
              workflowName: workflow.name,
              credentials,
              uniqueCredentials: [...new Set(credentials.map(c => c.credentialId))].length,
            }, null, 2),
          }],
        };
      }

      case "n8n_check_connections": {
        const workflow = await n8nRequest(`/workflows/${args.workflowId}`);
        const validation = validateWorkflowStructure(workflow);

        const issues: any[] = [];
        const nodeNames = new Set(workflow.nodes?.map((n: any) => n.name) || []);

        // Check for orphan nodes (no inputs or outputs)
        const nodesWithConnections = new Set<string>();

        if (workflow.connections) {
          for (const [sourceName, outputs] of Object.entries(workflow.connections)) {
            nodesWithConnections.add(sourceName);
            if (Array.isArray(outputs)) {
              for (const outputGroup of outputs) {
                if (Array.isArray(outputGroup)) {
                  for (const conn of outputGroup) {
                    if (conn.node) nodesWithConnections.add(conn.node);
                  }
                }
              }
            }
          }
        }

        // Find trigger nodes (they don't need inputs)
        const triggerNodes = new Set(
          workflow.nodes?.filter((n: any) =>
            n.type.includes("trigger") || n.type.includes("Trigger") || n.type.includes("webhook")
          ).map((n: any) => n.name) || []
        );

        workflow.nodes?.forEach((node: any) => {
          if (!nodesWithConnections.has(node.name) && !triggerNodes.has(node.name)) {
            issues.push({
              type: "orphanNode",
              node: node.name,
              message: "Node has no connections",
            });
          }
        });

        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              workflowId: args.workflowId,
              valid: validation.valid && issues.length === 0,
              structureErrors: validation.errors,
              connectionIssues: issues,
              stats: {
                totalNodes: workflow.nodes?.length || 0,
                connectedNodes: nodesWithConnections.size,
                triggerNodes: triggerNodes.size,
              },
            }, null, 2),
          }],
        };
      }

      case "n8n_compare_workflows": {
        const wf1 = await n8nRequest(`/workflows/${args.workflowId1}`);
        const wf2 = await n8nRequest(`/workflows/${args.workflowId2}`);

        const diff: any = {
          name: { wf1: wf1.name, wf2: wf2.name },
          nodeCount: { wf1: wf1.nodes?.length || 0, wf2: wf2.nodes?.length || 0 },
          nodesOnlyInWf1: [],
          nodesOnlyInWf2: [],
          nodesDifferent: [],
        };

        const wf1Nodes = new Map(wf1.nodes?.map((n: any) => [n.name, n]) || []);
        const wf2Nodes = new Map(wf2.nodes?.map((n: any) => [n.name, n]) || []);

        for (const [name, node] of wf1Nodes) {
          if (!wf2Nodes.has(name)) {
            diff.nodesOnlyInWf1.push(name);
          } else {
            const node2 = wf2Nodes.get(name);
            if (JSON.stringify(node) !== JSON.stringify(node2)) {
              diff.nodesDifferent.push({
                name,
                differences: {
                  type: node.type !== node2.type,
                  parameters: JSON.stringify(node.parameters) !== JSON.stringify(node2.parameters),
                  position: JSON.stringify(node.position) !== JSON.stringify(node2.position),
                },
              });
            }
          }
        }

        for (const name of wf2Nodes.keys()) {
          if (!wf1Nodes.has(name)) {
            diff.nodesOnlyInWf2.push(name);
          }
        }

        return { content: [{ type: "text", text: JSON.stringify(diff, null, 2) }] };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    return {
      content: [{
        type: "text",
        text: `Error: ${error instanceof Error ? error.message : String(error)}`,
      }],
      isError: true,
    };
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("N8N Enhanced MCP server running");
}

main().catch(console.error);
