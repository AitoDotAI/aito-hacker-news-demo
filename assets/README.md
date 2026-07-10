# Template assets

The platform's landing page (`aito.ai`) expects a `teaser.png` at this path. When you bootstrap a new demo from this template:

1. Replace this file with your demo's own `teaser.png` (recommended: 1200×630, dark navy `#0c0f41` background, purple accent `#7C5CFC`, white sans-serif). Look at `aito-accounting-demo/assets/teaser.png` or `aito-erp-demo/assets/teaser.png` for examples.
2. Optionally include `teaser.html` — the HTML source the PNG was screenshotted from. Easier to iterate on the design that way.

The platform's `landing/thumbnails/<demo-name>.png` is sourced from `assets/teaser.png` of each demo at deploy time. If your `assets/teaser.png` is missing, the landing card falls back to a gradient placeholder letter (the first letter of your demo's `name`).
