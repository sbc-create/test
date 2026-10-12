# SEO-матрица food-baking

Проверяется `tests/test_food_baking.py`. Preview: все ответы `X-Robots-Tag: noindex, nofollow`,
мета `noindex, nofollow`, `robots.txt` — `Disallow: /`. Колонка «production» — поведение
после переключателя (`mode: production` + `production_authorized` + домен; без домена — ошибка, BLOCKED_INPUT).

| тип | пример URL (preview) | intent | title / H1 | canonical | production | sitemap | schema |
| --- | --- | --- | --- | --- | --- | --- | --- |
| главная | `/` | что испечь, виды теста | «Тесто и десерты — книга рецептов выпечки» | себя | index | да | — |
| каталог | `/recepty/`, `/recepty/page/2/` | все рецепты | «Все рецепты выпечки — страница N» | себя (у каждой страницы свой) | index | да | BreadcrumbList, ItemList |
| фильтр | `/recepty/?testo=zavarnoe` | технический отбор | «Подбор выпечки» | нет | noindex, follow | нет | — |
| рецепт | `/recept/limonnyj-keks/` | конкретная выпечка | H1 = название, title = seo_title | себя | index | да, lastmod = дата версии | Recipe (без image/rating/author/nutrition), BreadcrumbList |
| вид теста | `/testo/keksovoe/` | техника теста | «Кексовое тесто на разрыхлителе» | себя | index (≥2 рецептов, иначе 404) | да | BreadcrumbList, ItemList |
| разбор ошибок | `/oshibki/zavarnoe/` | почему не получается | «Заварное тесто: на чём ошибаются» | себя | index | да | BreadcrumbList |
| тег | `/teg/shokolad/` | продукт/повод | «Выпечка: шоколад» | себя | index при ≥3, noindex при 2, 404 при <2 | только индексируемые | BreadcrumbList, ItemList |
| поиск | `/poisk/?q=слива` | поиск | «Поиск: …» | нет | noindex, follow; `Disallow: /poisk/` | нет | — |
| 404 | `/nesushchestvuet/` | — | «Страница не найдена» | нет | статус 404 | нет | — |
| редактор | `/redaktor/` | — | — | — | 401 без входа | нет | — |

Ограничения, зафиксированные честно: нет `image` у Recipe (фото нет) — расширенный
результат недоступен; нет VideoObject (роликов нет); пересчёта порций/формы нет
(нет проверенного алгоритма для выпечки).

## Вариант B (oven-bench)

Типы страниц и адреса те же, что у A. Отличия: `/recepty/?sort=…` — noindex без canonical (неизвестное значение игнорируется);
главная — разделы по температуре (якоря `#t-180`), без отдельных URL.
