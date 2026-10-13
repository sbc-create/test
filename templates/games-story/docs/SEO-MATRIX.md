# SEO-матрица games-story (вариант chapter-guides)

Preview закрыт (`noindex, nofollow`, robots `Disallow: /`); production — только с доменом и `production_authorized` (тест).

| тип | пример | title | canonical | production | sitemap | schema |
| --- | --- | --- | --- | --- | --- | --- |
| главная | `/` | «Сюжет пройден — гайды по главам…» | себя | index | да | WebSite |
| игра | `/igra/celeste/` | «Celeste: все главы, клубники и стороны» | себя | index (игра принадлежит сайту по реестру) | да | BreadcrumbList, ItemList |
| предметы | `/igra/celeste/kollekcii/` | «Celeste: коллекционные предметы по главам» | себя | index | да | BreadcrumbList |
| гайд главы | `/igra/celeste/glava-1-forsaken-city/` | «Глава 1. Forsaken City… — гайд по Celeste» | себя | index | да | BreadcrumbList (+ VideoObject, если на странице есть видео) |
| видео | `/video/` | «Проверенные видео об играх» | себя | index | да | BreadcrumbList, VideoObject |
| как работаем, источники | `/kak-my-rabotaem/`, `/istochniki/` | — | себя | index | да | BreadcrumbList |
| поиск | `/poisk/?q=…` | «Поиск: …» | нет | noindex | нет | — |
| 404 | `/igra/minecraft/` (игра другого сайта), `/igra/celeste/net/` | «Страница не найдена» | нет | 404 | нет | — |

В sitemap 17 URL, все 200, canonical на себя, один H1, уникальные title (тест). VideoObject — только name, embedUrl, url:
даты загрузки и длительности oEmbed не даёт, мы их не придумываем (тест).

## Вариант C (atlas)

`/igra/<игра>/personazhi/`, `/mehaniki/`, `/gde-ya/`, `/personazh/<слаг>/` — index, canonical на себя, в sitemap; `/gde-ya/?q=` — noindex без canonical; неизвестный персонаж — 404.
