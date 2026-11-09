const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: 'tests/frontend',
  fullyParallel: true,
  timeout: 30000,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8766',
    viewport: { width: 1000, height: 700 },
  },
  webServer: {
    command: 'node dev/server.js 8766',
    url: 'http://127.0.0.1:8766/dev/harness.html',
    reuseExistingServer: true,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1000, height: 700 } } },
    { name: 'webkit', use: { ...devices['Desktop Safari'], viewport: { width: 1000, height: 700 } } },
  ],
});
