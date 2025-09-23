import { expect, test } from "@playwright/test";

test("renders dashboard headline and status card", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Entropy Portfolio Lab/i })).toBeVisible();
  await expect(page.getByRole("status")).toBeVisible();
});

test("updates heartbeat indicator after mock ping", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/waiting/i)).toBeVisible();
  await expect(page.getByText(/connected \(demo heartbeat\)/i)).toBeVisible({ timeout: 7000 });
});
