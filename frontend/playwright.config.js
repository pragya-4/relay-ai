import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  use: {
    baseURL: 'http://127.0.0.1:3001',
    browserName: 'chromium',
    launchOptions: {
      executablePath: process.env.CHROME_PATH || undefined,
      args: ['--no-sandbox'],
    },
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 3001',
    url: 'http://127.0.0.1:3001',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
