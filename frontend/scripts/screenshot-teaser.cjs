#!/usr/bin/env node
// Render assets/teaser.html → assets/teaser.png at 1200×630.
// The aito-demo-server landing page sources thumbnails from each demo's
// assets/teaser.png at deploy time. Re-run this whenever teaser.html changes.
//
// Usage: node frontend/scripts/screenshot-teaser.cjs

const { chromium } = require("playwright-core");
const path = require("path");
const fs = require("fs");

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const SRC = path.join(REPO_ROOT, "assets", "teaser.html");
// Two destinations from one source: the landing-page thumbnail and the
// og:image the page itself points at. They were drifting when maintained
// separately, and a stale OG card is invisible until someone shares a link.
const OUTS = [
  path.join(REPO_ROOT, "assets", "teaser.png"),
  path.join(REPO_ROOT, "frontend", "public", "og.png"),
];

async function main() {
  if (!fs.existsSync(SRC)) {
    console.error(`✗ source not found: ${SRC}`);
    process.exit(1);
  }
  const executablePath = process.env.CHROME_PATH ||
    (process.platform === "darwin"
      ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
      : process.platform === "linux"
        ? "/usr/bin/chromium" // override with CHROME_PATH if installed elsewhere
        : undefined);

  let browser;
  try {
    browser = await chromium.launch({ executablePath, headless: true });
  } catch (e) {
    console.error(`✗ chromium launch failed: ${e.message}`);
    console.error(`  Set CHROME_PATH to your Chrome/Chromium binary, or install playwright (not playwright-core) to bundle browsers.`);
    process.exit(1);
  }

  const ctx = await browser.newContext({
    viewport: { width: 1200, height: 630 },
    deviceScaleFactor: 1,
  });
  const page = await ctx.newPage();
  await page.goto(`file://${SRC}`, { waitUntil: "networkidle" });
  for (const out of OUTS) {
    fs.mkdirSync(path.dirname(out), { recursive: true });
    await page.screenshot({ path: out, type: "png", omitBackground: false });
    const stat = fs.statSync(out);
    console.log(`✓ ${path.relative(REPO_ROOT, out)} (${stat.size} B, 1200×630)`);
  }
  await browser.close();
}

main().catch((e) => {
  console.error(`✗ ${e.stack || e.message}`);
  process.exit(1);
});
