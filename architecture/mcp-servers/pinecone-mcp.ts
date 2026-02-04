/**
 * MCP Server for Pinecone Vector Database
 * URL: https://n8nultimate-a4mkzmz.svc.aped-4627-b74a.pinecone.io
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const PINECONE_HOST = process.env.PINECONE_HOST || "https://n8nultimate-a4mkzmz.svc.aped-4627-b74a.pinecone.io";
const PINECONE_API_KEY = process.env.PINECONE_API_KEY;

if (!PINECONE_API_KEY) {
  throw new Error("PINECONE_API_KEY environment variable is required");
}

const server = new Server(
  { name: "pinecone-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// Helper function for Pinecone API calls
async function pineconeRequest(
  endpoint: string,
  method: string = "GET",
  body?: object
): Promise<any> {
  const url = `${PINECONE_HOST}${endpoint}`;
  const response = await fetch(url, {
    method,
    headers: {
      "Api-Key": PINECONE_API_KEY!,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    throw new Error(`Pinecone API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

// Tool definitions
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "pinecone_describe_index",
      description: "Get detailed information about the Pinecone index including dimensions, metric, and stats",
      inputSchema: {
        type: "object",
        properties: {},
        required: [],
      },
    },
    {
      name: "pinecone_query",
      description: "Query the Pinecone index with a vector to find similar vectors",
      inputSchema: {
        type: "object",
        properties: {
          vector: {
            type: "array",
            items: { type: "number" },
            description: "The query vector",
          },
          topK: {
            type: "number",
            description: "Number of results to return (default: 10)",
          },
          namespace: {
            type: "string",
            description: "Namespace to query (optional)",
          },
          includeMetadata: {
            type: "boolean",
            description: "Include metadata in results (default: true)",
          },
          filter: {
            type: "object",
            description: "Metadata filter (optional)",
          },
        },
        required: ["vector"],
      },
    },
    {
      name: "pinecone_fetch",
      description: "Fetch vectors by their IDs",
      inputSchema: {
        type: "object",
        properties: {
          ids: {
            type: "array",
            items: { type: "string" },
            description: "Vector IDs to fetch",
          },
          namespace: {
            type: "string",
            description: "Namespace (optional)",
          },
        },
        required: ["ids"],
      },
    },
    {
      name: "pinecone_upsert",
      description: "Insert or update vectors in the index",
      inputSchema: {
        type: "object",
        properties: {
          vectors: {
            type: "array",
            items: {
              type: "object",
              properties: {
                id: { type: "string" },
                values: { type: "array", items: { type: "number" } },
                metadata: { type: "object" },
              },
              required: ["id", "values"],
            },
            description: "Vectors to upsert",
          },
          namespace: {
            type: "string",
            description: "Namespace (optional)",
          },
        },
        required: ["vectors"],
      },
    },
    {
      name: "pinecone_delete",
      description: "Delete vectors by IDs or filter",
      inputSchema: {
        type: "object",
        properties: {
          ids: {
            type: "array",
            items: { type: "string" },
            description: "Vector IDs to delete",
          },
          deleteAll: {
            type: "boolean",
            description: "Delete all vectors in namespace",
          },
          namespace: {
            type: "string",
            description: "Namespace (optional)",
          },
          filter: {
            type: "object",
            description: "Metadata filter for deletion",
          },
        },
        required: [],
      },
    },
    {
      name: "pinecone_stats",
      description: "Get index statistics including vector count per namespace",
      inputSchema: {
        type: "object",
        properties: {
          filter: {
            type: "object",
            description: "Filter for stats (optional)",
          },
        },
        required: [],
      },
    },
    {
      name: "pinecone_list_namespaces",
      description: "List all namespaces in the index with their vector counts",
      inputSchema: {
        type: "object",
        properties: {},
        required: [],
      },
    },
  ],
}));

// Tool handlers
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "pinecone_describe_index": {
        const stats = await pineconeRequest("/describe_index_stats", "POST", {});
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(stats, null, 2),
            },
          ],
        };
      }

      case "pinecone_query": {
        const result = await pineconeRequest("/query", "POST", {
          vector: args.vector,
          topK: args.topK || 10,
          namespace: args.namespace || "",
          includeMetadata: args.includeMetadata !== false,
          filter: args.filter,
        });
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case "pinecone_fetch": {
        const params = new URLSearchParams();
        args.ids.forEach((id: string) => params.append("ids", id));
        if (args.namespace) params.append("namespace", args.namespace);

        const result = await pineconeRequest(`/vectors/fetch?${params}`);
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case "pinecone_upsert": {
        const result = await pineconeRequest("/vectors/upsert", "POST", {
          vectors: args.vectors,
          namespace: args.namespace || "",
        });
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case "pinecone_delete": {
        const result = await pineconeRequest("/vectors/delete", "POST", {
          ids: args.ids,
          deleteAll: args.deleteAll,
          namespace: args.namespace || "",
          filter: args.filter,
        });
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case "pinecone_stats": {
        const result = await pineconeRequest("/describe_index_stats", "POST", {
          filter: args.filter,
        });
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case "pinecone_list_namespaces": {
        const stats = await pineconeRequest("/describe_index_stats", "POST", {});
        const namespaces = stats.namespaces || {};
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  namespaces: Object.entries(namespaces).map(([name, data]: [string, any]) => ({
                    name: name || "(default)",
                    vectorCount: data.vectorCount,
                  })),
                  totalVectors: stats.totalVectorCount,
                },
                null,
                2
              ),
            },
          ],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: `Error: ${error instanceof Error ? error.message : String(error)}`,
        },
      ],
      isError: true,
    };
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Pinecone MCP server running");
}

main().catch(console.error);
