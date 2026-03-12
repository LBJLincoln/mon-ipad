/**
 * Logger — Structured logging for OpenClaw
 */

const winston = require('winston');

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
    winston.format.printf(({ timestamp, level, message, ...meta }) => {
      const metaStr = Object.keys(meta).length ? ` ${JSON.stringify(meta)}` : '';
      return `[${timestamp}] [${level.toUpperCase()}] ${message}${metaStr}`;
    })
  ),
  transports: [
    new winston.transports.Console(),
  ],
});

// Also log to file if /data is available
try {
  const fs = require('fs');
  fs.mkdirSync('/data/logs', { recursive: true });
  logger.add(new winston.transports.File({
    filename: '/data/logs/openclaw.log',
    maxsize: 5 * 1024 * 1024, // 5MB
    maxFiles: 3,
  }));
} catch {
  // /data may not exist in dev
}

module.exports = logger;
