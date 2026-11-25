import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

async function readDemoCatalog() {
  const { DatabaseSync } = await import("node:sqlite");
  const database = new DatabaseSync(":memory:");
  try {
    database.exec(readFileSync(new URL("./schema.sql", import.meta.url), "utf8"));
    return database.prepare("SELECT id, name, price, stock FROM products ORDER BY id").all();
  } finally {
    database.close();
  }
}

export default defineConfig(async ({ mode }) => {
  const pages = mode === "pages";
  return {
    root: fileURLToPath(new URL("./web/", import.meta.url)),
    plugins: [vue()],
    base: pages ? "./" : "/",
    build: { outDir: pages ? "dist-pages" : "dist" },
    define: {
      __PAGES_CATALOG__: JSON.stringify(pages ? await readDemoCatalog() : []),
    },
    server: {
      host: "127.0.0.1",
      proxy: {
        "/api": `http://127.0.0.1:${process.env.FURNITURE_PORT || "8000"}`,
      },
    },
  };
});
