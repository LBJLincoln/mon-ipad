/**
 * Persistence — Conversation history & state management
 *
 * Uses HF Spaces persistent storage (/data/) for:
 * - Conversation histories per chat ID
 * - Execution logs
 * - Agent state
 *
 * Also optionally syncs to HF Hub dataset via API.
 */

const fs = require('fs');
const path = require('path');
const logger = require('./logger');

const DATA_DIR = process.env.PERSISTENCE_DIR || '/data/conversations';
const LOG_DIR = process.env.LOG_DIR || '/data/logs';
const MAX_HISTORY_PER_CHAT = 100;
const FLUSH_INTERVAL_MS = 60000;

class Persistence {
  constructor() {
    this.conversations = {};
    this.dirty = new Set();
    this.stats = { totalMessages: 0, activeChatIds: 0 };
  }

  init() {
    // Ensure directories
    for (const dir of [DATA_DIR, LOG_DIR]) {
      try {
        fs.mkdirSync(dir, { recursive: true });
      } catch {
        // May already exist
      }
    }

    // Load existing conversations from disk
    try {
      const files = fs.readdirSync(DATA_DIR).filter(f => f.endsWith('.json'));
      for (const file of files) {
        try {
          const chatId = path.basename(file, '.json');
          const data = JSON.parse(fs.readFileSync(path.join(DATA_DIR, file), 'utf8'));
          this.conversations[chatId] = data;
          this.stats.totalMessages += data.length;
        } catch (err) {
          logger.warn(`Failed to load conversation ${file}: ${err.message}`);
        }
      }
      this.stats.activeChatIds = Object.keys(this.conversations).length;
      logger.info(`Loaded ${this.stats.activeChatIds} conversations, ${this.stats.totalMessages} messages`);
    } catch (err) {
      logger.info('No existing conversations found, starting fresh');
    }
  }

  /**
   * Save a message to conversation history
   */
  saveMessage(chatId, role, content) {
    const key = String(chatId);
    if (!this.conversations[key]) {
      this.conversations[key] = [];
    }

    this.conversations[key].push({
      role,
      content,
      timestamp: new Date().toISOString(),
    });

    // Trim old messages
    if (this.conversations[key].length > MAX_HISTORY_PER_CHAT) {
      this.conversations[key] = this.conversations[key].slice(-MAX_HISTORY_PER_CHAT);
    }

    this.dirty.add(key);
    this.stats.totalMessages++;
    this.stats.activeChatIds = Object.keys(this.conversations).length;
  }

  /**
   * Get conversation history for a chat
   */
  getHistory(chatId, limit = 20) {
    const key = String(chatId);
    const history = this.conversations[key] || [];
    return history.slice(-limit);
  }

  /**
   * Flush dirty conversations to disk
   */
  flush() {
    if (this.dirty.size === 0) return;

    for (const chatId of this.dirty) {
      try {
        const filePath = path.join(DATA_DIR, `${chatId}.json`);
        fs.writeFileSync(filePath, JSON.stringify(this.conversations[chatId], null, 2));
      } catch (err) {
        logger.error(`Failed to flush conversation ${chatId}: ${err.message}`);
      }
    }

    logger.debug(`Flushed ${this.dirty.size} conversations to disk`);
    this.dirty.clear();
  }

  /**
   * Get persistence stats
   */
  getStats() {
    return {
      ...this.stats,
      dirtyCount: this.dirty.size,
      dataDir: DATA_DIR,
    };
  }

  /**
   * Log an execution event
   */
  logExecution(event) {
    try {
      const logFile = path.join(LOG_DIR, `executions-${new Date().toISOString().slice(0, 10)}.jsonl`);
      const line = JSON.stringify({
        ...event,
        timestamp: new Date().toISOString(),
      }) + '\n';
      fs.appendFileSync(logFile, line);
    } catch (err) {
      logger.warn(`Failed to log execution: ${err.message}`);
    }
  }
}

module.exports = new Persistence();
