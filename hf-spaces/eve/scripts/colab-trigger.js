#!/usr/bin/env node
/**
 * Colab GPU Trigger — Opens Colab notebook and clicks "Run All" via Puppeteer
 *
 * Called by conversation-loop.py when GPU experiments are pending.
 * Uses headless Chromium to automate Google Colab.
 *
 * Usage: node colab-trigger.js [--notebook URL]
 */
'use strict';

const COLAB_NOTEBOOK = process.argv[2] ||
  'https://colab.research.google.com/github/LBJLincoln/nomos-nba-agent/blob/main/colab/nba_gpu_runner.ipynb';

async function triggerColab() {
  let puppeteer;
  try {
    puppeteer = require('puppeteer-core');
  } catch {
    console.error('[colab-trigger] puppeteer-core not installed');
    process.exit(1);
  }

  const execPath = process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium';
  console.log(`[colab-trigger] Launching Chromium: ${execPath}`);
  console.log(`[colab-trigger] Notebook: ${COLAB_NOTEBOOK}`);

  const browser = await puppeteer.launch({
    executablePath: execPath,
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--single-process',
    ],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });

    // Navigate to Colab notebook
    console.log('[colab-trigger] Loading notebook...');
    await page.goto(COLAB_NOTEBOOK, { waitUntil: 'networkidle2', timeout: 60000 });
    await page.waitForTimeout(5000);

    // Check if we need to sign in (Colab works without sign-in for public notebooks)
    const title = await page.title();
    console.log(`[colab-trigger] Page title: ${title}`);

    // Try to click "Runtime" menu → "Run all"
    // Colab's menu: Runtime > Run all (Ctrl+F9)
    console.log('[colab-trigger] Triggering Run All via keyboard shortcut...');
    await page.keyboard.down('Control');
    await page.keyboard.press('F9');
    await page.keyboard.up('Control');
    await page.waitForTimeout(3000);

    // Check for "Run anyway" dialog (appears for notebooks from GitHub)
    try {
      const runAnywayBtn = await page.$('paper-button[dialog-confirm]');
      if (runAnywayBtn) {
        console.log('[colab-trigger] Clicking "Run anyway" confirmation...');
        await runAnywayBtn.click();
        await page.waitForTimeout(2000);
      }
    } catch {
      // No dialog, that's fine
    }

    // Alternative: try clicking through the menu
    try {
      const runtimeMenu = await page.$('#runtime-menu-button');
      if (runtimeMenu) {
        await runtimeMenu.click();
        await page.waitForTimeout(1000);
        // Look for "Run all" menu item
        const menuItems = await page.$$('paper-item');
        for (const item of menuItems) {
          const text = await item.evaluate(el => el.textContent);
          if (text && text.includes('Run all')) {
            console.log('[colab-trigger] Clicking "Run all" from menu...');
            await item.click();
            await page.waitForTimeout(2000);
            break;
          }
        }
      }
    } catch {
      // Menu approach failed, keyboard shortcut should have worked
    }

    // Wait a bit to let execution start
    await page.waitForTimeout(5000);

    // Take a screenshot for verification
    const screenshot = '/tmp/colab-trigger-screenshot.png';
    await page.screenshot({ path: screenshot, fullPage: false });
    console.log(`[colab-trigger] Screenshot saved: ${screenshot}`);

    console.log('[colab-trigger] Colab notebook triggered successfully');
    return true;
  } catch (err) {
    console.error(`[colab-trigger] Error: ${err.message}`);
    return false;
  } finally {
    await browser.close();
  }
}

triggerColab()
  .then(ok => process.exit(ok ? 0 : 1))
  .catch(err => { console.error(err); process.exit(1); });
