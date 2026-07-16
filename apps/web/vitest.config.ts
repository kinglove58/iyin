import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { environment: "jsdom", setupFiles: ["./vitest.setup.ts"], include: ["**/*.test.tsx"] },
  resolve: { alias: { "@": new URL(".", import.meta.url).pathname } }
});
