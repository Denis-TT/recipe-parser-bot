const tg = window.Telegram?.WebApp;
if (tg) {
  tg.expand();
  tg.ready();
  tg.MainButton.setText('Закрыть').show().onClick(() => tg.close());
}

const FALLBACK_USER = Number(new URLSearchParams(window.location.search).get('user_id') || 218510504);
const currentUser = tg?.initDataUnsafe?.user?.id || FALLBACK_USER;

const CATEGORY_LABELS = {
  breakfast: { name: 'Завтраки', emoji: '🍳' },
  lunch: { name: 'Обеды', emoji: '🍲' },
  dinner: { name: 'Ужины', emoji: '🍽️' },
  dessert: { name: 'Десерты', emoji: '🍰' },
  snack: { name: 'Перекусы', emoji: '🥨' },
  salad: { name: 'Салаты', emoji: '🥗' },
  soup: { name: 'Супы', emoji: '🥣' },
  baking: { name: 'Выпечка', emoji: '🧁' },
  drink: { name: 'Напитки', emoji: '🥤' },
  other: { name: 'Другое', emoji: '📦' },
};

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function normalizeCategory(cat) {
  const key = cat.key || 'other';
  const fallback = CATEGORY_LABELS[key] || CATEGORY_LABELS.other;
  return {
    key,
    name: cat.name || fallback.name,
    emoji: cat.emoji || fallback.emoji,
    count: cat.count || 0,
  };
}

function setupTheme() {
  if (!tg?.themeParams) return;
  const root = document.documentElement;
  Object.entries(tg.themeParams).forEach(([k, v]) => {
    root.style.setProperty(`--tg-theme-${k.replace(/[A-Z]/g, m => `-${m.toLowerCase()}`)}`, v);
  });
}

function applyExpandToggle(buttonId, list, collapsed = 4) {
  if (!Array.isArray(list) || list.length <= collapsed) return { items: list, controls: '' };

  const items = list.slice(0, collapsed);
  const hidden = list.slice(collapsed);

  return {
    items,
    controls: `<button class="link-btn" id="${buttonId}" data-open="false">Развернуть</button><ul class="list hidden" id="${buttonId}-hidden">${hidden
      .map(item => `<li>${item}</li>`)
      .join('')}</ul>`,
  };
}

async function loadCategories() {
  const categoriesScreen = document.getElementById('categories-screen');
  if (!categoriesScreen) return;

  const empty = document.getElementById('empty-state');
  const grid = document.getElementById('categories-grid');
  const recipesScreen = document.getElementById('recipes-screen');
  const recipesList = document.getElementById('recipes-list');
  const title = document.getElementById('screen-title');
  const backBtn = document.getElementById('back-button');
  const searchInput = document.getElementById('search-input');

  backBtn.classList.add('hidden');
  title.textContent = '🍳 Кулинарная книга';
  categoriesScreen.classList.remove('hidden');
  recipesScreen.classList.add('hidden');
  recipesList.innerHTML = '';

  const response = await getJson(`/api/categories/${currentUser}`);
  const categories = response.map(normalizeCategory);

  if (!categories.length) {
    empty.classList.remove('hidden');
    empty.textContent = 'Сохраненных рецептов пока нет.';
    grid.innerHTML = '';
    return;
  }

  empty.classList.add('hidden');
  grid.innerHTML = categories
    .map(
      cat => `<button class="category-card" data-category="${cat.key}" data-name="${cat.name}">
        <div class="emoji">${cat.emoji}</div>
        <div class="name">${cat.name}</div>
        <div class="count">${cat.count}</div>
      </button>`,
    )
    .join('');

  grid.querySelectorAll('.category-card').forEach(node => {
    node.addEventListener('click', () => loadRecipes(node.dataset.category, node.dataset.name));
  });

  searchInput.oninput = () => {
    const value = searchInput.value.toLowerCase().trim();
    grid.querySelectorAll('.category-card').forEach(node => {
      node.classList.toggle('hidden', !node.dataset.name.toLowerCase().includes(value));
    });
  };
}

async function loadRecipes(category, name) {
  const empty = document.getElementById('empty-state');
  const categoriesScreen = document.getElementById('categories-screen');
  const recipesScreen = document.getElementById('recipes-screen');
  const recipesList = document.getElementById('recipes-list');
  const title = document.getElementById('screen-title');
  const backBtn = document.getElementById('back-button');
  const searchInput = document.getElementById('search-input');

  categoriesScreen.classList.add('hidden');
  recipesScreen.classList.remove('hidden');
  backBtn.classList.remove('hidden');
  title.textContent = `← ${name}`;

  const recipes = await getJson(`/api/recipes/${currentUser}/${encodeURIComponent(category)}`);

  if (!recipes.length) {
    recipesList.innerHTML = '';
    empty.classList.remove('hidden');
    empty.textContent = `В категории «${name}» пока нет рецептов.`;
    return;
  }

  empty.classList.add('hidden');

  function renderList(filter = '') {
    const filtered = recipes.filter(r => (r.title || '').toLowerCase().includes(filter));
    recipesList.innerHTML = filtered
      .map(recipe => {
        const nutrition = recipe.nutrition_per_serving || {};
        const kcal = nutrition.calories || 0;
        const cookTime = recipe.cook_time || recipe.total_time || 0;
        return `<button class="recipe-card" data-id="${recipe.id}">
          <div class="recipe-title">${recipe.title || 'Без названия'}</div>
          <div class="recipe-meta">🔥 ${kcal} ккал | ⏱ ${cookTime} мин</div>
        </button>`;
      })
      .join('');

    recipesList.querySelectorAll('.recipe-card').forEach(node => {
      node.addEventListener('click', () => {
        window.location.href = `/recipe?id=${node.dataset.id}&user_id=${currentUser}`;
      });
    });
  }

  renderList();

  searchInput.oninput = () => renderList(searchInput.value.toLowerCase().trim());
  backBtn.onclick = loadCategories;
}

async function initDetailPage() {
  const content = document.getElementById('recipe-content');
  if (!content) return;

  document.getElementById('detail-back').onclick = () => window.history.back();

  const id = new URLSearchParams(window.location.search).get('id');
  if (!id) {
    content.innerHTML = '<p>Рецепт не найден.</p>';
    return;
  }

  const recipe = await getJson(`/api/recipe/${id}`);

  const ingredients = (recipe.ingredients || []).map(i => `${i.name || i.ingredient || 'Ингредиент'} ${i.amount || ''} ${i.unit || ''}`.trim());
  const steps = (recipe.steps || []).map((s, idx) => s.description || s.text || `${idx + 1}. ${s}`);

  const ingredientsBlock = applyExpandToggle('expand-ingredients', ingredients);
  const stepsBlock = applyExpandToggle('expand-steps', steps);

  const nutrition = recipe.nutrition_per_serving || {};

  content.innerHTML = `
    <h2>🍲 ${recipe.title || 'Без названия'}</h2>
    <div class="recipe-subtitle">${recipe.cuisine || 'Интернациональная'} • ${recipe.difficulty || 'средне'}</div>

    <div>⏱ ${recipe.total_time || recipe.cook_time || 0} мин  👥 ${recipe.servings || 1} порций</div>

    <section class="section">
      <h3>📊 КБЖУ на порцию</h3>
      <div class="nutrition">🔥 ${nutrition.calories || 0} ккал<br/>💪 ${nutrition.protein || 0}г 🧈 ${nutrition.fat || 0}г 🍚 ${nutrition.carbs || 0}г</div>
    </section>

    <section class="section">
      <h3>🛒 Ингредиенты</h3>
      <ul class="list">${ingredientsBlock.items.map(i => `<li>${i}</li>`).join('')}</ul>
      ${ingredientsBlock.controls}
    </section>

    <section class="section">
      <h3>📝 Приготовление</h3>
      <ol class="list">${stepsBlock.items.map(s => `<li>${s}</li>`).join('')}</ol>
      ${stepsBlock.controls}
    </section>

    <section class="section">
      <h3>💡 Советы</h3>
      <ul class="list">${(recipe.tips || ['Нет дополнительных советов']).map(t => `<li>${t}</li>`).join('')}</ul>
    </section>
  `;

  ['expand-ingredients', 'expand-steps'].forEach(id => {
    const btn = document.getElementById(id);
    if (!btn) return;
    const hiddenList = document.getElementById(`${id}-hidden`);
    btn.onclick = () => {
      const isOpen = btn.dataset.open === 'true';
      btn.dataset.open = String(!isOpen);
      btn.textContent = isOpen ? 'Развернуть' : 'Свернуть';
      hiddenList.classList.toggle('hidden', isOpen);
    };
  });
}

setupTheme();
loadCategories().catch(err => {
  const empty = document.getElementById('empty-state');
  if (empty) {
    empty.classList.remove('hidden');
    empty.textContent = `Ошибка загрузки: ${err.message}`;
  }
});
initDetailPage().catch(err => {
  const content = document.getElementById('recipe-content');
  if (content) content.innerHTML = `<p>Ошибка загрузки рецепта: ${err.message}</p>`;
});
