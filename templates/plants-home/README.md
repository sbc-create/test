# plants-home — «Домашние растения», вариант C `my-collection`

Вариант C: «мои растения» — сводка ядовитости и света по своей коллекции и этикетки ухода для печати. Порт 8869, ключи `ph-mine:*`.
Вариант A — ветка `claude/template-plants-home`, B — `claude/template-plants-home-b`.

Каталог комнатных растений: карточки видов с фильтром по свету и сложности ухода; карточка — паспорт условий по справочнику,
уход по темам (свет, полив, температура, влажность, почва, подкормка, цветение, размножение), проблемы, чек-лист, источник.

```bash
bin/plants-home start | stop | status            # preview http://127.0.0.1:8869/ (loopback, noindex)
bin/plants-home test
bin/plants-home qa --shots docs/screenshots/<sha> --out docs/verification-browser-qa.json
python3 qa/viewports.py 8869
bin/plants-home build --commit HEAD
bin/plants-home sources ncsu <url>… | reparse | check
bin/plants-home content validate | build
```

Данные: `data/sources/src-*.json` — 16 страниц NC State Extension (14 опубликовано), `data/materials/*.json` — 14 карточек.
Документы: `docs/AUDIT.md`, `docs/SEO-MATRIX.md`, `docs/ACTION-MAP.md`, `DECISIONS.md`, `OWNERSHIP.yaml`, `REPORT.md`.
