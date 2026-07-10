// Drive a single prediction in a headless browser and screenshot the
// full result panel. Used for visual regression on the demo's primary
// flow.
const { chromium } = require("playwright-core");
const path = require("path");

const BASE = (process.env.BASE_URL || "http://localhost:3000").replace(/\/$/, "");
const OUT = path.resolve(__dirname, "output", "predict-result.png");

const TITLE = process.argv[2] || "Show HN: a tiny Postgres client written in Rust";

(async () => {
  const executablePath = process.env.CHROME_PATH ||
    (process.platform === "linux" ? "/usr/bin/chromium" : undefined);
  const browser = await chromium.launch({ executablePath, headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1100 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto(BASE, { waitUntil: "networkidle" });

  // Type into the title input
  await page.fill(".hn-title-input", TITLE);

  // Click Predict
  await Promise.all([
    page.waitForResponse(r => r.url().includes("/api/predict-hn")),
    page.click(".hn-submit-btn"),
  ]);

  // Wait for the predicted-story entry to render
  await page.waitForSelector(".hn-story-prediction", { timeout: 8000 });
  await page.waitForTimeout(400);

  await page.screenshot({ path: OUT, fullPage: true });
  console.log(`✓ ${BASE} (predict: ${TITLE}) → ${OUT}`);
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
