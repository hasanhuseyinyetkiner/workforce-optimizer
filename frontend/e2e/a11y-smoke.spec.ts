import { expect, test } from "@playwright/test";

test("a11y smoke: landmarks, skip link, and primary nav", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Overview/i })).toBeVisible({ timeout: 30_000 });

  const skip = page.getByRole("link", { name: /Skip to main content/i });
  await expect(skip).toBeAttached();
  await skip.focus();
  await expect(skip).toBeFocused();

  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.locator("#main")).toBeVisible();
  await expect(page.getByTestId("demo-banner")).toBeVisible();
  await expect(page.getByTestId("theme-toggle")).toHaveAttribute("aria-pressed", /true|false/);

  for (const label of ["Employees", "Shifts", "Rules", "Solve", "Schedule", "Scenarios"]) {
    await expect(page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: label })).toBeVisible();
  }
});
