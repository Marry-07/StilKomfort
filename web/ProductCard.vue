<script setup>
defineProps({
  product: { type: Object, required: true },
  price: { type: String, required: true },
  disabled: Boolean,
});

defineEmits(["add"]);
</script>

<template>
  <article class="product">
    <div class="product-media">
      <img v-if="product.photo" :src="product.photo" :alt="product.name" loading="lazy" decoding="async">
      <span class="stock" :data-sold-out="product.stock === 0">
        {{ product.stock ? `В наличии ${product.stock} шт.` : "Нет в наличии" }}
      </span>
    </div>
    <div class="product-details">
      <div>
        <h3 class="product-name">{{ product.name }}</h3>
        <p class="product-price">{{ price }}</p>
      </div>
      <button
        class="add-button"
        type="button"
        :disabled="disabled"
        :aria-label="`Добавить в корзину — ${product.name}`"
        @click="$emit('add', product.id)"
      >+</button>
    </div>
  </article>
</template>
