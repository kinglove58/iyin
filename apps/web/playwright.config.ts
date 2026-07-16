import { defineConfig, devices } from "@playwright/test";

const externalBaseUrl = process.env.PLAYWRIGHT_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  reporter: "html",
  use: { baseURL: externalBaseUrl ?? "http://127.0.0.1:3000", trace: "on-first-retry" },
  webServer: externalBaseUrl
    ? undefined
    : { command: "npm run dev", url: "http://127.0.0.1:3000", reuseExistingServer: !process.env.CI },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }]
});
