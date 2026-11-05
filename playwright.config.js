const { defineConfig } = require('@playwright/test');
const path = require('path');
// Each test run gets a new database; no operational history is deleted.
const db = path.join(__dirname, '.runtime', `ui-${Date.now()}.sqlite`);
module.exports = defineConfig({
  testDir: './tests', testMatch: ['**/ui.spec.js', '**/ui.integration.spec.js'], workers: 1, fullyParallel: false,
  timeout: 45000, expect: { timeout: 10000 },
  use: { baseURL: 'http://127.0.0.1:8766', browserName: 'chromium', viewport: { width: 1440, height: 1000 }, trace: 'retain-on-failure' },
  webServer: { command: `py -3 app.py --port 8766 --db "${db}"`, url: 'http://127.0.0.1:8766/api/health', reuseExistingServer: false, timeout: 30000 },
  reporter: [['list']]
});
