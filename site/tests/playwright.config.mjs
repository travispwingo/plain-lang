import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.mjs",
  timeout: 60_000,
  use: { baseURL: "http://localhost:8123" },
  webServer: {
    command: "python3 ../build.py --serve --port 8123",
    url: "http://localhost:8123",
    timeout: 120_000,
    reuseExistingServer: false,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
});
