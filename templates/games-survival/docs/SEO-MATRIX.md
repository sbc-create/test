# SEO-матрица games-survival (вариант craft-tree)

Preview закрыт (`noindex, nofollow`, robots `Disallow: /`); production — только с доменом и `production_authorized` (тест).

| тип | пример | canonical | production | sitemap | schema |
| --- | --- | --- | --- | --- | --- |
| главная | `/` | себя | index | да | WebSite |
| игра | `/minecraft/` | себя | index (игра принадлежит сайту по реестру) | да | BreadcrumbList |
| раздел | `/minecraft/predmety/`, `/minecraft/postrojki/` | себя | index | да | BreadcrumbList, ItemList |
| предмет / ресурс / биом | `/minecraft/predmety/palka/` | себя | index | да | BreadcrumbList |
| версия | `/minecraft/versiya/versiya/` | себя | index | да | BreadcrumbList |
| поиск | `/poisk/?q=…` | нет | noindex | нет | — |
| 404 | `/celeste/` (игра другого сайта), `/minecraft/biomy/palka/` (не тот раздел) | нет | 404 | нет | — |

В sitemap 31 URL, все 200, canonical на себя, один H1, уникальные title, нет `href="#"` (тест).
Разметка HowTo/Recipe не используется: рецепт крафта — не кулинарный рецепт, а автора и дат для Article нет.
