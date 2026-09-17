import { defineConfig } from "vite";

// Open MCT ships its worker scripts and themes as files it loads at runtime,
// not as things a bundler can follow. They have to be served verbatim, which
// is what `openmct.setAssetPath()` in src/main.js points at.
//
// `base` is "/" for local work and set to the repository name in CI, because
// GitHub Pages serves a project site under a subdirectory. Everything that
// builds a URL reads `import.meta.env.BASE_URL` rather than assuming the root.
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  server: { port: 5174 },
  build: { outDir: "dist" },
});
