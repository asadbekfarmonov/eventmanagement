const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:8000',
    headless: true,
  },
  webServer: {
    command: '.venv/bin/python tests/e2e_server.py',
    url: 'http://127.0.0.1:8000/health',
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
