# SEO-матрица plants-home (вариант pick-and-diagnose)

Preview закрыт (`noindex, nofollow`, robots `Disallow: /`); production — только с доменом и `production_authorized` (тест). Рекламы и счётчиков нет.

| тип | пример | title | canonical | production | sitemap | schema |
| --- | --- | --- | --- | --- | --- | --- |
| главная | `/` | «Домашние растения — условия и уход по конкретному виду» | себя | index | да | WebSite |
| подбор | `/podbor/` | «Подбор комнатного растения по условиям» | себя (без параметров) | index; с ответами — noindex без canonical | да | BreadcrumbList |
| что случилось | `/chto-sluchilos/` | «Что случилось с растением: …» | себя | index | да | BreadcrumbList |
| сравнение | `/katalog/` | «Каталог комнатных растений» | себя | index | да | BreadcrumbList, ItemList |
| каталог с фильтром | `/katalog/?svet=…&uhod=…` | «Каталог…: …» | нет | noindex; `Disallow: /*?` | нет | BreadcrumbList, ItemList |
| растение | `/rastenie/fikus-kauchukonosnyj/` | «Фикус каучуконосный (Ficus elastica): свет, полив, проблемы» | себя | index | да | BreadcrumbList |
| освещение / категория | `/svet/`, `/svet/ten/` | «Тень: какие комнатные растения подойдут» | себя | index | да | BreadcrumbList, ItemList |
| проблемы / проблема | `/problemy/`, `/problema/korni-gniyut/` | «Корни гниют от перелива: у каких растений и что делать» | себя | index (≥2 вида) | да | BreadcrumbList, ItemList |
| подборки / подборка | `/podborki/`, `/podborki/neprihotlivye/` | название подборки | себя | index (≥2) | да | BreadcrumbList, ItemList |
| как читать, источники | `/kak-chitat/`, `/istochniki/` | — | себя | index | да | BreadcrumbList |
| поиск | `/poisk/?q=…` | «Поиск: …» | нет | noindex | нет | — |
| 404 | `/rastenie/net/`, `/svet/luna/` | «Страница не найдена» | нет | 404 | нет | — |

В sitemap 38 URL, все 200, canonical на себя, один H1, уникальные title (тест). Для карточек растений нет подходящего
типа schema.org без выдумывания полей (Product/Offer — не про уход), поэтому только BreadcrumbList.
