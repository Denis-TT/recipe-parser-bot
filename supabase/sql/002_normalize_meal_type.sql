-- Normalize legacy Cyrillic meal_type values in public.recipes.
-- Run in Supabase SQL Editor once.

begin;

update public.recipes
set meal_type = case lower(trim(coalesce(meal_type, '')))
  when 'завтрак' then 'breakfast'
  when 'обед' then 'lunch'
  when 'ужин' then 'dinner'
  when 'десерт' then 'dessert'
  when 'перекус' then 'snack'
  when 'закуска' then 'snack'
  when 'салат' then 'salad'
  when 'суп' then 'soup'
  when 'выпечка' then 'baking'
  when 'напиток' then 'drink'
  when 'другое' then 'other'
  when 'основное блюдо' then 'dinner'
  when 'breakfast' then 'breakfast'
  when 'lunch' then 'lunch'
  when 'dinner' then 'dinner'
  when 'dessert' then 'dessert'
  when 'snack' then 'snack'
  when 'salad' then 'salad'
  when 'soup' then 'soup'
  when 'baking' then 'baking'
  when 'drink' then 'drink'
  when 'other' then 'other'
  else 'other'
end
where meal_type is distinct from case lower(trim(coalesce(meal_type, '')))
  when 'завтрак' then 'breakfast'
  when 'обед' then 'lunch'
  when 'ужин' then 'dinner'
  when 'десерт' then 'dessert'
  when 'перекус' then 'snack'
  when 'закуска' then 'snack'
  when 'салат' then 'salad'
  when 'суп' then 'soup'
  when 'выпечка' then 'baking'
  when 'напиток' then 'drink'
  when 'другое' then 'other'
  when 'основное блюдо' then 'dinner'
  when 'breakfast' then 'breakfast'
  when 'lunch' then 'lunch'
  when 'dinner' then 'dinner'
  when 'dessert' then 'dessert'
  when 'snack' then 'snack'
  when 'salad' then 'salad'
  when 'soup' then 'soup'
  when 'baking' then 'baking'
  when 'drink' then 'drink'
  when 'other' then 'other'
  else 'other'
end;

commit;

-- Optional verification:
-- select meal_type, count(*) from public.recipes group by meal_type order by count(*) desc;
