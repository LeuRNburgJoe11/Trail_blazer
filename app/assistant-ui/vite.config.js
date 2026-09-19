import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const proxy = {
  "/api/assistant": { target: "http://127.0.0.1:8766", changeOrigin: false },
};
export default defineConfig({
  plugins: [react()],
  server: { proxy },
  preview: { proxy },
});
