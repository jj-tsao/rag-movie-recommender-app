import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";
import tsconfigPaths from "vite-tsconfig-paths";
import netlify from '@netlify/vite-plugin'

export default defineConfig({
  plugins: [react(), tailwind(), tsconfigPaths(), netlify()],
});
