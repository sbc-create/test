# food-appliances — «Готовим в технике»

Рецепты для мультиварки и аэрогриля. Сверху рецепта — табло прибора: режим, температура и
время, каждое значение ведёт к своему шагу. Собственный дизайн «панель прибора»: графит,
янтарный индикатор, моноширинные цифры (`static/css/panel.css`). JavaScript не нужен.

## Команды (из `templates/food-appliances`)

```bash
bin/food-appliances start | stop | status   # preview http://127.0.0.1:8850/ (только loopback, noindex)
bin/food-appliances test                    # pytest шаблона
bin/food-appliances qa --shots docs/screenshots/<sha> --out docs/verification-browser-qa.json
bin/food-appliances build --commit HEAD     # статический артефакт в var/food-appliances/build/<sha>
bin/food-appliances import --only aerogril  # факты eda.rambler.ru (allowlist, robots, задержка)
bin/food-appliances drafts validate | build # проверка черновиков против фактов → data/content.json
bin/food-appliances audit                   # замеры референсов → docs/audit-measurements.json
npm ci --prefix qa                          # axe-core 4.13.0 только для этого шаблона
```

## Данные

- `data/facts/*.json` — факты источника без текста шагов (64 записи, 19 полных).
- `data/drafts/*.json` — 12 черновиков. Ссылаются на индексы фактов; проходят `drafts.validate`.
- `data/content.json` — единственный вход сайта; `data/history.jsonl` — версии.

Документы: `docs/AUDIT.md`, `docs/SEO-MATRIX.md`, `DECISIONS.md`, `OWNERSHIP.yaml`, `REPORT.md`.
