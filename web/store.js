import { browserStore } from "./browser-store.js";

export const isPages = import.meta.env.MODE === "pages";

async function request(path, options) {
  let response;
  let body;
  try {
    response = await fetch(path, options);
    body = await response.json();
  } catch {
    throw new Error("Сервер недоступен. Попробуйте ещё раз.");
  }
  if (!response.ok) {
    throw new Error(body.error || "Не удалось выполнить запрос.");
  }
  return body;
}

const serverStore = {
  catalog: () => request("/api/products"),
  history: () => request("/api/sales"),
  sell(cart) {
    return request("/api/sales", {
      method: "POST",
      headers: { "Content-Type": "application/x-furniture-cart" },
      body: [...cart].map(([id, quantity]) => `${id}:${quantity}`).join(" "),
    });
  },
};

export const store = isPages ? browserStore : serverStore;
