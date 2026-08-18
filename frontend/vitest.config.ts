import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
    // Tier 1 target (Phase 2 architecture): entire frontend unit tier
    // under 30s. Fails loudly instead of silently degrading if this
    // creeps up, so it stays something people actually run on every save.
    testTimeout: 5_000,
  },
});
