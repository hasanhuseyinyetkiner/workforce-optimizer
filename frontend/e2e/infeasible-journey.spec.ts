import { expect, test } from "@playwright/test";

test("INFEASIBLE scenario → conflict groups, no fabricated roster on solve", async ({ page }) => {
  await page.goto("/scenarios");
  await expect(page.getByRole("heading", { name: "Scenarios" })).toBeVisible();
  await page.getByTestId("scenario-infeasible").click();
  await expect(page.getByTestId("scenario-timing")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("scenario-timing")).toContainText("INFEASIBLE");

  await page.goto("/solve");
  await page.getByTestId("run-solve").click();
  await expect(page.getByTestId("solver-telemetry")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("solver-telemetry")).toContainText("INFEASIBLE");
  await expect(page.getByTestId("solver-telemetry")).toContainText("none");
  await expect(page.getByText(/no assignment satisfies the configured hard rules/i)).toBeVisible();
  await expect(page.getByTestId("diagnostics-iis-disclaimer")).toBeVisible();
  await expect(page.getByText(/Conflicting hard-constraint groups/i)).toBeVisible();
  await expect(page.getByText(/Skill requirements/i)).toBeVisible();
  await expect(page.getByText(/Objective breakdown/i)).toBeVisible();
  await expect(page.getByText(/No breakdown available for this run/i)).toBeVisible();
});
