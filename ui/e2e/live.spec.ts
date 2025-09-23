import { test, expect } from '@playwright/test'
test('loads /live and shows header', async ({ page }) => {
  await page.goto('http://localhost:4173/live')
  await expect(page.locator('text=Entropy Lab')).toBeVisible()
})
