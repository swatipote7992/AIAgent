import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the browser talks to Vite, and Vite forwards /api to the FastAPI server.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
