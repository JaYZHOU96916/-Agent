import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests", timeout: 30000, fullyParallel: false,
  use: { baseURL: "http://127.0.0.1:3100", headless: true, screenshot: "only-on-failure" },
  webServer: { command: "npm run start -- --port 3100", url: "http://127.0.0.1:3100", reuseExistingServer: !process.env.CI },
});
