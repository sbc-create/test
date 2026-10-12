# games-story — «Сюжет пройден» (вариант A: chapter-guides)

Гайды по сюжетным играм по главам: маршрут (участки из источника), новые механики, коллекционные предметы, стороны,
прогресс по главе, проверенные видео. Игры сайта — по реестру `config/ownership.yaml`; сейчас — Celeste.

```bash
bin/games-story start | stop | status          # preview http://127.0.0.1:8857/ (loopback, noindex)
bin/games-story test
bin/games-story qa --shots docs/screenshots/<sha> --out docs/verification-browser-qa.json
python3 qa/viewports.py 8857
bin/games-story build --commit HEAD
bin/games-story sources chapters <url>… | collectible <url>… | video <id>… | check
bin/games-story content validate | build
```

Документы: `docs/AUDIT.md`, `docs/SEO-MATRIX.md`, `docs/ACTION-MAP.md`, `DECISIONS.md`, `OWNERSHIP.yaml`, `REPORT.md`.
