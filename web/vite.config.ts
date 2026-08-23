import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base so the built bundle can be served from any subdirectory,
// which is how these maps usually end up being published.
export default defineConfig({
  base: "./",
  plugins: [react()],
});
