/**
 * MCP Server for Supabase PostgreSQL
 * Connection: postgresql://postgres:***@db.ayqviqmxifzmhphiqfmj.supabase.co:5432/postgres
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import pg from "pg";

const { Pool } = pg;

const CONNECTION_STRING = process.env.POSTGRES_CONNECTION_STRING ||
  "postgresql://postgres:LxtBJKljhhBassDS@db.ayqviqmxifzmhphiqfmj.supabase.co:5432/postgres";

const pool = new Pool({
  connectionString: CONNECTION_STRING,
  ssl: { rejectUnauthorized: false },
});

const server = new Server(
  { name: "supabase-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// Helper function for safe queries
async function query(sql: string, params: any[] = []): Promise<any> {
  const client = await pool.connect();
  try {
    const result = await client.query(sql, params);
    return {
      rows: result.rows,
      rowCount: result.rowCount,
      fields: result.fields?.map(f => ({ name: f.name, dataType: f.dataTypeID })),
    };
  } finally {
    client.release();
  }
}

// Tool definitions
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "pg_query",
      description: "Execute a read-only SQL query against the database",
      inputSchema: {
        type: "object",
        properties: {
          sql: {
            type: "string",
            description: "The SQL query to execute (SELECT only for safety)",
          },
          params: {
            type: "array",
            items: {},
            description: "Query parameters for prepared statements ($1, $2, etc.)",
          },
        },
        required: ["sql"],
      },
    },
    {
      name: "pg_list_tables",
      description: "List all tables in the database with row counts",
      inputSchema: {
        type: "object",
        properties: {
          schema: {
            type: "string",
            description: "Schema name (default: public)",
          },
        },
        required: [],
      },
    },
    {
      name: "pg_describe_table",
      description: "Get detailed schema information for a table",
      inputSchema: {
        type: "object",
        properties: {
          table: {
            type: "string",
            description: "Table name",
          },
          schema: {
            type: "string",
            description: "Schema name (default: public)",
          },
        },
        required: ["table"],
      },
    },
    {
      name: "pg_list_functions",
      description: "List all RPC functions available in Supabase",
      inputSchema: {
        type: "object",
        properties: {
          schema: {
            type: "string",
            description: "Schema name (default: public)",
          },
        },
        required: [],
      },
    },
    {
      name: "pg_foreign_keys",
      description: "Get all foreign key relationships in the database",
      inputSchema: {
        type: "object",
        properties: {
          table: {
            type: "string",
            description: "Filter by table name (optional)",
          },
        },
        required: [],
      },
    },
    {
      name: "pg_indexes",
      description: "List all indexes for a table or the entire database",
      inputSchema: {
        type: "object",
        properties: {
          table: {
            type: "string",
            description: "Table name (optional)",
          },
        },
        required: [],
      },
    },
    {
      name: "pg_check_nulls",
      description: "Find columns with high null percentages in a table",
      inputSchema: {
        type: "object",
        properties: {
          table: {
            type: "string",
            description: "Table name",
          },
          threshold: {
            type: "number",
            description: "Null percentage threshold (default: 50)",
          },
        },
        required: ["table"],
      },
    },
    {
      name: "pg_find_duplicates",
      description: "Find duplicate values in specified columns",
      inputSchema: {
        type: "object",
        properties: {
          table: {
            type: "string",
            description: "Table name",
          },
          columns: {
            type: "array",
            items: { type: "string" },
            description: "Columns to check for duplicates",
          },
          limit: {
            type: "number",
            description: "Maximum results (default: 100)",
          },
        },
        required: ["table", "columns"],
      },
    },
    {
      name: "pg_sample_data",
      description: "Get sample rows from a table",
      inputSchema: {
        type: "object",
        properties: {
          table: {
            type: "string",
            description: "Table name",
          },
          limit: {
            type: "number",
            description: "Number of rows (default: 10)",
          },
          orderBy: {
            type: "string",
            description: "Column to order by (optional)",
          },
        },
        required: ["table"],
      },
    },
    {
      name: "pg_execute_write",
      description: "Execute a write operation (INSERT, UPDATE, DELETE) with confirmation",
      inputSchema: {
        type: "object",
        properties: {
          sql: {
            type: "string",
            description: "The SQL statement to execute",
          },
          params: {
            type: "array",
            items: {},
            description: "Query parameters",
          },
          dryRun: {
            type: "boolean",
            description: "If true, only show what would be affected without executing",
          },
        },
        required: ["sql"],
      },
    },
  ],
}));

// Tool handlers
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "pg_query": {
        // Safety check: only allow SELECT, WITH (CTEs), and EXPLAIN
        const sqlUpper = args.sql.trim().toUpperCase();
        if (!sqlUpper.startsWith("SELECT") && !sqlUpper.startsWith("WITH") && !sqlUpper.startsWith("EXPLAIN")) {
          throw new Error("Only SELECT queries are allowed. Use pg_execute_write for modifications.");
        }
        const result = await query(args.sql, args.params || []);
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "pg_list_tables": {
        const schema = args.schema || "public";
        const result = await query(`
          SELECT
            t.table_name,
            pg_stat_user_tables.n_live_tup as estimated_row_count,
            pg_size_pretty(pg_total_relation_size(quote_ident(t.table_name))) as total_size
          FROM information_schema.tables t
          LEFT JOIN pg_stat_user_tables ON t.table_name = pg_stat_user_tables.relname
          WHERE t.table_schema = $1
            AND t.table_type = 'BASE TABLE'
          ORDER BY pg_total_relation_size(quote_ident(t.table_name)) DESC
        `, [schema]);
        return {
          content: [{ type: "text", text: JSON.stringify(result.rows, null, 2) }],
        };
      }

      case "pg_describe_table": {
        const schema = args.schema || "public";
        const columns = await query(`
          SELECT
            column_name,
            data_type,
            character_maximum_length,
            column_default,
            is_nullable,
            is_identity
          FROM information_schema.columns
          WHERE table_schema = $1 AND table_name = $2
          ORDER BY ordinal_position
        `, [schema, args.table]);

        const constraints = await query(`
          SELECT
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name
          FROM information_schema.table_constraints tc
          JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
          WHERE tc.table_schema = $1 AND tc.table_name = $2
        `, [schema, args.table]);

        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              table: args.table,
              schema,
              columns: columns.rows,
              constraints: constraints.rows,
            }, null, 2),
          }],
        };
      }

      case "pg_list_functions": {
        const schema = args.schema || "public";
        const result = await query(`
          SELECT
            p.proname as function_name,
            pg_get_function_arguments(p.oid) as arguments,
            pg_get_function_result(p.oid) as return_type,
            d.description
          FROM pg_proc p
          JOIN pg_namespace n ON p.pronamespace = n.oid
          LEFT JOIN pg_description d ON p.oid = d.objoid
          WHERE n.nspname = $1
            AND p.prokind = 'f'
          ORDER BY p.proname
        `, [schema]);
        return {
          content: [{ type: "text", text: JSON.stringify(result.rows, null, 2) }],
        };
      }

      case "pg_foreign_keys": {
        let sql = `
          SELECT
            tc.table_name as from_table,
            kcu.column_name as from_column,
            ccu.table_name as to_table,
            ccu.column_name as to_column,
            tc.constraint_name
          FROM information_schema.table_constraints tc
          JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
          JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
          WHERE tc.constraint_type = 'FOREIGN KEY'
        `;
        const params: string[] = [];

        if (args.table) {
          sql += ` AND (tc.table_name = $1 OR ccu.table_name = $1)`;
          params.push(args.table);
        }

        sql += ` ORDER BY tc.table_name, kcu.column_name`;

        const result = await query(sql, params);
        return {
          content: [{ type: "text", text: JSON.stringify(result.rows, null, 2) }],
        };
      }

      case "pg_indexes": {
        let sql = `
          SELECT
            tablename,
            indexname,
            indexdef
          FROM pg_indexes
          WHERE schemaname = 'public'
        `;
        const params: string[] = [];

        if (args.table) {
          sql += ` AND tablename = $1`;
          params.push(args.table);
        }

        sql += ` ORDER BY tablename, indexname`;

        const result = await query(sql, params);
        return {
          content: [{ type: "text", text: JSON.stringify(result.rows, null, 2) }],
        };
      }

      case "pg_check_nulls": {
        const threshold = args.threshold || 50;
        const columns = await query(`
          SELECT column_name
          FROM information_schema.columns
          WHERE table_schema = 'public' AND table_name = $1
        `, [args.table]);

        const results = [];
        for (const col of columns.rows) {
          const nullCheck = await query(`
            SELECT
              COUNT(*) as total,
              COUNT(*) FILTER (WHERE ${col.column_name} IS NULL) as null_count
            FROM ${args.table}
          `);
          const total = nullCheck.rows[0].total;
          const nullCount = nullCheck.rows[0].null_count;
          const nullPct = total > 0 ? (nullCount / total * 100).toFixed(2) : 0;

          if (Number(nullPct) >= threshold) {
            results.push({
              column: col.column_name,
              nullCount,
              totalRows: total,
              nullPercentage: `${nullPct}%`,
            });
          }
        }

        return {
          content: [{ type: "text", text: JSON.stringify(results, null, 2) }],
        };
      }

      case "pg_find_duplicates": {
        const limit = args.limit || 100;
        const columnList = args.columns.join(", ");
        const result = await query(`
          SELECT ${columnList}, COUNT(*) as duplicate_count
          FROM ${args.table}
          GROUP BY ${columnList}
          HAVING COUNT(*) > 1
          ORDER BY COUNT(*) DESC
          LIMIT ${limit}
        `);
        return {
          content: [{ type: "text", text: JSON.stringify(result.rows, null, 2) }],
        };
      }

      case "pg_sample_data": {
        const limit = args.limit || 10;
        const orderBy = args.orderBy ? `ORDER BY ${args.orderBy} DESC` : "";
        const result = await query(`
          SELECT * FROM ${args.table} ${orderBy} LIMIT ${limit}
        `);
        return {
          content: [{ type: "text", text: JSON.stringify(result.rows, null, 2) }],
        };
      }

      case "pg_execute_write": {
        if (args.dryRun) {
          // For dry run, try to estimate affected rows
          const sqlUpper = args.sql.trim().toUpperCase();
          let countSql = "";

          if (sqlUpper.startsWith("UPDATE")) {
            const match = args.sql.match(/UPDATE\s+(\w+)\s+SET.+WHERE\s+(.+)/i);
            if (match) {
              countSql = `SELECT COUNT(*) as affected FROM ${match[1]} WHERE ${match[2]}`;
            }
          } else if (sqlUpper.startsWith("DELETE")) {
            const match = args.sql.match(/DELETE\s+FROM\s+(\w+)\s+WHERE\s+(.+)/i);
            if (match) {
              countSql = `SELECT COUNT(*) as affected FROM ${match[1]} WHERE ${match[2]}`;
            }
          }

          if (countSql) {
            const result = await query(countSql, args.params || []);
            return {
              content: [{
                type: "text",
                text: JSON.stringify({
                  dryRun: true,
                  estimatedAffectedRows: result.rows[0]?.affected || 0,
                  sql: args.sql,
                }, null, 2),
              }],
            };
          }

          return {
            content: [{
              type: "text",
              text: JSON.stringify({
                dryRun: true,
                message: "Cannot estimate affected rows for this query type",
                sql: args.sql,
              }, null, 2),
            }],
          };
        }

        // Execute the write
        const result = await query(args.sql, args.params || []);
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              success: true,
              rowsAffected: result.rowCount,
            }, null, 2),
          }],
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
  console.error("Supabase MCP server running");
}

main().catch(console.error);
