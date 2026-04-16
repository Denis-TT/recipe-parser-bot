-- RPC function required by src/supabase_storage.py::get_categories
-- Run in Supabase SQL Editor.

create or replace function public.get_user_categories(p_user_id bigint)
returns table (
  key text,
  name text,
  emoji text,
  count bigint
)
language sql
security definer
set search_path = public
as $$
  select
    coalesce(meal_type, 'other') as key,
    case coalesce(meal_type, 'other')
      when 'breakfast' then 'Завтраки'
      when 'lunch' then 'Обеды'
      when 'dinner' then 'Ужины'
      when 'dessert' then 'Десерты'
      when 'snack' then 'Перекусы'
      when 'salad' then 'Салаты'
      when 'soup' then 'Супы'
      when 'baking' then 'Выпечка'
      when 'drink' then 'Напитки'
      else 'Другое'
    end as name,
    case coalesce(meal_type, 'other')
      when 'breakfast' then '🍳'
      when 'lunch' then '🍲'
      when 'dinner' then '🍽️'
      when 'dessert' then '🍰'
      when 'snack' then '🥨'
      when 'salad' then '🥗'
      when 'soup' then '🥣'
      when 'baking' then '🧁'
      when 'drink' then '🥤'
      else '📦'
    end as emoji,
    count(*)::bigint as count
  from public.recipes
  where user_id = p_user_id
  group by coalesce(meal_type, 'other')
  order by count(*) desc;
$$;

grant execute on function public.get_user_categories(bigint) to anon, authenticated, service_role;

create index if not exists idx_recipes_user_meal_type on public.recipes(user_id, meal_type);
