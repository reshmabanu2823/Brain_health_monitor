import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  timeout: 60000,
  use: {
    baseURL: "http://127.0.0.1:8011",
    trace: "retain-on-failure",
    launchOptions: process.env.CORTIA_BROWSER
      ? { executablePath: process.env.CORTIA_BROWSER }
      : {},
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "bash ../scripts/e2e-server.sh",
    url: "http://127.0.0.1:8011/api/health",
    reuseExistingServer: false,
    timeout: 60000,
  },
  reporter: "list",
});
