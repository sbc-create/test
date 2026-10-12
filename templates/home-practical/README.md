# home-practical — «Удобный дом» (вариант B: problem-checklists)

Хранение, организация пространства, мебель и небольшие улучшения. Навигация от проблемы: «что мешает дома» →
решения по порядку → инструкция-чек-лист, где каждый шаг отмечается, есть прогресс и «Следующий шаг».
Компактный каталог — таблица с фильтрами-переключателями и сортировкой. Сравнение с вариантом A — `docs/VARIANTS.md`.

## Команды (из `templates/home-practical`)

```bash
bin/home-practical start | stop | status          # preview http://127.0.0.1:8852/ (только loopback, noindex)
bin/home-practical test                           # pytest шаблона
bin/home-practical qa --shots docs/screenshots/<sha> --out docs/verification-browser-qa.json
python3 qa/viewports.py 8852                      # все URL sitemap × 320/390/768/1440
bin/home-practical build --commit HEAD            # статический артефакт var/home-practical/build/<sha>
bin/home-practical sources ikea <url>… | quotes | reparse | check   # факты источников (allowlist, robots)
bin/home-practical content validate | build       # проверка материалов против фактов → data/content.json
npm ci --prefix qa                                # axe-core 4.13.0 только для этого шаблона
```

## Данные

- `data/sources/src-*.json` — факты 15 открытых и прочитанных страниц (13 карточек IKEA, 2 страницы CPSC Anchor It!).
- `data/sources/manual/*.yaml` — ручные цитаты; при импорте каждая сверяется с текстом страницы.
- `data/materials/*.json` — 13 инструкций (6 помещений, 4 задачи); `data/content.json` — единственный вход сайта.

Документы: `docs/AUDIT.md`, `docs/SEO-MATRIX.md`, `docs/ACTION-MAP.md`, `DECISIONS.md`, `OWNERSHIP.yaml`, `REPORT.md`.
