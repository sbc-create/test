# games-rpg — «Гайды RPG» (вариант A: codex-sections)

Справочник по ролевым играм: спутники (раса, класс, предыстория, характеристики), основы билдов по таблице класса,
квесты с отмечаемыми этапами, механики; версия игры (патч) на виду. Игры сайта — по реестру `config/ownership.yaml`.

```bash
bin/games-rpg start | stop | status       # preview http://127.0.0.1:8859/ (loopback, noindex)
bin/games-rpg test
bin/games-rpg qa --shots docs/screenshots/<sha> --out docs/verification-browser-qa.json
python3 qa/viewports.py 8859
bin/games-rpg build --commit HEAD
bin/games-rpg sources import <тип> <url>… | reparse | check
bin/games-rpg content validate | build
```
