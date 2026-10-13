# games-survival — «База выживания», вариант C `inventory-first`

Вариант C: «что сделать из того, что есть» — отметки инвентаря → что можно собрать сейчас и чего не хватает. Порт 8872, ключи `gsv-inv:*`.
Вариант A — `claude/template-games-survival`, B — `claude/template-games-survival-b`.

Планировщик крафта: выберите предмет и количество — шаги по порядку (отметки сохраняются) и базовые ресурсы по сетке источника. Плюс справочник: предметы и блоки с рецептами по сетке крафта, ресурсы, биомы; связи
«из чего делается» и «что можно сделать» — из рецептов источника; версия игры на виду. Игры сайта — по реестру `config/ownership.yaml`.

```bash
bin/games-survival start | stop | status       # preview http://127.0.0.1:8872/ (loopback, noindex)
bin/games-survival test
bin/games-survival qa --shots docs/screenshots/<sha> --out docs/verification-browser-qa.json
python3 qa/viewports.py 8872 '/planirovshchik/?item=fakel&n=16' '/planirovshchik/?item=x&n=0' /poisk/?q=факел /nesushchestvuet/
bin/games-survival build --commit HEAD
bin/games-survival sources import <тип> <url>… | reparse | check
bin/games-survival content validate | build
```
