# SEO-отчёт — pilot-local

Итог: FAILED

Критических: 27, серьёзных: 0, малых: 0

## seo-lint — passed

Счётчики: `{"sitemap_urls": 45, "routes": 48, "indexable": 45, "in_sitemap": 45, "paginated": 2, "redirects": 4}`

Находок нет.

## seo-crawl — passed

Счётчики: `{"fetched": 45, "unique_urls": 45, "max_depth": 4, "titles": 45, "internal_links": 45}`

Находок нет.

## seo-render — FAILED

Счётчики: `{"status": "failed", "exit_code": 2}`

| severity | check | url | сообщение |
|---|---|---|---|
| critical | browser | `http://127.0.0.1:8082` | Браузерная проверка завершилась без отчёта: Error: page.goto: net::ERR_CONNECTION_REFUSED at http://127.0.0.1:8082/lekcii/page/2/
Call log:
[2m  - navigating to "http://127.0.0.1:8082/lekcii/page/2/" |

## security-smoke — FAILED

Счётчики: `{"checked_paths": 8, "root_status": 0}`

| severity | check | url | сообщение |
|---|---|---|---|
| critical | headers | `/` | Отсутствует заголовок X-Content-Type-Options. |
| critical | headers | `/` | Отсутствует заголовок X-Frame-Options. |
| critical | headers | `/` | Отсутствует заголовок Referrer-Policy. |
| critical | headers | `/` | Отсутствует заголовок Content-Security-Policy. |
| critical | staging | `/` | Staging не отдаёт X-Robots-Tag: noindex. |
| critical | staging | `/` | Staging доступен без авторизации (HTTP 0). robots.txt защитой не считается. |
| critical | exposure | `/.env` | Служебный путь доступен публично (HTTP 0). |
| critical | exposure | `/.git/config` | Служебный путь доступен публично (HTTP 0). |
| critical | exposure | `/routes.json` | Служебный путь доступен публично (HTTP 0). |
| critical | exposure | `/build-manifest.json` | Служебный путь доступен публично (HTTP 0). |
| critical | exposure | `/shared/logs/php-server.log` | Служебный путь доступен публично (HTTP 0). |
| critical | exposure | `/backups/` | Служебный путь доступен публично (HTTP 0). |
| critical | exposure | `/install.php` | Служебный путь доступен публично (HTTP 0). |
| critical | exposure | `/engine/data/config.php` | Служебный путь доступен публично (HTTP 0). |

## acceptance-routes — FAILED

Счётчики: `{"routes": 11}`

| severity | check | url | сообщение |
|---|---|---|---|
| critical | acceptance | `/` | Ожидался 200, получен 0. |
| critical | acceptance | `/lekcii/` | Ожидался 200, получен 0. |
| critical | acceptance | `/lekcii/page/2/` | Ожидался 200, получен 0. |
| critical | acceptance | `/lekcii/material-01/` | Ожидался 200, получен 0. |
| critical | acceptance | `/praktikum/serial-fikstura/season-1/episode-1/` | Ожидался 200, получен 0. |
| critical | acceptance | `/praktikum/serial-fikstura/season-1/episode-3/` | Ожидался 200, получен 0. |
| critical | acceptance | `/news/` | Ожидался 200, получен 0. |
| critical | acceptance | `/legal/terms/` | Ожидался 200, получен 0. |
| critical | acceptance | `/search/` | Ожидался 200, получен 0. |
| critical | acceptance | `/lekcii/page/999/` | Ожидался 404, получен 0. |
| critical | acceptance | `/arhiv/` | Ожидался 404, получен 0. |

## major-findings-budget — passed

Счётчики: `{"status": "ok", "major": 0, "budget": 25}`

Находок нет.

## performance-budget — FAILED

Счётчики: `{"status": "failed", "lab_lcp_ms_max": null, "lab_cls_max": null, "lab_transfer_bytes_max": null, "budgets": {"lab_lcp_ms": 2500, "lab_cls": 0.1, "lab_total_bytes": 800000, "field_targets": {"lcp_ms": 2500, "inp_ms": 200, "cls": 0.1}}, "field_targets_note": "Полевые LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 на 75-м перцентиле измеряются только на реальном трафике."}`

| severity | check | url | сообщение |
|---|---|---|---|
| critical | performance | `-` | Метрики не собраны: браузерная проверка недоступна (failed). |
