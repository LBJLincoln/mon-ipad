/**
 * A2A Protocol — Adam ↔ Eve Bidirectional Communication
 *
 * Structured message protocol between:
 *   Adam (Claude Code CLI on VM) → sends COMMANDS
 *   Eve (OpenClaw on HF Space)   → sends REPORTS, ALERTS, DATA
 *
 * Message Types:
 *   COMMAND   — Adam → Eve: "do this" (execute, fetch, restart)
 *   REPORT    — Eve → Adam: "here's what I observed"
 *   ALERT     — Eve → Adam: "something needs attention"
 *   DATA      — Eve → Adam: "here's new data I collected"
 *   ACK       — Bidirectional: "received your message"
 *
 * Endpoints (added to server.js):
 *   POST /api/v1/a2a/command     — Adam sends a command
 *   GET  /api/v1/a2a/inbox       — Adam reads Eve's reports
 *   GET  /api/v1/a2a/status      — Protocol status
 *   POST /api/v1/a2a/ack         — Acknowledge a message
 *
 * Persistence: /data/a2a/
 */

const fs = require('fs');
const path = require('path');
const logger = require('./logger');

const A2A_DIR = '/data/a2a';
const COMMANDS_FILE = path.join(A2A_DIR, 'commands.json');
const REPORTS_FILE = path.join(A2A_DIR, 'reports.json');
const INBOX_FILE = path.join(A2A_DIR, 'inbox.json');

class A2AProtocol {
  constructor({ onCommand }) {
    this.onCommand = onCommand; // Callback: (command) => result

    // Command queue (Adam → Eve)
    this.commands = [];

    // Reports/Alerts (Eve → Adam)
    this.inbox = [];

    // Stats
    this.stats = {
      commandsReceived: 0,
      commandsExecuted: 0,
      commandsFailed: 0,
      reportsPosted: 0,
      alertsPosted: 0,
      lastCommandAt: null,
      lastReportAt: null,
    };

    this._load();
  }

  // ══════════════════════════════════════════
  //  COMMANDS — Adam → Eve
  // ══════════════════════════════════════════

  /**
   * Receive a command from Adam.
   * Execute immediately and return result.
   */
  async receiveCommand(command) {
    const id = `cmd_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const entry = {
      id,
      type: 'COMMAND',
      action: command.action,
      params: command.params || {},
      source: 'adam',
      receivedAt: new Date().toISOString(),
      status: 'executing',
      result: null,
    };

    this.commands.push(entry);
    this.stats.commandsReceived++;
    this.stats.lastCommandAt = entry.receivedAt;

    logger.info(`[A2A] Command received: ${command.action} (${id})`);

    // Execute
    try {
      const result = await this.onCommand(command);
      entry.status = 'completed';
      entry.result = result;
      entry.completedAt = new Date().toISOString();
      this.stats.commandsExecuted++;
      logger.info(`[A2A] Command completed: ${command.action} (${id})`);
    } catch (err) {
      entry.status = 'failed';
      entry.result = { error: err.message };
      entry.completedAt = new Date().toISOString();
      this.stats.commandsFailed++;
      logger.error(`[A2A] Command failed: ${command.action}: ${err.message}`);
    }

    // Trim queue
    if (this.commands.length > 200) this.commands = this.commands.slice(-200);
    this._save();

    return entry;
  }

  /**
   * Get command history (for Adam to check results)
   */
  getCommands(limit = 20) {
    return this.commands.slice(-limit).reverse();
  }

  // ══════════════════════════════════════════
  //  REPORTS — Eve → Adam
  // ══════════════════════════════════════════

  /**
   * Post a report from Eve for Adam to read.
   * Called by watchdog, data-worker, etc.
   */
  postReport(report) {
    const entry = {
      id: `rpt_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      type: report.type || 'REPORT',
      level: report.level || 'INFO',
      message: report.message || '',
      data: report.data || {},
      source: 'eve',
      createdAt: new Date().toISOString(),
      read: false,
    };

    this.inbox.push(entry);
    this.stats.reportsPosted++;
    this.stats.lastReportAt = entry.createdAt;

    if (entry.level === 'CRITICAL' || entry.level === 'WARNING') {
      this.stats.alertsPosted++;
    }

    // Trim inbox
    if (this.inbox.length > 500) this.inbox = this.inbox.slice(-500);

    // Periodic save (don't save every single report)
    if (this.stats.reportsPosted % 5 === 0) {
      this._save();
    }

    return entry;
  }

  /**
   * Get Eve's inbox (for Adam to read).
   * Options: { unread: true, limit: 50, level: 'CRITICAL' }
   */
  getInbox(options = {}) {
    let items = [...this.inbox];

    if (options.unread) {
      items = items.filter(i => !i.read);
    }

    if (options.level) {
      items = items.filter(i => i.level === options.level);
    }

    if (options.type) {
      items = items.filter(i => i.type === options.type);
    }

    if (options.since) {
      items = items.filter(i => new Date(i.createdAt) > new Date(options.since));
    }

    const limit = options.limit || 50;
    return items.slice(-limit).reverse();
  }

  /**
   * Mark messages as read.
   */
  acknowledge(messageIds) {
    let count = 0;
    for (const msg of this.inbox) {
      if (messageIds.includes(msg.id)) {
        msg.read = true;
        count++;
      }
    }
    this._save();
    return { acknowledged: count };
  }

  /**
   * Mark all as read.
   */
  acknowledgeAll() {
    let count = 0;
    for (const msg of this.inbox) {
      if (!msg.read) {
        msg.read = true;
        count++;
      }
    }
    this._save();
    return { acknowledged: count };
  }

  // ══════════════════════════════════════════
  //  STRUCTURED REPORTS — Eve auto-generates
  // ══════════════════════════════════════════

  /**
   * Generate a structured evolution report.
   * Called periodically by the agentic loop.
   */
  postEvolutionReport(evoData) {
    return this.postReport({
      type: 'evolution_status',
      level: 'INFO',
      message: `Gen ${evoData.generation}: Brier ${evoData.brier?.toFixed(4)}, ${evoData.features} features, stagnation ${evoData.stagnation}`,
      data: evoData,
    });
  }

  /**
   * Post data collection report.
   */
  postDataReport(dataType, data) {
    return this.postReport({
      type: 'data_collection',
      level: 'INFO',
      message: `${dataType} data collected: ${JSON.stringify(data).substring(0, 100)}`,
      data: { dataType, ...data },
    });
  }

  // ══════════════════════════════════════════
  //  STATUS
  // ══════════════════════════════════════════

  getStatus() {
    const unread = this.inbox.filter(i => !i.read).length;
    const pending = this.commands.filter(c => c.status === 'executing').length;

    return {
      stats: this.stats,
      unreadInbox: unread,
      pendingCommands: pending,
      totalInbox: this.inbox.length,
      totalCommands: this.commands.length,
      recentCommands: this.commands.slice(-5).reverse(),
      recentReports: this.inbox.slice(-5).reverse(),
    };
  }

  // ══════════════════════════════════════════
  //  PERSISTENCE
  // ══════════════════════════════════════════

  _load() {
    try {
      if (!fs.existsSync(A2A_DIR)) fs.mkdirSync(A2A_DIR, { recursive: true });

      if (fs.existsSync(COMMANDS_FILE)) {
        this.commands = JSON.parse(fs.readFileSync(COMMANDS_FILE, 'utf8'));
      }
      if (fs.existsSync(INBOX_FILE)) {
        this.inbox = JSON.parse(fs.readFileSync(INBOX_FILE, 'utf8'));
      }
    } catch (e) {
      logger.warn(`[A2A] Load state: ${e.message}`);
    }
  }

  _save() {
    try {
      fs.writeFileSync(COMMANDS_FILE, JSON.stringify(this.commands.slice(-200), null, 2));
      fs.writeFileSync(INBOX_FILE, JSON.stringify(this.inbox.slice(-500), null, 2));
    } catch (e) {
      logger.warn(`[A2A] Save state: ${e.message}`);
    }
  }
}

module.exports = A2AProtocol;
