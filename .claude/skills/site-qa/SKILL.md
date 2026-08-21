---
name: site-qa
description: Прогнать полный QA-контур сайта — SEO, E2E, accessibility, visual, security, производительность. Использовать после сборки и после каждого деплоя на staging.
allowed-tools: Read, Grep, Glob, Bash(python3 -m factory verify *), Bash(python3 -m factory seo-* *), Bash(pytest *), Bash(npx playwright *)
---

# site-qa

Порядок и обязательные ворота:

1. `python3 -m factory seo-lint --site <id>` — статические проверки сборки.
2. `python3 -m factory seo-crawl --site <id> --base <url>` — обход реального HTTP:
   статусы, цепочки редиректов, canonical, robots/noindex, sitemap, дубли title/H1/
   description, пагинация и прямое открытие page N, orphan pages, глубина, крошки.
3. `python3 -m factory seo-render --site <id>` — mobile rendered HTML, видимость
   lazy-контента и плеера, ошибки console/network.
4. `python3 -m factory verify --site <id>` — сводные ворота: security smoke (закрытость
   `.env`, бэкапов, installer, debug, directory listing; заголовки; cookies; mixed content),
   a11y, visual, lab-бюджеты производительности.
5. E2E и cross-browser: `npx playwright test` (chromium, firefox, webkit; mobile + desktop).

Отчёт по каждому шагу — в `artifacts/qa/<site_id>/`. Ни один шаг нельзя объявить
пройденным без файла отчёта с фактическим exit code.
