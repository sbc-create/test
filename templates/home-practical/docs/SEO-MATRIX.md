# SEO-матрица home-practical (вариант problem-checklists)

Preview закрыт: `X-Robots-Tag` и мета `noindex, nofollow` на всех ответах, `robots.txt` — `Disallow: /`.
Production — отдельный переключатель: `mode: production`, `production_authorized: true` и `origin.production`;
без домена `abs()` падает с BLOCKED_INPUT (тест). Рекламы и счётчиков нет (`ads/analytics: disabled`).

| тип | пример | title | canonical | production | sitemap | schema |
| --- | --- | --- | --- | --- | --- | --- |
| главная | `/` | «Удобный дом — хранение, мебель и небольшие улучшения по комнатам» | себя | index | да | WebSite |
| проблемы | `/problemy/` | «Что мешает дома: выберите проблему» | себя | index | да | BreadcrumbList |
| проблема | `/problemy/mebel-mozhet-upast/` | формулировка проблемы | себя | index (все инструкции опубликованы, иначе 404) | да | BreadcrumbList, ItemList |
| помещения | `/pomeshcheniya/` | «Помещения: что улучшить в каждой комнате» | себя | index | да | BreadcrumbList |
| помещение | `/pomeshcheniya/spalnya/` | «Спальня: хранение, мебель и улучшения» | себя | index (≥1 материал, иначе 404) | да | BreadcrumbList, ItemList |
| каталог задач | `/zadachi/` | «Каталог задач по дому» | себя | index | да | BreadcrumbList, ItemList |
| каталог с фильтром или сортировкой | `/zadachi/?pomeshchenie=…&zadacha=…&sort=…` | «Каталог задач по дому: …» | **нет** | noindex, follow; `Disallow: /*?` | нет | BreadcrumbList, ItemList |
| задача | `/zadachi/mebel/` | «Мебель: инструкции для всех помещений» | себя | index (≥1, иначе 404) | да | BreadcrumbList, ItemList |
| инструкция | `/instrukciya/zakrepit-komod-k-stene/` | название инструкции | себя | index | да | HowTo (название, описание, supply, step), BreadcrumbList |
| подборки | `/podborki/` | «Подборки: крепление, ящики, обувь, без дрели» | себя | index | да | BreadcrumbList |
| подборка | `/podborki/krepim-k-stene/` | название подборки | себя | index (≥2, иначе нет страницы) | да | BreadcrumbList, ItemList |
| тег | `/teg/sverlenie/` | «<тег> — инструкции» | себя | index (≥2 и тег не совпадает с подборкой) | да | BreadcrumbList, ItemList |
| источники | `/istochniki/` | «Источники: производители и профильные организации» | себя | index | да | BreadcrumbList |
| как проверяем | `/kak-my-proveryaem/` | «Как мы проверяем инструкции» | себя | index | да | BreadcrumbList |
| поиск | `/poisk/?q=…` | «Поиск: …» | нет | noindex, follow | нет | — |
| сохранённое | `/sohranennoe/` | «Сохранённые инструкции» | нет | noindex, follow | нет | — |
| 404 | `/pomeshcheniya/cherdak/`, `/teg/opasnost-padeniya/` | «Страница не найдена» | нет | 404 | нет | — |

В sitemap 44 URL (37 как в A + 7 страниц проблем); все отвечают 200, canonical = абсолютный адрес страницы, ровно один H1, title уникальны (тест).
HowTo — только видимое: число шагов совпадает со страницей; нет `image`, `aggregateRating`, `author`, `estimatedCost`,
`totalTime`, `video`, `review` (тест). Тег, на котором построена подборка, ссылается на подборку и своей страницы не имеет —
иначе две страницы с одинаковым набором. Адрес без завершающего слэша получает 301.
