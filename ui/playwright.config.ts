import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  retries: 0,
  use: { baseURL: process.env.BASE_URL || "http://localhost:5173", trace: "off" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run preview",
    port: 5173,
    reuseExistingServer: !process.env.CI
  }
});
