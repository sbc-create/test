# games-survival — «База выживания» (вариант A: craft-tree)

Справочник по игре на выживание: предметы и блоки с рецептами по сетке крафта, ресурсы, биомы; связи
«из чего делается» и «что можно сделать» — из рецептов источника; версия игры на виду. Игры сайта — по реестру `config/ownership.yaml`.

```bash
bin/games-survival start | stop | status       # preview http://127.0.0.1:8861/ (loopback, noindex)
bin/games-survival test
bin/games-survival qa --shots docs/screenshots/<sha> --out docs/verification-browser-qa.json
python3 qa/viewports.py 8861 /poisk/?q=факел /nesushchestvuet/
bin/games-survival build --commit HEAD
bin/games-survival sources import <тип> <url>… | reparse | check
bin/games-survival content validate | build
```
