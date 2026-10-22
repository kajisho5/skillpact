import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
const REPO = process.env.SKILLPACT_REPO || path.resolve(__dirname, "..");
export default defineConfig({
  base: "/skillpact/",
  plugins: [react()],
  build: { assetsInlineLimit: 0 },
  resolve: { alias: { "@": path.resolve(__dirname, "src"), "@repo": REPO } },
  server: { fs: { allow: [__dirname, REPO] } },
  ssgOptions: { dirStyle: "nested", formatting: "none", entry: "src/main.tsx" },
});
