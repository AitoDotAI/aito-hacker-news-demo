// Full-page screenshot of /features. Hits the page, waits for the
// per-bucket grid to render (which only appears once /api/category-features
// resolves), then snapshots.
const { chromium } = require("playwright-core");
const path = require("path");

const BASE = (process.env.BASE_URL || "http://localhost:3000").replace(/\/$/, "");
const OUT = path.resolve(__dirname, "output", "features.png");

(async () => {
  const executablePath = process.env.CHROME_PATH ||
    (process.platform === "linux" ? "/usr/bin/chromium" : undefined);
  const browser = await chromium.launch({ executablePath, headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1200 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto(BASE + "/features", { waitUntil: "networkidle" });

  // The grid only renders once data arrives
  await page.waitForSelector(".hn-feat-bucket", { timeout: 15000 });
  await page.waitForTimeout(400);

  await page.screenshot({ path: OUT, fullPage: true });
  console.log(`✓ ${BASE}/features → ${OUT}`);
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
