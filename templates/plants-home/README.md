# plants-home — «Домашние растения» (вариант B: pick-and-diagnose)

Подбор по условиям (свет, уход, дети/животные) с честной ядовитостью, таблица сравнения видов, карточка «уход + если … то»,
диагностика «что случилось». Сравнение с вариантом A — `docs/VARIANTS.md`.

```bash
bin/plants-home start | stop | status            # preview http://127.0.0.1:8856/ (loopback, noindex)
bin/plants-home test
bin/plants-home qa --shots docs/screenshots/<sha> --out docs/verification-browser-qa.json
python3 qa/viewports.py 8856
bin/plants-home build --commit HEAD
bin/plants-home sources ncsu <url>… | reparse | check
bin/plants-home content validate | build
```

Данные: `data/sources/src-*.json` — 16 страниц NC State Extension (14 опубликовано), `data/materials/*.json` — 14 карточек.
Документы: `docs/AUDIT.md`, `docs/SEO-MATRIX.md`, `docs/ACTION-MAP.md`, `DECISIONS.md`, `OWNERSHIP.yaml`, `REPORT.md`.
