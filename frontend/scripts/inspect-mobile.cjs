#!/usr/bin/env node
// Capture mobile screenshots of the running demo for layout review.
// Saves to frontend/scripts/output/mobile-<pathname>.png so they can be
// reviewed visually and (optionally) committed as a regression baseline.
//
// Usage:
//   node frontend/scripts/inspect-mobile.cjs                   # / only
//   node frontend/scripts/inspect-mobile.cjs / /about /pricing  # named pages
//
// Configure:
//   BASE_URL   default http://localhost:3000 (your `./do dev` frontend)
//   CHROME_PATH override Chrome binary

const { chromium, devices } = require("playwright-core");
const path = require("path");
const fs = require("fs");

const BASE = (process.env.BASE_URL || "http://localhost:3000").replace(/\/$/, "");
const OUT_DIR = path.resolve(__dirname, "output");

const DEVICE = devices["iPhone 13 mini"] || {
  viewport: { width: 375, height: 812 },
  deviceScaleFactor: 3,
  isMobile: true,
  hasTouch: true,
};

async function main() {
  const paths = process.argv.slice(2);
  if (paths.length === 0) paths.push("/");

  const executablePath = process.env.CHROME_PATH ||
    (process.platform === "linux" ? "/usr/bin/chromium" : undefined);

  let browser;
  try {
    browser = await chromium.launch({ executablePath, headless: true });
  } catch (e) {
    console.error(`✗ chromium launch failed: ${e.message}`);
    console.error(`  Set CHROME_PATH or install playwright (bundled browsers).`);
    process.exit(1);
  }

  fs.mkdirSync(OUT_DIR, { recursive: true });
  const ctx = await browser.newContext(DEVICE);

  for (const p of paths) {
    const page = await ctx.newPage();
    const url = `${BASE}${p.startsWith("/") ? p : "/" + p}`;
    try {
      await page.goto(url, { waitUntil: "networkidle", timeout: 15000 });
    } catch (e) {
      console.error(`✗ ${url} — ${e.message}`);
      await page.close();
      continue;
    }
    const slug = p.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "") || "root";
    const out = path.join(OUT_DIR, `mobile-${slug}.png`);
    await page.screenshot({ path: out, fullPage: true });
    const stat = fs.statSync(out);
    console.log(`✓ ${url} → ${path.relative(process.cwd(), out)} (${stat.size} B)`);
    await page.close();
  }

  await browser.close();
}

main().catch((e) => {
  console.error(`✗ ${e.stack || e.message}`);
  process.exit(1);
});
