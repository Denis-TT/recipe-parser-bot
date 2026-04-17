const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const API_BASE = window.location.origin;
const FALLBACK_USER_ID = 218510504;
const currentUser = tg?.initDataUnsafe?.user?.id || FALLBACK_USER_ID;

const CATEGORY_TITLES = {
  breakfast: "🍳 Завтраки",
  lunch: "🍲 Обеды",
  dinner: "🍽️ Ужины",
  dessert: "🍰 Десерты",
  snack: "🥨 Перекусы",
  salad: "🥗 Салаты",
  soup: "🥣 Супы",
  baking: "🧁 Выпечка",
  drink: "🥤 Напитки",
  other: "📦 Другое",
};

let recipesCache = [];

async function request(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Ошибка API: ${response.status}`);
  }
  return response.json();
}

function applyTheme() {
  if (!tg?.themeParams) return;
  const root = document.documentElement;
  Object.entries({
    "--tg-theme-bg-color": tg.themeParams.bg_color,
    "--tg-theme-text-color": tg.themeParams.text_color,
    "--tg-theme-hint-color": tg.themeParams.hint_color,
    "--tg-theme-secondary-bg-color": tg.themeParams.secondary_bg_color,
    "--tg-theme-button-color": tg.themeParams.button_color,
  }).forEach(([key, value]) => value && root.style.setProperty(key, value));
}

function cardMeta(recipe) {
  const kcal = recipe?.nutrition_per_serving?.calories || recipe?.calories || 0;
  const cookTime = recipe?.cook_time || recipe?.total_time || 0;
  return `🔥 ${kcal} ккал | ⏱ ${cookTime} мин`;
}

async function loadCategories() {
  const categories = await request(`/api/categories/${currentUser}`);
  const grid = document.getElementById("categories-grid");
  grid.innerHTML = categories
    .map(
      (cat) => `
      <button class="category-card" onclick="loadRecipes('${cat.key}')">
        <div class="emoji">${cat.emoji || "🍽️"}</div>
        <div class="name">${cat.name || cat.key}</div>
        <div class="count">${cat.count || 0}</div>
      </button>
    `,
    )
    .join("");
}

async function loadRecipes(category) {
  const recipes = await request(`/api/recipes/${currentUser}/${encodeURIComponent(category)}`);
  recipesCache = recipes;

  document.getElementById("categories-screen").classList.add("hidden");
  document.getElementById("recipes-screen").classList.remove("hidden");
  document.getElementById("back-button").classList.remove("hidden");
  document.getElementById("search-wrap").classList.remove("hidden");
  document.getElementById("screen-title").textContent = CATEGORY_TITLES[category] || category;
  renderRecipes(recipes);

  document.getElementById("search-input").oninput = (event) => {
    const q = event.target.value.trim().toLowerCase();
    const filtered = recipesCache.filter((r) => (r.title || "").toLowerCase().includes(q));
    renderRecipes(filtered);
  };
}

function renderRecipes(recipes) {
  const list = document.getElementById("recipes-list");
  if (!recipes.length) {
    list.innerHTML = '<div class="recipe-card">В этой категории пока нет рецептов.</div>';
    return;
  }

  list.innerHTML = recipes
    .map(
      (recipe) => `
      <article class="recipe-card" onclick="openRecipe('${recipe.id}')">
        <div class="recipe-title">${recipe.title || "Без названия"}</div>
        <div class="recipe-meta">${cardMeta(recipe)}</div>
      </article>
    `,
    )
    .join("");
}

function openRecipe(recipeId) {
  window.location.href = `/recipe-detail.html?id=${recipeId}&user=${currentUser}`;
}

function goHome() {
  document.getElementById("categories-screen")?.classList.remove("hidden");
  document.getElementById("recipes-screen")?.classList.add("hidden");
  document.getElementById("search-wrap")?.classList.add("hidden");
  document.getElementById("back-button")?.classList.add("hidden");
  const title = document.getElementById("screen-title");
  if (title) title.textContent = "🍳 Кулинарная книга";
}

function renderExpandableList(items, max, ordered = false) {
  const listClass = ordered ? "list ordered" : "list";
  if (!items?.length) return '<div class="inline-meta">Нет данных</div>';

  const visible = items.slice(0, max);
  const hidden = items.slice(max);

  return `
    <${ordered ? "ol" : "ul"} class="${listClass}">
      ${visible.map((item) => `<li>${item}</li>`).join("")}
    </${ordered ? "ol" : "ul"}>
    ${
      hidden.length
        ? `<button class="expand-button" onclick="this.previousElementSibling.insertAdjacentHTML('beforeend', '${hidden
            .map((item) => `<li>${String(item).replace(/'/g, "&#39;")}</li>`)
            .join("")}'); this.remove();">Развернуть</button>`
        : ""
    }
  `;
}

async function loadRecipeDetail() {
  const detailNode = document.getElementById("recipe-detail");
  if (!detailNode) return;

  const params = new URLSearchParams(window.location.search);
  const recipeId = params.get("id");
  if (!recipeId) {
    detailNode.innerHTML = "<p>Рецепт не найден.</p>";
    return;
  }

  const recipe = await request(`/api/recipe/${recipeId}`);
  const nutrition = recipe.nutrition_per_serving || recipe.nutrition || {};
  const ingredients = (recipe.ingredients || []).map((item) => {
    if (typeof item === "string") return item;
    return `${item.name || "Ингредиент"} ${item.amount || ""} ${item.unit || ""}`.trim();
  });
  const steps = (recipe.steps || []).map((item, idx) => {
    if (typeof item === "string") return `${idx + 1}. ${item}`;
    return `${idx + 1}. ${item.description || ""}`;
  });

  detailNode.innerHTML = `
    <section>
      <h1 class="detail-title">🍲 ${recipe.title || "Без названия"}</h1>
      <div class="detail-subtitle">${recipe.cuisine || "Интернациональная"} • ${recipe.difficulty || "средне"}</div>
      <div class="inline-meta">⏱ ${recipe.total_time || recipe.cook_time || 0} мин • 👥 ${recipe.servings || 1} порций</div>
    </section>

    <section class="detail-section">
      <h2 class="section-title">📊 КБЖУ на порцию</h2>
      <div>🔥 ${nutrition.calories || 0} ккал</div>
      <div>💪 ${nutrition.protein || 0}г &nbsp; 🧈 ${nutrition.fat || 0}г &nbsp; 🍚 ${nutrition.carbs || 0}г</div>
    </section>

    <section class="detail-section">
      <h2 class="section-title">🛒 Ингредиенты</h2>
      ${renderExpandableList(ingredients, 5)}
    </section>

    <section class="detail-section">
      <h2 class="section-title">📝 Приготовление</h2>
      ${renderExpandableList(steps, 4, true)}
    </section>

    <section class="detail-section">
      <h2 class="section-title">💡 Советы</h2>
      ${renderExpandableList(recipe.tips || [], 3)}
    </section>
  `;

  document.getElementById("detail-back-button")?.addEventListener("click", () => window.history.back());
  document.getElementById("share-button")?.addEventListener("click", async () => {
    const shareText = `🍽️ ${recipe.title}\n${window.location.href}`;
    if (navigator.share) {
      await navigator.share({ title: recipe.title, text: shareText, url: window.location.href });
      return;
    }
    await navigator.clipboard.writeText(shareText);
    tg?.showPopup?.({ title: "Готово", message: "Ссылка на рецепт скопирована" });
  });
}

window.loadRecipes = loadRecipes;
window.openRecipe = openRecipe;

window.addEventListener("DOMContentLoaded", async () => {
  applyTheme();

  const mainBackButton = document.getElementById("back-button");
  if (mainBackButton) {
    mainBackButton.addEventListener("click", goHome);
  }

  if (document.getElementById("categories-grid")) {
    await loadCategories();
    tg?.MainButton.setText("Закрыть");
    tg?.MainButton.show();
    tg?.MainButton.onClick(() => tg.close());
  }

  await loadRecipeDetail();
});
