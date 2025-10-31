/**
 * Playwright screenshot script for UI testing
 * Captures screenshots of dashboard pages to verify UI improvements
 */

import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SCREENSHOT_DIR = path.join(__dirname, '../screenshots');
const PORT = process.env.PORT || 5173;
const BASE_URL = `http://localhost:${PORT}`;

async function takeScreenshot(page, url, filename, options = {}) {
  try {
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000); // Wait for animations
    
    const screenshotPath = path.join(SCREENSHOT_DIR, filename);
    await page.screenshot({
      path: screenshotPath,
      fullPage: options.fullPage !== false,
      ...options
    });
    
    console.log(`✅ Screenshot saved: ${filename}`);
    return screenshotPath;
  } catch (error) {
    console.error(`❌ Failed to capture ${filename}:`, error.message);
    throw error;
  }
}

async function main() {
  // Create screenshots directory
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
    console.log(`📁 Created directory: ${SCREENSHOT_DIR}`);
  }

  console.log(`🚀 Starting Playwright screenshot capture...`);
  console.log(`📍 Target URL: ${BASE_URL}`);

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 2, // High DPI for better quality
  });

  const page = await context.newPage();

  try {
    // Wait for server to be ready
    console.log('⏳ Waiting for server to be ready...');
    let serverReady = false;
    for (let i = 0; i < 30; i++) {
      try {
        const response = await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 5000 });
        if (response && response.status() < 400) {
          serverReady = true;
          break;
        }
      } catch (e) {
        // Server not ready yet
      }
      await new Promise(resolve => setTimeout(resolve, 1000));
    }

    if (!serverReady) {
      throw new Error('Server is not responding. Make sure the dev server is running on port ' + PORT);
    }

    console.log('✅ Server is ready!\n');

    // Screenshot: Dashboard
    await takeScreenshot(
      page,
      `${BASE_URL}/`,
      'dashboard-full.png',
      { fullPage: true }
    );

    // Screenshot: Dashboard (viewport only)
    await takeScreenshot(
      page,
      `${BASE_URL}/`,
      'dashboard-viewport.png',
      { fullPage: false }
    );

    // Screenshot: Enrichment Dashboard
    await takeScreenshot(
      page,
      `${BASE_URL}/enrichment`,
      'enrichment-dashboard-full.png',
      { fullPage: true }
    );

    // Screenshot: Enrichment Dashboard (viewport)
    await takeScreenshot(
      page,
      `${BASE_URL}/enrichment`,
      'enrichment-dashboard-viewport.png',
      { fullPage: false }
    );

    // Mobile viewport
    const mobileContext = await browser.newContext({
      viewport: { width: 375, height: 667 }, // iPhone SE
      deviceScaleFactor: 2,
    });
    const mobilePage = await mobileContext.newPage();
    
    await takeScreenshot(
      mobilePage,
      `${BASE_URL}/`,
      'dashboard-mobile.png',
      { fullPage: true }
    );

    await mobilePage.close();
    await mobileContext.close();

    console.log(`\n✨ All screenshots captured successfully!`);
    console.log(`📂 Screenshots saved in: ${SCREENSHOT_DIR}\n`);

  } catch (error) {
    console.error('❌ Error during screenshot capture:', error);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

// Run if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

export { takeScreenshot, main };

