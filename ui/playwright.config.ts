import { defineConfig } from '@playwright/test'
export default defineConfig({
  webServer: { command: 'npm run preview', port: 4173, reuseExistingServer: !process.env.CI },
  use: { headless: true }
})
