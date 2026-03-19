/**
 * Browser utility — Puppeteer-based scraping + form filling + automation.
 *
 * Uses Chromium from Debian apt (installed in Dockerfile).
 * Lazy-initialized: browser only launches when first needed.
 *
 * Capabilities:
 *   - scrape(url)        — fetch JS-rendered pages
 *   - fillForm(url, fields, submitSelector) — fill forms and submit
 *   - screenshot(url)    — take page screenshot
 *   - executeScript(url, script) — run arbitrary JS on a page
 *   - triggerKaggle(kernelId) — push Kaggle kernel for GPU execution
 */
const puppeteer = require('puppeteer-core');
const logger = require('./logger');

let browser = null;

async function getBrowser() {
  if (browser && browser.connected) return browser;

  browser = await puppeteer.launch({
    executablePath: process.env.CHROME_BIN || '/usr/bin/chromium',
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

  logger.info('[BROWSER] Chromium launched');
  return browser;
}

/**
 * Scrape a URL — returns HTML content or extracted data.
 */
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

/**
 * Fill a form on a page and submit it.
 *
 * @param {string} url - Page URL
 * @param {Object} fields - Map of CSS selector → value to type
 * @param {string} submitSelector - CSS selector for submit button
 * @param {Object} options - { timeout, waitAfterSubmit, cookies }
 * @returns {Object} { success, responseUrl, responseText, screenshot }
 */
async function fillForm(url, fields, submitSelector, options = {}) {
  const { timeout = 30000, waitAfterSubmit = 3000, cookies } = options;
  const b = await getBrowser();
  const page = await b.newPage();

  try {
    await page.setUserAgent('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36');

    // Set cookies if provided (for authentication)
    if (cookies && Array.isArray(cookies)) {
      await page.setCookie(...cookies);
    }

    await page.goto(url, { waitUntil: 'networkidle2', timeout });

    // Fill each field
    for (const [selector, value] of Object.entries(fields)) {
      const el = await page.$(selector);
      if (!el) {
        logger.warn(`[BROWSER] Form field not found: ${selector}`);
        continue;
      }

      // Clear existing value
      await el.click({ clickCount: 3 });
      await el.type(value, { delay: 20 });
      logger.debug(`[BROWSER] Filled ${selector}`);
    }

    // Submit
    if (submitSelector) {
      await page.click(submitSelector);
      logger.info(`[BROWSER] Form submitted via ${submitSelector}`);
    }

    // Wait for navigation or timeout
    try {
      await page.waitForNavigation({ timeout: waitAfterSubmit });
    } catch {
      // Navigation may not happen (AJAX form)
    }

    const responseUrl = page.url();
    const responseText = await page.content();
    const screenshot = await page.screenshot({ encoding: 'base64', type: 'jpeg', quality: 50 });

    return {
      success: true,
      responseUrl,
      responseText: responseText.substring(0, 5000),
      screenshot: `data:image/jpeg;base64,${screenshot}`,
    };
  } catch (err) {
    logger.warn(`[BROWSER] Form fill failed: ${err.message}`);
    return { success: false, error: err.message };
  } finally {
    await page.close();
  }
}

/**
 * Take a screenshot of a page.
 */
async function screenshot(url, options = {}) {
  const { timeout = 15000, fullPage = true } = options;
  const b = await getBrowser();
  const page = await b.newPage();

  try {
    await page.setViewport({ width: 1280, height: 800 });
    await page.goto(url, { waitUntil: 'networkidle2', timeout });
    const img = await page.screenshot({ encoding: 'base64', type: 'jpeg', quality: 70, fullPage });
    return `data:image/jpeg;base64,${img}`;
  } finally {
    await page.close();
  }
}

/**
 * Execute arbitrary JavaScript on a page and return the result.
 */
async function executeScript(url, script, options = {}) {
  const { timeout = 15000, waitFor } = options;
  const b = await getBrowser();
  const page = await b.newPage();

  try {
    await page.goto(url, { waitUntil: 'networkidle2', timeout });
    if (waitFor) await page.waitForSelector(waitFor, { timeout: timeout / 2 });
    const result = await page.evaluate(script);
    return result;
  } finally {
    await page.close();
  }
}

/**
 * Trigger a Kaggle kernel push via VM SSH (since kaggle CLI needs auth).
 * Eve calls this to auto-trigger GPU experiment runs on Kaggle.
 */
async function triggerKaggle(vmBridge, kernelPath = '/home/termius/nomos-nba-agent/kaggle') {
  if (!vmBridge) {
    logger.warn('[BROWSER] No VM bridge — cannot trigger Kaggle');
    return { success: false, error: 'No VM bridge' };
  }

  try {
    const result = await vmBridge.execute(
      `source /home/termius/mon-ipad/.env.local && cd ${kernelPath} && kaggle kernels push -p . 2>&1`
    );
    logger.info(`[BROWSER] Kaggle kernel pushed: ${result.substring(0, 200)}`);
    return { success: true, output: result };
  } catch (err) {
    logger.warn(`[BROWSER] Kaggle trigger failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

async function closeBrowser() {
  if (browser) {
    await browser.close();
    browser = null;
    logger.info('[BROWSER] Chromium closed');
  }
}

module.exports = { getBrowser, scrape, fillForm, screenshot, executeScript, triggerKaggle, closeBrowser };
