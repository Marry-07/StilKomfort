export const categories = [
  { id: "all", label: "Всё" },
  { id: "sofas", label: "Диваны" },
  { id: "tables", label: "Столы" },
  { id: "chairs", label: "Стулья" },
  { id: "wardrobes", label: "Шкафы" },
  { id: "beds", label: "Кровати" },
];

const photosByCategory = {
  chairs: { 1: "chair", 5: "chair-lira", 6: "chair-cloud", 7: "chair-retro", 8: "chair-milan" },
  tables: { 2: "table", 9: "table-round", 10: "table-bianco", 11: "table-nord", 12: "table-reef" },
  sofas: { 3: "sofa", 13: "sofa-nimbus", 14: "sofa-amber", 15: "sofa-modul", 16: "sofa-velvet" },
  wardrobes: { 4: "wardrobe", 17: "wardrobe-linen", 18: "wardrobe-walnut", 19: "wardrobe-mirror", 20: "wardrobe-sage" },
  beds: { 21: "bed-dune", 22: "bed-rose", 23: "bed-taiga", 24: "bed-moon", 25: "bed-line" },
};

const metadata = new Map();
for (const [category, photos] of Object.entries(photosByCategory)) {
  for (const [id, filename] of Object.entries(photos)) {
    metadata.set(Number(id), { category, photo: `/images/${filename}.webp` });
  }
}

export function withProductPhoto(product) {
  return { ...product, ...metadata.get(product.id) };
}
