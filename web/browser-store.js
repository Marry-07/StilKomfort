const catalog = __PAGES_CATALOG__;
const productsById = new Map(catalog.map((product) => [product.id, product]));

function storageKey() {
  return `stilkomfort:${new URL("./", window.location.href).pathname}:sales-v1`;
}

function readState() {
  const saved = localStorage.getItem(storageKey());
  return saved ? JSON.parse(saved) : { stock: {}, sales: [] };
}

function saveSale(cart) {
  if (!cart.size) {
    throw new Error("Добавьте товары в корзину.");
  }
  const { stock, sales } = readState();
  let total = 0;
  let quantity = 0;
  for (const [id, count] of cart) {
    if (!Number.isSafeInteger(count) || count <= 0) {
      throw new Error("Укажите положительное количество товара.");
    }
    const product = productsById.get(id);
    if (!product) {
      throw new Error("Товар отсутствует в каталоге.");
    }
    const available = stock[id] ?? product.stock;
    if (count > available) {
      throw new Error("Товаров не хватает. Проверьте остатки.");
    }
    stock[id] = available - count;
    total += product.price * count;
    quantity += count;
  }
  const id = (sales[0]?.id ?? 0) + 1;
  sales.unshift({ id, createdAt: new Date().toISOString(), quantity, total });
  try {
    localStorage.setItem(storageKey(), JSON.stringify({ stock, sales }));
  } catch {
    throw new Error("Не удалось сохранить продажу в этом браузере.");
  }
  return { id, total };
}

export const browserStore = {
  async catalog() {
    const { stock } = readState();
    return catalog.map((product) => ({ ...product, stock: stock[product.id] ?? product.stock }));
  },
  async history() {
    return readState().sales;
  },
  async sell(cart) {
    if (navigator.locks) {
      return navigator.locks.request(storageKey(), () => saveSale(cart));
    }
    return saveSale(cart);
  },
};
