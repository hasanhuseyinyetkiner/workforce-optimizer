import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const shots = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../docs/screenshots");

test.describe("portfolio screenshots", () => {
  test("capture overview / solve / schedule / validate / scenarios", async ({ page, request }) => {
    // Ensure two labeled schedules exist for scenario compare.
    await request.post("http://127.0.0.1:8103/api/demo/load", {
      data: { scenario: "feasible" },
    });
    for (const label of ["docs-baseline", "docs-candidate"]) {
      const created = await request.post("http://127.0.0.1:8103/api/optimization-runs", {
        data: { mode: "reproducible", random_seed: label === "docs-baseline" ? 1 : 42, label },
      });
      expect(created.ok()).toBeTruthy();
      const body = await created.json();
      for (let i = 0; i < 90; i++) {
        await page.waitForTimeout(1000);
        const run = await (await request.get(`http://127.0.0.1:8103/api/optimization-runs/${body.id}`)).json();
        if (["SUCCEEDED", "FAILED", "CANCELLED"].includes(run.status)) {
          expect(run.solver_status).toMatch(/OPTIMAL|FEASIBLE/);
          break;
        }
      }
    }

    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto("/");
    await expect(page.getByRole("heading", { name: /Overview/i })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/FEASIBLE|OPTIMAL/i).first()).toBeVisible({ timeout: 30_000 });
    // Recharts paints asynchronously; wait for at least one bar path.
    await expect(page.locator(".recharts-bar-rectangle path").first()).toBeVisible({ timeout: 15_000 });
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(shots, "overview.png"), fullPage: true });

    await page.goto("/solve");
    await expect(page.getByRole("heading", { name: "Solve" })).toBeVisible();
    await expect(page.getByTestId("run-solve")).toBeVisible();
    await page.screenshot({ path: path.join(shots, "solve.png"), fullPage: true });

    await page.goto("/schedule");
    await expect(page.getByRole("heading", { name: "Schedule" })).toBeVisible();
    await expect(page.getByText(/Validator summary/i)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/Day|Evening|Night/i).first()).toBeVisible();
    await page.screenshot({ path: path.join(shots, "schedule.png"), fullPage: true });

    await page.getByTestId("revalidate").click();
    await expect(page.getByText(/No hard-constraint violations/i).first()).toBeVisible();
    await expect(page.getByText(/^Valid$/).first()).toBeVisible();
    await page.screenshot({ path: path.join(shots, "validate.png"), fullPage: true });

    await page.goto("/scenarios");
    await expect(page.getByRole("heading", { name: "Scenarios" })).toBeVisible();
    const schedules = await (await request.get("http://127.0.0.1:8103/api/schedules")).json();
    expect(schedules.length).toBeGreaterThanOrEqual(2);
    const left = schedules[0].id;
    const right = schedules[1].id;
    await page.getByTestId("compare-left").selectOption(String(left));
    await page.getByTestId("compare-right").selectOption(String(right));
    await expect(page.getByTestId("compare-result")).toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: path.join(shots, "scenarios.png"), fullPage: true });
  });
});
