# SEO-отчёт — pilot-local

Итог: FAILED

Критических: 0, серьёзных: 2, малых: 0

## seo-lint — passed

Счётчики: `{"sitemap_urls": 45, "routes": 48, "indexable": 45, "in_sitemap": 45, "paginated": 2, "redirects": 4}`

Находок нет.

## seo-crawl — passed

Счётчики: `{"fetched": 45, "unique_urls": 45, "max_depth": 4, "titles": 45, "internal_links": 45}`

Находок нет.

## seo-render — FAILED

Счётчики: `{"status": "skipped"}`

| severity | check | url | сообщение |
|---|---|---|---|
| major | browser | `http://127.0.0.1:8082` | Браузерная проверка не выполнялась (--skip-browser): приёмка неполная. |

## security-smoke — passed

Счётчики: `{"checked_paths": 8, "root_status": 200}`

Находок нет.

## acceptance-routes — passed

Счётчики: `{"routes": 11}`

Находок нет.

## performance-budget — passed

Счётчики: `{"lab_lcp_ms_max": null, "lab_cls_max": null, "lab_transfer_bytes_max": null, "budgets": {"lab_lcp_ms": 2500, "lab_cls": 0.1, "lab_total_bytes": 800000, "field_targets": {"lcp_ms": 2500, "inp_ms": 200, "cls": 0.1}}, "field_targets_note": "Полевые LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 на 75-м перцентиле измеряются только на реальном трафике."}`

| severity | check | url | сообщение |
|---|---|---|---|
| major | performance | `-` | Метрики не собраны: браузерная проверка пропущена флагом. |
