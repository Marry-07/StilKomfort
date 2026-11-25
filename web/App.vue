<script setup>
import { computed, nextTick, onMounted, reactive, ref } from "vue";
import ProductCard from "./ProductCard.vue";
import { categories, photoUrl, withProductPhoto } from "./catalog.js";
import { isPages, store } from "./store.js";

const formatNumber = new Intl.NumberFormat("ru-RU");
const formatDate = new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" });
const money = (value) => `${formatNumber.format(value)} ₽`;

const products = ref(new Map());
const activeCategory = ref("all");
const loadingProducts = ref(true);
const catalogError = ref(false);
const cart = reactive(new Map());
const submitting = ref(false);
const feedback = ref(null);
const cartDialog = ref(null);
const historyDialog = ref(null);
const sales = ref([]);
const historyStatus = ref("");
let historyRequest = 0;

const visibleProducts = computed(() => [...products.value.values()].filter(
  (product) => activeCategory.value === "all" || product.category === activeCategory.value,
));
const cartItems = computed(() => [...cart].map(([id, quantity]) => ({
  product: products.value.get(id),
  quantity,
})));
const cartCount = computed(() => cartItems.value.reduce((count, item) => count + item.quantity, 0));
const cartTotal = computed(() => cartItems.value.reduce(
  (total, { product, quantity }) => total + product.price * quantity, 0,
));
const canCheckout = computed(() => !submitting.value && cartCount.value > 0 &&
  cartItems.value.every(({ product, quantity }) => quantity <= product.stock));

async function refreshProducts() {
  loadingProducts.value = true;
  catalogError.value = false;
  try {
    const catalog = await store.catalog();
    const updated = new Map(catalog.map((product) => [product.id, withProductPhoto(product)]));
    for (const id of cart.keys()) {
      if (!updated.has(id)) {
        cart.delete(id);
      }
    }
    products.value = updated;
  } catch {
    catalogError.value = true;
  } finally {
    loadingProducts.value = false;
  }
}

function changeQuantity(id, change) {
  const quantity = (cart.get(id) || 0) + change;
  if (submitting.value || (change > 0 && quantity > products.value.get(id).stock)) {
    return;
  }
  if (quantity > 0) {
    cart.set(id, quantity);
  } else {
    cart.delete(id);
  }
  feedback.value = null;
}

async function changeCartQuantity(id, change, event) {
  const button = event.currentTarget;
  const row = button.closest(".cart-item");
  changeQuantity(id, change);
  await nextTick();

  if (!row.isConnected) {
    cartDialog.value.querySelector(".close-button").focus();
  } else if (button.disabled) {
    row.querySelector(".decrease").focus();
  }
}

async function checkout() {
  if (!canCheckout.value) {
    return;
  }
  submitting.value = true;
  feedback.value = null;
  try {
    const receipt = await store.sell(cart);
    cart.clear();
    feedback.value = { message: `Продажа №${receipt.id} оформлена на ${money(receipt.total)}.` };
  } catch (error) {
    feedback.value = { message: error.message, error: true };
  } finally {
    await refreshProducts();
    submitting.value = false;
  }
}

async function openHistory() {
  const currentRequest = ++historyRequest;
  historyStatus.value = "Загружаем продажи…";
  sales.value = [];
  historyDialog.value.showModal();
  try {
    const history = await store.history();
    if (currentRequest === historyRequest) {
      sales.value = history;
      historyStatus.value = history.length ? "" : "Продаж пока нет.";
    }
  } catch (error) {
    if (currentRequest === historyRequest) {
      historyStatus.value = error.message;
    }
  }
}

onMounted(refreshProducts);
</script>

<template>
  <header class="site-header">
    <div class="shell topbar">
      <a class="wordmark" href="#top" aria-label="Форма, начало страницы">StilKomfort<span>.</span></a>
      <nav class="navigation" aria-label="Навигация">
        <a class="nav-catalog" href="#catalog">Каталог</a>
        <button id="open-history" class="text-button" type="button" @click="openHistory">Продажи</button>
      </nav>
      <button
        id="open-cart"
        class="cart-toggle"
        type="button"
        :aria-label="`Корзина, товаров: ${cartCount}`"
        @click="cartDialog.showModal()"
      >
        <span class="bag-icon" aria-hidden="true"></span>
        <span class="cart-toggle-label">Корзина</span>
        <span id="cart-count">{{ cartCount }}</span>
      </button>
    </div>
  </header>

  <main class="shell">
    <section class="hero" aria-labelledby="hero-title">
      <div class="hero-copy">
        <p class="eyebrow">Мебельная жизнь</p>
        <h1 id="hero-title">Пространство<br><em>для комфорта.</em></h1>
        <p class="hero-description">Найдите мебель для дома и соберите покупку из того, что есть в наличии.</p>
        <a class="primary-button" href="#catalog">Смотреть каталог</a>
      </div>
      <div class="hero-visual">
        <img :src="photoUrl('hero')" alt="Оливковый диван и деревянный столик в солнечной гостиной" fetchpriority="high">
        <a class="featured-product" href="#catalog" @click="activeCategory = 'sofas'">Новинка - Диван «Уют»</a>
      </div>
    </section>

    <section id="catalog" class="catalog" aria-labelledby="catalog-title">
      <div class="catalog-heading">
        <h2 id="catalog-title">Каталог мебели</h2>
        <div class="filters" aria-label="Категории мебели" role="group">
          <button
            v-for="{ id, label } in categories"
            :key="id"
            type="button"
            :aria-pressed="activeCategory === id"
            @click="activeCategory = id"
          >{{ label }}</button>
        </div>
      </div>
      <p v-if="loadingProducts" class="catalog-status" role="status">Загружаем каталог…</p>
      <p v-else-if="catalogError" class="catalog-status" role="status">
        Не удалось загрузить каталог.
        <button type="button" class="text-button" @click="refreshProducts">Повторить</button>
      </p>
      <p v-else-if="!visibleProducts.length" class="catalog-status" role="status">В этой категории пока нет товаров.</p>
      <div id="products" class="product-grid">
        <ProductCard
          v-for="product in visibleProducts"
          :key="product.id"
          :product="product"
          :price="money(product.price)"
          :disabled="submitting || (cart.get(product.id) || 0) >= product.stock"
          @add="changeQuantity($event, 1)"
        />
      </div>
    </section>
  </main>

  <footer class="site-footer">
    <div class="shell footer-content">
      <a class="wordmark" href="#top" aria-label="Форма, начало страницы">StilKomfort<span>.</span></a>
      <span>Магазин мебели</span>
    </div>
  </footer>

  <dialog ref="cartDialog" id="cart-dialog" class="drawer" aria-labelledby="cart-title" @click.self="cartDialog.close()">
    <div class="drawer-content">
      <div class="drawer-header">
        <h2 id="cart-title">Корзина</h2>
        <button class="close-button" type="button" aria-label="Закрыть корзину" @click="cartDialog.close()">×</button>
      </div>
      <p v-if="feedback" class="feedback" role="status" :data-error="feedback.error">{{ feedback.message }}</p>
      <p v-else-if="!cartCount" class="empty">Добавьте мебель из каталога.</p>
      <div class="cart-items">
        <article
          v-for="{ product, quantity } in cartItems"
          :key="product.id"
          class="cart-item"
          :class="{ 'cart-item-without-photo': !product.photo }"
        >
          <img v-if="product.photo" class="cart-thumbnail" :src="product.photo" alt="">
          <div class="cart-item-info">
            <h3>{{ product.name }}</h3>
            <p class="cart-item-price">{{ money(product.price) }} / шт.</p>
            <p v-if="quantity > product.stock" class="cart-item-stock">Доступно {{ product.stock }} шт.</p>
            <div class="quantity">
              <button
                class="decrease"
                type="button"
                :aria-label="`Уменьшить количество — ${product.name}`"
                :disabled="submitting"
                @click="changeCartQuantity(product.id, -1, $event)"
              >−</button>
              <span>{{ quantity }}</span>
              <button
                class="increase"
                type="button"
                :aria-label="`Увеличить количество — ${product.name}`"
                :disabled="submitting || quantity >= product.stock"
                @click="changeCartQuantity(product.id, 1, $event)"
              >+</button>
            </div>
          </div>
          <strong class="line-total">{{ money(product.price * quantity) }}</strong>
        </article>
      </div>
      <div v-if="cartCount" class="cart-summary">
        <div class="total-row"><span>Итого</span><strong>{{ money(cartTotal) }}</strong></div>
        <button id="checkout" class="primary-button" type="button" :disabled="!canCheckout" @click="checkout">
          {{ submitting ? "Оформляем…" : "Оформить продажу" }}
        </button>
      </div>
    </div>
  </dialog>

  <dialog ref="historyDialog" id="history-dialog" class="drawer" aria-labelledby="history-title" @click.self="historyDialog.close()">
    <div class="drawer-content">
      <div class="drawer-header">
        <h2 id="history-title">История продаж</h2>
        <button class="close-button" type="button" aria-label="Закрыть историю продаж" @click="historyDialog.close()">×</button>
      </div>
      <p v-if="isPages" class="empty">Демонстрационные продажи хранятся в этом браузере.</p>
      <p v-if="historyStatus" class="empty" role="status">{{ historyStatus }}</p>
      <div class="sales">
        <article v-for="sale in sales" :key="sale.id" class="sale-row">
          <div>
            <strong>Продажа №{{ sale.id }}</strong>
            <p class="sale-time">{{ formatDate.format(new Date(sale.createdAt)) }} · {{ sale.quantity }} шт.</p>
          </div>
          <strong>{{ money(sale.total) }}</strong>
        </article>
      </div>
    </div>
  </dialog>
</template>


<!-- 
    npm.cmd run build
    python app.py
-->
