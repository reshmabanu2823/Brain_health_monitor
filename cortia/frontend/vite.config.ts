import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8010", ws: true },
      "/docs": { target: "http://127.0.0.1:8010" },
      "/docs-assets": { target: "http://127.0.0.1:8010" },
      "/openapi.json": { target: "http://127.0.0.1:8010" },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: { charts: ["recharts"] },
      },
    },
  },
});
