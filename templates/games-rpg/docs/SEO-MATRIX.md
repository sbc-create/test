# SEO-матрица games-rpg (вариант codex-sections)

Preview закрыт (`noindex, nofollow`, robots `Disallow: /`); production — только с доменом и `production_authorized` (тест).

| тип | пример | canonical | production | sitemap | schema |
| --- | --- | --- | --- | --- | --- |
| главная | `/` | себя | index | да | WebSite |
| игра | `/baldurs-gate-3/` | себя | index (игра принадлежит сайту по реестру) | да | BreadcrumbList |
| раздел | `/baldurs-gate-3/personazhi/` | себя | index | да | BreadcrumbList, ItemList |
| материал | `/baldurs-gate-3/bildy/klass-voin/` | себя | index | да | BreadcrumbList |
| версия | `/baldurs-gate-3/versiya/versiya-patch-8/` | себя | index | да | BreadcrumbList |
| поиск | `/poisk/?q=…` | нет | noindex | нет | — |
| 404 | `/celeste/` (игра другого сайта), `/baldurs-gate-3/bildy/shadowheart/` (не тот раздел) | нет | 404 | нет | — |

В sitemap 27 URL (с разделом «Предметы»), все 200, canonical на себя, один H1, уникальные title (тест). Разметка Article/HowTo не используется:
у материалов нет автора и дат, которые можно было бы честно указать в ней.

## Вариант C (index-compare)

`/` — указатель, index; `/?tip=…` — noindex без canonical (неизвестный тип — 400). `/<игра>/sravnenie-predmetov/` — index, в sitemap.
