const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  fs.mkdirSync('.impeccable/review', { recursive: true });
  const browser = await chromium.launch();
  const errors = [];
  const shot = async (page, name) => page.screenshot({ path: `.impeccable/review/${name}.png` });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('http://127.0.0.1:8765', { waitUntil: 'networkidle' });
  await page.waitForTimeout(800);
  await shot(page, 'desktop');
  const near = page.locator('.proximity-alert-btn').first();
  if (await near.count()) { await near.click(); await page.waitForTimeout(900); await shot(page, 'desktop-proximity'); }
  for (const tab of ['shipments', 'review', 'lab', 'history']) {
    const b = page.locator(`button[data-tab="${tab}"]`);
    if (await b.count()) { await b.click(); await page.waitForTimeout(400); await shot(page, `tab-${tab}`); }
  }
  const m = await browser.newPage({ viewport: { width: 390, height: 844 } });
  m.on('pageerror', e => errors.push(e.message));
  await m.goto('http://127.0.0.1:8765', { waitUntil: 'networkidle' });
  await m.waitForTimeout(800);
  await shot(m, 'mobile');
  await m.screenshot({ path: '.impeccable/review/mobile-full.png', fullPage: true });
  console.log(JSON.stringify({ errors, overflow: await m.evaluate(() => document.documentElement.scrollWidth) }));
  await browser.close();
})();
