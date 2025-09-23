import { defineConfig, configDefaults } from "vitest/config";
import react from "@vitejs/plugin-react-swc";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  test: {
    environment: "jsdom",
    exclude: [...configDefaults.exclude, "tests/**/*", "e2e/**/*"]
  }
});
