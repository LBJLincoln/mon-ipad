/**
 * Browser utility — Puppeteer-based scraping for JS-rendered sources.
 *
 * Uses Google Chrome installed via apt in Dockerfile.
 * Lazy-initialized: browser only launches when first needed.
 */
const puppeteer = require('puppeteer-core');
const logger = require('./logger');

let browser = null;

async function getBrowser() {
  if (browser && browser.connected) return browser;

  browser = await puppeteer.launch({
    executablePath: process.env.CHROME_BIN || '/usr/bin/google-chrome-stable',
    headless: 'shell',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--no-first-run',
      '--no-zygote',
      '--single-process',
      '--disable-extensions',
    ],
  });

  logger.info('[BROWSER] Chrome launched');
  return browser;
}

async function scrape(url, options = {}) {
  const { waitFor, timeout = 15000, extractFn } = options;
  const b = await getBrowser();
  const page = await b.newPage();

  try {
    await page.setUserAgent('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36');
    await page.goto(url, { waitUntil: 'networkidle2', timeout });

    if (waitFor) {
      await page.waitForSelector(waitFor, { timeout: timeout / 2 });
    }

    if (extractFn) {
      return await page.evaluate(extractFn);
    }

    return await page.content();
  } finally {
    await page.close();
  }
}

async function closeBrowser() {
  if (browser) {
    await browser.close();
    browser = null;
    logger.info('[BROWSER] Chrome closed');
  }
}

module.exports = { getBrowser, scrape, closeBrowser };
