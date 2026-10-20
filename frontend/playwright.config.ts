import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const backend = path.join(root, "backend");
const e2eDb = path.join(backend, "data", "e2e-workforce.db").replace(/\\/g, "/");

export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:5103",
    trace: "on-first-retry",
  },
  webServer: [
    {
      command: "uv run python -m app.cli",
      cwd: backend,
      url: "http://127.0.0.1:8103/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        ...process.env,
        APP_ENV: "demo",
        HOST: "127.0.0.1",
        PORT: "8103",
        ALLOW_NETWORK_BIND: "false",
        RESET_DEMO: "true",
        DATABASE_URL: `sqlite:///${e2eDb}`,
        SOLVER_NUM_WORKERS: "2",
      },
    },
    {
      command: "pnpm dev",
      url: "http://127.0.0.1:5103",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
