/**
 * InfraBridge — Direct database access (same as Claude Code CLI on VM)
 *
 * Provides read-only access to:
 * - Supabase PostgreSQL (43K docs, 212 financial tables)
 * - Neo4j Aura (72K nodes, sector entities)
 * - Pinecone (58K vectors)
 */

const { Pool } = require('pg');
const neo4j = require('neo4j-driver');
const https = require('https');
const logger = require('./logger');

class InfraBridge {
  constructor(config) {
    this.config = config;

    // Supabase PostgreSQL connection pool
    if (config.supabaseUrl) {
      this.pgPool = new Pool({
        connectionString: config.supabaseUrl,
        max: 3,
        idleTimeoutMillis: 30000,
        connectionTimeoutMillis: 10000,
        ssl: { rejectUnauthorized: false },
      });
      logger.info('Supabase PG pool initialized');
    }

    // Neo4j driver
    if (config.neo4jUri && config.neo4jPassword) {
      this.neo4jDriver = neo4j.driver(
        config.neo4jUri,
        neo4j.auth.basic('neo4j', config.neo4jPassword),
        {
          maxConnectionPoolSize: 3,
          connectionAcquisitionTimeout: 10000,
        }
      );
      logger.info('Neo4j driver initialized');
    }

    // Pinecone config
    this.pineconeHost = config.pineconeHost;
    this.pineconeApiKey = config.pineconeApiKey;
  }

  /**
   * Query Supabase PostgreSQL
   */
  async querySupabase(sql) {
    if (!this.pgPool) throw new Error('Supabase not configured');

    const client = await this.pgPool.connect();
    try {
      // Always set search_path to public (schema quirk)
      await client.query('SET search_path TO public');
      const result = await client.query(sql);
      return {
        rows: result.rows,
        rowCount: result.rowCount,
        fields: result.fields?.map(f => f.name),
      };
    } finally {
      client.release();
    }
  }

  /**
   * Query Neo4j
   */
  async queryNeo4j(cypher) {
    if (!this.neo4jDriver) throw new Error('Neo4j not configured');

    const session = this.neo4jDriver.session({ defaultAccessMode: neo4j.session.READ });
    try {
      const result = await session.run(cypher);
      return result.records.map(record => {
        const obj = {};
        record.keys.forEach(key => {
          const val = record.get(key);
          obj[key] = neo4j.isInt(val) ? val.toNumber() : val;
        });
        return obj;
      });
    } finally {
      await session.close();
    }
  }

  /**
   * Query Pinecone (describe index stats)
   */
  async queryPinecone(options = {}) {
    if (!this.pineconeHost || !this.pineconeApiKey) {
      throw new Error('Pinecone not configured');
    }

    const url = `https://${this.pineconeHost}/describe_index_stats`;

    return new Promise((resolve, reject) => {
      const parsedUrl = new URL(url);
      const req = https.request({
        hostname: parsedUrl.hostname,
        path: parsedUrl.pathname,
        method: 'POST',
        headers: {
          'Api-Key': this.pineconeApiKey,
          'Content-Type': 'application/json',
        },
        timeout: 15000,
      }, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch {
            resolve({ raw: data });
          }
        });
      });

      req.on('error', reject);
      req.write(JSON.stringify(options.filter ? { filter: options.filter } : {}));
      req.end();
    });
  }

  /**
   * Check all database connections
   */
  async checkDatabases() {
    const status = {};

    // Supabase
    try {
      if (this.pgPool) {
        const res = await this.querySupabase(
          "SELECT count(*) as docs FROM sector_documents LIMIT 1"
        );
        status.supabase = {
          connected: true,
          info: `${res.rows[0]?.docs || '?'} docs`,
        };
      } else {
        status.supabase = { connected: false, info: 'Not configured' };
      }
    } catch (err) {
      status.supabase = { connected: false, info: err.message };
    }

    // Neo4j
    try {
      if (this.neo4jDriver) {
        const res = await this.queryNeo4j(
          "MATCH (n) RETURN count(n) as nodes LIMIT 1"
        );
        status.neo4j = {
          connected: true,
          info: `${res[0]?.nodes || '?'} nodes`,
        };
      } else {
        status.neo4j = { connected: false, info: 'Not configured' };
      }
    } catch (err) {
      status.neo4j = { connected: false, info: err.message };
    }

    // Pinecone
    try {
      if (this.pineconeHost) {
        const res = await this.queryPinecone();
        status.pinecone = {
          connected: true,
          info: `${res.totalVectorCount || res.total_vector_count || '?'} vectors`,
        };
      } else {
        status.pinecone = { connected: false, info: 'Not configured' };
      }
    } catch (err) {
      status.pinecone = { connected: false, info: err.message };
    }

    return status;
  }

  /**
   * Cleanup connections on shutdown
   */
  async close() {
    if (this.pgPool) await this.pgPool.end();
    if (this.neo4jDriver) await this.neo4jDriver.close();
  }
}

module.exports = InfraBridge;
