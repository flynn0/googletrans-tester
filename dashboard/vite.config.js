import { defineConfig } from "vite";

export default defineConfig({
  // Use relative base './' or repo base '/googletrans-all/' so it works locally and on GitHub Pages
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
