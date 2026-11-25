import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiTarget = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/auth": apiTarget,
      "/chat": apiTarget,
      "/health": apiTarget,
      "/orders": apiTarget,
      "/samples": apiTarget,
      "/conversations": apiTarget,
      "/memory": apiTarget,
      "/usage": apiTarget,
      "/admin": apiTarget,
      "/risk": apiTarget,
    },
  },
});
