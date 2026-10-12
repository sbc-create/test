# garden-season — «Дача по сезону» (вариант B: region-timeline)

Сначала регион: главная — выбор региона источника, страница региона — вертикальная лента года только с его
сроками и фильтрами-чипами. Работа — шкала года по регионам и компактная раскладка. Сайт запоминает регион.
Сравнение с вариантом A — `docs/VARIANTS.md`.

## Команды (из `templates/garden-season`)

```bash
bin/garden-season start | stop | status          # preview http://127.0.0.1:8854/ (loopback, noindex)
bin/garden-season test                           # pytest шаблона
bin/garden-season qa --shots docs/screenshots/<sha> --out docs/verification-browser-qa.json
python3 qa/viewports.py 8854                     # все URL sitemap × 320/390/768/1440
bin/garden-season build --commit HEAD            # статический артефакт var/garden-season/build/<sha>
bin/garden-season sources osu <url>… | quotes | reparse | check
bin/garden-season content validate | build
```

## Данные

- `data/sources/src-*.json` — 12 календарей OSU (330 пунктов с регионом) и 2 руководства RHS (цитаты с регионом).
- `data/materials/*.json` — 14 работ; `data/content.json` — единственный вход сайта.

Документы: `docs/AUDIT.md`, `docs/SEO-MATRIX.md`, `docs/ACTION-MAP.md`, `DECISIONS.md`, `OWNERSHIP.yaml`, `REPORT.md`.
