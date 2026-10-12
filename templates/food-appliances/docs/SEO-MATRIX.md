# SEO-матрица food-appliances

Preview закрыт: `X-Robots-Tag` и мета `noindex, nofollow` на всех ответах, `robots.txt` — `Disallow: /`.
Production включается отдельным переключателем и требует `origin.production` и `production_authorized: true`,
иначе RuntimeError (BLOCKED_INPUT). Проверки — `tests/test_food_appliances.py`.

| тип | пример | title | canonical | production | sitemap | schema |
| --- | --- | --- | --- | --- | --- | --- |
| главная | `/` | «Готовим в технике — рецепты для мультиварки и аэрогриля» | себя | index | да | — |
| прибор | `/pribor/multivarka/` | «Рецепты для прибора: мультиварка» | себя | index (≥1 рецепт, иначе 404) | да | BreadcrumbList, ItemList |
| прибор × категория | `/pribor/aerogril/kurica/` | «Аэрогриль: курица» | себя | index (≥2 рецепта, иначе 404) | да | BreadcrumbList, ItemList |
| рецепт | `/recept/plov-v-multivarke/` | seo_title черновика (блюдо + режимы) | себя | index | да | Recipe (`tool` = прибор), BreadcrumbList |
| режим | `/rezhim/multivarka-vypechka/` | «Мультиварка: режим «Выпечка»» | себя | index (≥2 рецепта, иначе 404) | да | BreadcrumbList, ItemList |
| инструкция | `/kak-chitat-rezhimy/` | «Как читать режимы и температуры…» | себя | index | да | BreadcrumbList |
| поиск | `/poisk/?q=…` | «Поиск: …» | **нет** | noindex, follow | нет | — |
| 404 | `/pribor/gril/`, `/rezhim/aerogril-x/` | «Страница не найдена» | нет | 404 | нет | — |

В sitemap 25 URL: главная, инструкция, 2 прибора, 6 разделов прибор × категория, 4 режима, 12 рецептов.
Все отвечают 200, canonical = абсолютный URL самой страницы, ровно один H1, title уникальны (тест).

В Recipe нет `image`, `aggregateRating`, `author`, `nutrition` и `video`: этих данных нет, и их
не выдумываем (тест). Число шагов в `recipeInstructions` совпадает с шагами на странице.
Адрес без завершающего слэша получает 301 на канонический.
Дубли с food-daily исключены: другие рецепты (только для прибора) и собственные тексты черновиков.
