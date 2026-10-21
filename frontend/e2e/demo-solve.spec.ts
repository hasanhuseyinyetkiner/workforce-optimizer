import { expect, test } from "@playwright/test";

test("demo → solve → validate → export", async ({ page }) => {
  await page.goto("/scenarios");
  await expect(page.getByRole("heading", { name: "Scenarios" })).toBeVisible();
  await page.getByTestId("scenario-feasible").click();
  await expect(page.getByTestId("scenario-timing")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("scenario-timing")).toContainText(/FEASIBLE|OPTIMAL/);

  await page.goto("/solve");
  await page.getByTestId("run-solve").click();
  await expect(page.getByTestId("solver-telemetry")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("solver-telemetry")).toContainText(/OPTIMAL|FEASIBLE/);
  await expect(page.getByTestId("solver-telemetry")).toContainText(/ms/);

  await page.goto("/schedule");
  await expect(page.getByRole("heading", { name: "Schedule" })).toBeVisible();
  await expect(page.getByText(/Valid|violation/i).first()).toBeVisible();
  await page.getByTestId("revalidate").click();
  await expect(page.getByText(/No hard-constraint violations|violation/i).first()).toBeVisible();

  const csv = page.getByTestId("export-csv");
  const ics = page.getByTestId("export-ics");
  await expect(csv).toHaveAttribute("href", /export\.csv$/);
  await expect(ics).toHaveAttribute("href", /export\.ics$/);

  const csvResponse = await page.request.get((await csv.getAttribute("href"))!);
  expect(csvResponse.ok()).toBeTruthy();
  expect(await csvResponse.text()).toContain("employee_alias");
});
