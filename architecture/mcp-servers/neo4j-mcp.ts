/**
 * MCP Server for Neo4j Graph Database
 * URL: https://a9a062c3.databases.neo4j.io/db/neo4j/query/v2
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const NEO4J_URI = process.env.NEO4J_URI || "https://a9a062c3.databases.neo4j.io";
const NEO4J_DATABASE = process.env.NEO4J_DATABASE || "neo4j";
const NEO4J_USER = process.env.NEO4J_USER || "neo4j";
const NEO4J_PASSWORD = process.env.NEO4J_PASSWORD;

if (!NEO4J_PASSWORD) {
  throw new Error("NEO4J_PASSWORD environment variable is required");
}

const server = new Server(
  { name: "neo4j-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// Helper function for Neo4j Query API
async function neo4jQuery(cypher: string, parameters: Record<string, any> = {}): Promise<any> {
  const url = `${NEO4J_URI}/db/${NEO4J_DATABASE}/query/v2`;
  const auth = Buffer.from(`${NEO4J_USER}:${NEO4J_PASSWORD}`).toString("base64");

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Basic ${auth}`,
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify({
      statement: cypher,
      parameters,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Neo4j API error: ${response.status} - ${errorText}`);
  }

  return response.json();
}

// Tool definitions
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "neo4j_query",
      description: "Execute a Cypher query against the Neo4j database",
      inputSchema: {
        type: "object",
        properties: {
          cypher: {
            type: "string",
            description: "The Cypher query to execute",
          },
          parameters: {
            type: "object",
            description: "Query parameters (optional)",
          },
        },
        required: ["cypher"],
      },
    },
    {
      name: "neo4j_get_schema",
      description: "Get the database schema including node labels, relationship types, and properties",
      inputSchema: {
        type: "object",
        properties: {},
        required: [],
      },
    },
    {
      name: "neo4j_get_node_labels",
      description: "List all node labels with their counts",
      inputSchema: {
        type: "object",
        properties: {},
        required: [],
      },
    },
    {
      name: "neo4j_get_relationship_types",
      description: "List all relationship types with their counts",
      inputSchema: {
        type: "object",
        properties: {},
        required: [],
      },
    },
    {
      name: "neo4j_find_nodes",
      description: "Find nodes by label and optional property filters",
      inputSchema: {
        type: "object",
        properties: {
          label: {
            type: "string",
            description: "Node label to search",
          },
          filters: {
            type: "object",
            description: "Property filters (key-value pairs)",
          },
          limit: {
            type: "number",
            description: "Maximum results (default: 25)",
          },
        },
        required: ["label"],
      },
    },
    {
      name: "neo4j_get_node_relationships",
      description: "Get all relationships for a specific node",
      inputSchema: {
        type: "object",
        properties: {
          nodeId: {
            type: "string",
            description: "The node's element ID or a property to match",
          },
          label: {
            type: "string",
            description: "Node label (optional, improves performance)",
          },
          direction: {
            type: "string",
            enum: ["incoming", "outgoing", "both"],
            description: "Relationship direction (default: both)",
          },
        },
        required: ["nodeId"],
      },
    },
    {
      name: "neo4j_stats",
      description: "Get database statistics (node count, relationship count, etc.)",
      inputSchema: {
        type: "object",
        properties: {},
        required: [],
      },
    },
    {
      name: "neo4j_find_isolated_nodes",
      description: "Find nodes with no relationships (orphans)",
      inputSchema: {
        type: "object",
        properties: {
          label: {
            type: "string",
            description: "Filter by label (optional)",
          },
          limit: {
            type: "number",
            description: "Maximum results (default: 100)",
          },
        },
        required: [],
      },
    },
    {
      name: "neo4j_path_between",
      description: "Find paths between two nodes",
      inputSchema: {
        type: "object",
        properties: {
          startNodeId: {
            type: "string",
            description: "Starting node ID",
          },
          endNodeId: {
            type: "string",
            description: "Ending node ID",
          },
          maxDepth: {
            type: "number",
            description: "Maximum path length (default: 5)",
          },
        },
        required: ["startNodeId", "endNodeId"],
      },
    },
  ],
}));

// Tool handlers
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "neo4j_query": {
        const result = await neo4jQuery(args.cypher, args.parameters || {});
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "neo4j_get_schema": {
        const labels = await neo4jQuery("CALL db.labels() YIELD label RETURN label");
        const relTypes = await neo4jQuery("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType");
        const props = await neo4jQuery(`
          CALL db.schema.nodeTypeProperties() YIELD nodeLabels, propertyName, propertyTypes
          RETURN nodeLabels, propertyName, propertyTypes
        `);

        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              nodeLabels: labels.data?.values?.map((v: any) => v[0]) || [],
              relationshipTypes: relTypes.data?.values?.map((v: any) => v[0]) || [],
              nodeProperties: props.data?.values || [],
            }, null, 2),
          }],
        };
      }

      case "neo4j_get_node_labels": {
        const result = await neo4jQuery(`
          CALL db.labels() YIELD label
          CALL {
            WITH label
            MATCH (n) WHERE label IN labels(n)
            RETURN count(n) as count
          }
          RETURN label, count
          ORDER BY count DESC
        `);
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "neo4j_get_relationship_types": {
        const result = await neo4jQuery(`
          CALL db.relationshipTypes() YIELD relationshipType
          CALL {
            WITH relationshipType
            MATCH ()-[r]->() WHERE type(r) = relationshipType
            RETURN count(r) as count
          }
          RETURN relationshipType, count
          ORDER BY count DESC
        `);
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "neo4j_find_nodes": {
        const limit = args.limit || 25;
        let whereClause = "";
        const params: Record<string, any> = {};

        if (args.filters && Object.keys(args.filters).length > 0) {
          const conditions = Object.entries(args.filters).map(([key, value], i) => {
            params[`p${i}`] = value;
            return `n.${key} = $p${i}`;
          });
          whereClause = `WHERE ${conditions.join(" AND ")}`;
        }

        const result = await neo4jQuery(
          `MATCH (n:${args.label}) ${whereClause} RETURN n LIMIT ${limit}`,
          params
        );
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "neo4j_get_node_relationships": {
        const direction = args.direction || "both";
        let pattern = "";
        switch (direction) {
          case "incoming": pattern = "<-[r]-"; break;
          case "outgoing": pattern = "-[r]->"; break;
          default: pattern = "-[r]-";
        }

        const labelMatch = args.label ? `:${args.label}` : "";
        const result = await neo4jQuery(
          `MATCH (n${labelMatch})${pattern}(m)
           WHERE elementId(n) = $nodeId OR n.id = $nodeId
           RETURN type(r) as relType, properties(r) as relProps,
                  labels(m) as targetLabels, properties(m) as targetProps
           LIMIT 50`,
          { nodeId: args.nodeId }
        );
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "neo4j_stats": {
        const nodes = await neo4jQuery("MATCH (n) RETURN count(n) as nodeCount");
        const rels = await neo4jQuery("MATCH ()-[r]->() RETURN count(r) as relCount");
        const labels = await neo4jQuery("CALL db.labels() YIELD label RETURN count(label) as labelCount");
        const relTypes = await neo4jQuery("CALL db.relationshipTypes() YIELD relationshipType RETURN count(relationshipType) as typeCount");

        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              totalNodes: nodes.data?.values?.[0]?.[0] || 0,
              totalRelationships: rels.data?.values?.[0]?.[0] || 0,
              labelCount: labels.data?.values?.[0]?.[0] || 0,
              relationshipTypeCount: relTypes.data?.values?.[0]?.[0] || 0,
            }, null, 2),
          }],
        };
      }

      case "neo4j_find_isolated_nodes": {
        const limit = args.limit || 100;
        const labelFilter = args.label ? `:${args.label}` : "";

        const result = await neo4jQuery(
          `MATCH (n${labelFilter})
           WHERE NOT (n)--()
           RETURN n LIMIT ${limit}`
        );
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "neo4j_path_between": {
        const maxDepth = args.maxDepth || 5;
        const result = await neo4jQuery(
          `MATCH path = shortestPath((a)-[*1..${maxDepth}]-(b))
           WHERE elementId(a) = $startId AND elementId(b) = $endId
           RETURN path`,
          { startId: args.startNodeId, endId: args.endNodeId }
        );
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
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
  console.error("Neo4j MCP server running");
}

main().catch(console.error);
