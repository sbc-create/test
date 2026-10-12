# GA4: план раскатки по витринам (согласован с Архитектором 12.10.2026)

Статус: **ждёт ID** — ресурсов GA4 нет; ID не придумываются (пустое поле = `BLOCKED_INPUT`).
Тег и проба готовы: `automation/host/seo_layer.py::тег_ga4` (8da3f47), `automation/local/ga4-tag-audit.py` (53469d7).

## Правила

- Один ключ на сеть — имя переменной `LORDS_GA4_MEASUREMENT_ID`, его читает общий слой.
  Место значения в файле — по конвенции репозитория, ровно одно на витрину.
- GA4 появляется ровно там и ровно при тех условиях, при которых появляется Метрика
  на той же витрине: тот же сторож (`analytics.enabled`, `allowed_hosts`, форма ID).
- Новых блоков в `site.json` не вводить; правка `run.py` — по уже работающему образцу
  «поле из site.json → экспорт под универсальным именем», не новый механизм.
- Параллельного поля в реестре ячеек нет (D177). Сборщик Архитектора берёт домен → G-ID
  с живой страницы по метке `data-ga4-id`.
- Выкладка слоя — только вместе с первым ID; без ID она ничего не меняет.

## По витринам

| Витрина | Где Метрика | Куда GA4 | Правка run.py |
|---|---|---|---|
| lordserial33.biz, lordfilm47.space, 1lordserials1.online, lordserials22.info, lordserials22.site, lordserials22.space | `environment.LORDS_METRIKA_COUNTER` | `environment.LORDS_GA4_MEASUREMENT_ID` | нет |
| zonafilm.space, zonafilm12.site, zonafilm.cc | `environment.LORDS_METRIKA_COUNTER` | `environment.LORDS_GA4_MEASUREMENT_ID` | нет |
| an1mego.site, animeg0.site, an1meg0.site | `analytics.counter_id` (+ `ANIMEGO_METRIKA_COUNTER`), сторож `enabled` | `analytics.ga4_measurement_id` | да, сторож `enabled` + форма |
| animedia.space | `analytics.counter_id` (+ ручное), `_счётчик_метрики` | `analytics.ga4_measurement_id` | да, тот же сторож |
| animedia.icu | `analytics.counter_id`, сторож `enabled` + `allowed_hosts` | `analytics.ga4_measurement_id` | да, тот же сторож с `allowed_hosts` |
| lordserial101.site, lordfilm077.site | счётчика нет | — | по решению владельца вместе с Метрикой |
| Yummy ×5 | разметку отдаёт образ Next.js | тег в образе приложения | не наш путь (выпуск владельца Yummy) |

У AnimeGo ×3 и animedia.space блока `environment` в `site.json` нет; у Lords/Zona нет блока `analytics`.

## Приёмка

1. `python3 automation/local/ga4-tag-audit.py --expect <домен>=<G-ID> …` — до выкладки на
   непатченной витрине нарушение, после — чисто; витрины без ID — без тега.
2. build двумя источниками (заголовок + итог исполнителя) и поведение — независимо Архитектором.
3. Замер в браузере на одной витрине: время до/после (база 12.10 — в выводе пробы).
4. Realtime/DebugView — дополнительно, не вместо п.1.
