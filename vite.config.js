import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath } from "node:url";

export default defineConfig({
  root: fileURLToPath(new URL("./web/", import.meta.url)),
  plugins: [vue()],
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": `http://127.0.0.1:${process.env.FURNITURE_PORT || "8000"}`,
    },
  },
});
