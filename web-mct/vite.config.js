import { defineConfig } from "vite";

// Open MCT ships its worker scripts and themes as files it loads at runtime,
// not as things a bundler can follow. They have to be served verbatim, which
// is what `openmct.setAssetPath()` in src/main.js points at.
export default defineConfig({
  server: { port: 5174 },
  build: { outDir: "dist" },
});
