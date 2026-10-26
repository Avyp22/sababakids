import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const root = path.dirname(fileURLToPath(import.meta.url));

// A NODE_ENV=development left in the shell would otherwise ship React's dev build.
if (process.argv.includes("build")) process.env.NODE_ENV = "production";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(root, "src") } },
  // Keep the REACT_APP_* names already set on Render/Netlify (read via import.meta.env).
  envPrefix: ["VITE_", "REACT_APP_"],
  server: { port: 3000 },
  build: { outDir: "build" },   // render.yaml / netlify.toml publish "build"
});
