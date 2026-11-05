const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const log = [];
  page.on('console', m => log.push(m.type() + ': ' + m.text()));
  page.on('pageerror', e => log.push('pageerror: ' + e.message));
  page.on('response', r => { if (r.url().includes('/api/')) log.push(r.status() + ' ' + r.url()); });
  await page.route(/tile\.openstreetmap\.org/, r => r.abort());
  await page.goto('http://127.0.0.1:8765/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  log.push('badge=' + await page.textContent('#header-integrity-badge'));
  log.push('btn disabled=' + await page.locator('#btn-submit-shipment').isDisabled());
  console.log(log.join('\n'));
  await browser.close();
})();
