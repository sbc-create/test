# games-rpg — «Гайды RPG», вариант C `index-compare`

Вариант C: указатель А–Я по всем материалам и сравнение предметов. Порт 8871, ключи `grpg-index:*`.
Вариант A — ветка `claude/template-games-rpg`, B — `claude/template-games-rpg-b`.

Справочник по ролевым играм: спутники (раса, класс, предыстория, характеристики), основы билдов по таблице класса,
квесты с отмечаемыми этапами, механики; версия игры (патч) на виду. Игры сайта — по реестру `config/ownership.yaml`.

```bash
bin/games-rpg start | stop | status       # preview http://127.0.0.1:8871/ (loopback, noindex)
bin/games-rpg test
bin/games-rpg qa --shots docs/screenshots/<sha> --out docs/verification-browser-qa.json
python3 qa/viewports.py 8871
bin/games-rpg build --commit HEAD
bin/games-rpg sources import <тип> <url>… | reparse | check
bin/games-rpg content validate | build
```
