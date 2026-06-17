import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI
    ? [["github"], ["html", { open: "never", outputFolder: "playwright-report" }], ["list"]]
    : [["list"]],
  outputDir: "test-results",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
    headless: true,
  },
  webServer: {
    command: "npm run build && npm run start -- --hostname 127.0.0.1 --port 3000",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: "chromium",
    },
  ],
});
