# SEO-матрица food-daily

Проверяется автоматически: `tests/test_site_seo.py` рендерит страницы тем же
`App`, что обслуживает preview. Режим сайта — `config/site.yaml: mode`.
В preview **все** ответы несут `X-Robots-Tag: noindex, nofollow`, мета
`robots=noindex, nofollow`, а `robots.txt` — `Disallow: /`. Колонка
«индексация» описывает поведение в production после переключателя
(`mode: production`, `production_authorized: true`, заданный домен).

| тип | адрес | canonical | индексация (production) | в sitemap | JSON-LD | H1 / title |
| --- | --- | --- | --- | --- | --- | --- |
| главная | `/` | себя | index, follow | да | — | уникальные |
| каталог | `/recepty/`, `/recepty/page/N/` | себя (каждая страница пагинации — свой canonical, rel prev/next) | index, follow | да | BreadcrumbList | «… — страница N» |
| каталог с фильтрами | `/recepty/?produkt=&vremya=&tip=` | нет | noindex, follow | нет | — | «Подбор рецептов» |
| раздел | `/recepty/<раздел>/` (+ `page/N/`) | себя | index, follow | да, lastmod = последнее обновление рецептов раздела | BreadcrumbList + ItemList (карточки этой страницы) | «<Раздел>: рецепты» |
| продукт | `/produkty/<тег>/` | себя | index при ≥3 рецептах, noindex,follow при 2; страницы нет при <2 | только индексируемые | BreadcrumbList | «Рецепты: <продукт>» |
| способ | `/sposob/<тег>/` | себя | так же | так же | BreadcrumbList | «<Способ>: рецепты» |
| подборка | `/podborki/<id>/` | себя | index (подборка существует при ≥3 рецептах) | да | BreadcrumbList | уникальные |
| рецепт | `/recept/<slug>/` | себя | index, follow | да, lastmod = дата текущей версии | Recipe + BreadcrumbList | H1 = название, title = seo_title |
| видео | `/video/<slug>/` | — | **страницы нет**: готовых роликов нет | нет | VideoObject появится только при `media.status=ready` и реальном файле | — |
| поиск | `/poisk/?q=` | нет | noindex, follow; `Disallow: /poisk/` | нет | — | «Поиск: …» |
| избранное, покупки | `/izbrannoe/`, `/spisok-pokupok/` | нет | noindex, follow | нет | — | — |
| о проекте, контакты | `/o-proekte/`, `/kontakty/` | себя | index | да | — | — |
| индекс тем | `/produkty/`, `/sposob/` | себя | index | да | BreadcrumbList | «Продукты: рецепты по темам» |
| советы | `/sovety/`, `/sovety/<slug>/` | себя | index | да, lastmod = `updated` статьи | Article (без автора и изображения) + BreadcrumbList | H1 = заголовок статьи |
| 404 | любой неизвестный | нет | noindex; код 404 | нет | — | «Такой страницы нет» |
| редактор | `/redaktor/` | — | Basic Auth, noindex; `Disallow: /redaktor/` | нет | — | — |

## Recipe JSON-LD — только видимое

| поле | источник | на странице |
| --- | --- | --- |
| name, description | наш черновик (title, intro) | H1, вводный абзац |
| recipeIngredient | факты источника (название из черновика, количество и единица — из фактов) | список ингредиентов |
| recipeInstructions / HowToStep | наш текст шагов, url `#shag-N` | нумерованные шаги |
| recipeYield | факты (порции) | «Порции» |
| prepTime / cookTime / totalTime | факты источника, только если указаны | «Время» |
| recipeCategory, keywords | раздел и теги | крошки, теги |
| datePublished | дата публикации в preview (событие журнала) | «Опубликовано …» |

Не выводятся: `aggregateRating`, `review`, `author`, `nutrition` (данных нет),
`image` (фотографий с подтверждёнными правами нет; иллюстрации раздела фото
блюда не являются — подписано на странице), `video`. Следствие: без `image`
страницы рецептов не соответствуют требованиям Google к расширенному
результату Recipe — до появления собственных фото это известное ограничение,
а не дефект разметки.

## Карта intent → URL

Одна тема — один основной URL (`data/topic-map.csv`, колонка `planned_url`).
Варианты рецепта с другой пропорцией или способом — отдельные материалы со
своим URL только после редакторского решения; автоматическое объединение
несовместимых рецептов запрещено (`dedupe_key` = тема + набор ингредиентов).
Темы, отданные другим сайтам сети, имеют префикс сайта (`food-baking:/…`) и
здесь не публикуются.

## Дерево сайта (preview на 11.10.2026)

```
/                                  главная: поиск, продукты, время, новые, подборки, разделы
├── /recepty/                      каталог + фильтры (22 рецепта, 3 страницы)
│   ├── /recepty/zavtraki/         7
│   ├── /recepty/supy/             4
│   ├── /recepty/vtorye-blyuda/    6
│   ├── /recepty/garniry/          2
│   ├── /recepty/salaty/           2
│   └── /recepty/zakuski/          1
├── /produkty/<продукт>/           тег-страницы, только при ≥2 рецептах
├── /sposob/<способ>/
├── /podborki/                     подборки по правилу (≥3 рецептов)
├── /recept/<slug>/                22 рецепта
├── /poisk/  /izbrannoe/  /spisok-pokupok/   служебные, noindex
└── /o-proekte/  /kontakty/
```

## Производительность (лабораторно)

Playwright, Chromium headless, локальный preview без троттлинга сети. Это
лабораторные значения на одной машине, **не** полевые данные CrUX/Метрики.
Результаты — `docs/verification/browser-qa.json`. Рекламные места в preview
не выводятся вовсе (адаптер `disabled`), поэтому сдвига от них нет; при
включении адаптера слот резервирует высоту заранее (`factory/ads.py` MockAds/Official).

## Подключения после появления домена

Яндекс Вебмастер, Search Console и счётчики не подключены и не заявлены:
домена нет (`origin.production: null`). Тестовые адреса preview в панели не
отправлялись. Порядок: домен → `origin.production` → `mode: production` +
`production_authorized` → проверка `tests/test_site_seo.py::test_production_switch`
на реальном origin → подтверждение прав в Вебмастере → sitemap.

## Реальные примеры URL (preview, 12.10.2026)

| тип | пример | ответ |
| --- | --- | --- |
| главная | `/` | 200 |
| каталог | `/recepty/`, `/recepty/page/2/` | 200; `/recepty/page/1/` → 404, `/recepty/page/9/` → 404 |
| раздел | `/recepty/supy/`, `/recepty/zavtraki/` | 200 |
| тег | `/produkty/kurica/`, `/sposob/na-skovorode/` | 200; `/produkty/zzz/` → 404 |
| подборка | `/podborki/bystro-do-30-minut/` | 200 |
| рецепт | `/recept/syrniki-s-ezhevikoj/` | 200; в карантине `/recept/tomatnyj-sup-s-zapechennym-percem/` → 404 |
| совет | `/sovety/priznaki-gotovnosti/` | 200; `/sovety/net-takogo/` → 404 |
| поиск | `/poisk/?q=творог` | 200, noindex, без canonical |
| фильтр | `/recepty/?produkt=kurica&vremya=do-60` | 200, noindex, без canonical |
| без слеша | `/recepty` | 301 → `/recepty/` |

## Теги — ссылки, не текст

На странице рецепта выводятся только теги, у которых есть живая страница
(`Site.tag_links`); каждая — `<a href>` на `/produkty/<тег>/` или
`/sposob/<тег>/`. Синонимов нет: один тег на продукт или способ.
Проверка — `test_recipe_tags_are_links_to_live_pages`.

## Изображения

Иллюстрация раздела больше не выводится ни в карточке рецепта, ни в его
шапке: она не изображает конкретное блюдо. Карточка отличается содержанием
(раздел, название, первая фраза, главные продукты, время, порции). Фото и
нейроиллюстраций конкретных блюд нет: подключённого генератора нет — честное
состояние «без медиа». Иллюстрации остаются только на плитках разделов.

## Вариант C (party-list)

`/na-kompaniyu/` без параметров — index, canonical на себя, в sitemap; с выбором — noindex без canonical; гостей вне 1–20 или только неизвестные рецепты — 400.
