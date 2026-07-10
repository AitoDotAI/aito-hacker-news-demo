#!/usr/bin/env node
// Desktop full-page screenshots — a coarse regression baseline.
// Saves to frontend/scripts/output/desktop-<pathname>.png.
//
// Usage:
//   node frontend/scripts/screenshot-pages.cjs                    # / only
//   node frontend/scripts/screenshot-pages.cjs / /about /pricing  # named pages
//
// Configure: BASE_URL (default http://localhost:3000), CHROME_PATH

const { chromium } = require("playwright-core");
const path = require("path");
const fs = require("fs");

const BASE = (process.env.BASE_URL || "http://localhost:3000").replace(/\/$/, "");
const OUT_DIR = path.resolve(__dirname, "output");

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
    process.exit(1);
  }

  fs.mkdirSync(OUT_DIR, { recursive: true });
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });

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
    const out = path.join(OUT_DIR, `desktop-${slug}.png`);
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
