import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5103,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8103",
      "/health": "http://127.0.0.1:8103",
      "/ready": "http://127.0.0.1:8103",
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 5103,
    strictPort: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    include: ["src/**/*.test.tsx", "src/**/*.test.ts"],
  },
});
