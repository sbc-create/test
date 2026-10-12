# SEO-матрица garden-season (вариант month-calendar)

Preview закрыт: `X-Robots-Tag` и мета `noindex, nofollow`, robots `Disallow: /`. Production — `mode: production`,
`production_authorized: true`, `origin.production`; без домена — RuntimeError (BLOCKED_INPUT, тест). Рекламы и счётчиков нет.

| тип | пример | title | canonical | production | sitemap | schema |
| --- | --- | --- | --- | --- | --- | --- |
| главная | `/` | «Дача по сезону — календарь работ с регионом для каждого срока» | себя | index | да | WebSite |
| календарь | `/kalendar/` | «Календарь работ на год» | себя | index | да | BreadcrumbList |
| календарь с фильтром | `/kalendar/?region=…&tip=…` | «Календарь работ на год: …» | нет | noindex; `Disallow: /*?` | нет | BreadcrumbList |
| месяц | `/kalendar/oktyabr/` | «Работы на даче в октябре: по регионам» | себя | index (есть работы) | да | BreadcrumbList, ItemList |
| месяц без работ | `/kalendar/dekabr/` | то же | нет | noindex | нет | BreadcrumbList |
| культуры / культура | `/kultury/`, `/kultura/malina/` | «Малина: когда что делать — по регионам» | себя | index | да | BreadcrumbList, ItemList |
| работа | `/rabota/malina-obrezka/` | название работы | себя | index | да | HowTo (название, описание, шаги), BreadcrumbList |
| регионы / регион | `/regiony/`, `/region/or-west/` | «Западный Орегон: сезонные работы» | себя | index | да | BreadcrumbList, ItemList |
| тип работ | `/tip/zima/` | «Подготовка к зиме: работы по месяцам» | себя | index | да | BreadcrumbList, ItemList |
| подборки / подборка | `/podborki/`, `/podborki/yagodniki/` | название подборки | себя | index (≥2) | да | BreadcrumbList, ItemList |
| как читать сроки, источники | `/kak-chitat-sroki/`, `/istochniki/` | — | себя | index | да | BreadcrumbList |
| поиск | `/poisk/?q=…` | «Поиск: …» | нет | noindex | нет | — |
| 404 | `/kalendar/xx/`, `/kultura/banan/` | «Страница не найдена» | нет | 404 | нет | — |

В sitemap 54 URL, все 200, canonical на себя, один H1, уникальные title (тест). HowTo — только видимое, без image,
рейтинга, автора, цены, времени (тест). Сроки в разметку не выносятся: они региональные и показаны в таблице на странице.
