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
| раздел | `/recepty/<раздел>/` (+ `page/N/`) | себя | index, follow | да, lastmod = последнее обновление рецептов раздела | BreadcrumbList | «<Раздел>: рецепты» |
| продукт | `/produkty/<тег>/` | себя | index при ≥3 рецептах, noindex,follow при 2; страницы нет при <2 | только индексируемые | BreadcrumbList | «Рецепты: <продукт>» |
| способ | `/sposob/<тег>/` | себя | так же | так же | BreadcrumbList | «<Способ>: рецепты» |
| подборка | `/podborki/<id>/` | себя | index (подборка существует при ≥3 рецептах) | да | BreadcrumbList | уникальные |
| рецепт | `/recept/<slug>/` | себя | index, follow | да, lastmod = дата текущей версии | Recipe + BreadcrumbList | H1 = название, title = seo_title |
| видео | `/video/<slug>/` | — | **страницы нет**: готовых роликов нет | нет | VideoObject появится только при `media.status=ready` и реальном файле | — |
| поиск | `/poisk/?q=` | нет | noindex, follow; `Disallow: /poisk/` | нет | — | «Поиск: …» |
| избранное, покупки | `/izbrannoe/`, `/spisok-pokupok/` | нет | noindex, follow | нет | — | — |
| о проекте, контакты | `/o-proekte/`, `/kontakty/` | себя | index | да | — | — |
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
