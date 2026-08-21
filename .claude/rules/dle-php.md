---
paths:
  - "blueprints/**"
  - "plugins/**/*.php"
  - "themes/**/*.php"
  - "factory/blueprint.py"
---

# DLE и PHP

- Базовая версия — DLE 20.0. Переход на более новую версию только после отдельной
  compatibility-проверки и нового knowledge freeze.
- Ядро DLE не модифицируется. Расширения — через официальную plugin system / virtual
  file system, шаблоны и поддерживаемые точки расширения.
- Изменяемые каталоги берутся **только** из `blueprints/dle20/profiles/paths.yaml`.
  Профиль не заполнен → `BLOCKED_INPUT`. Угадывать пути запрещено (§3.8).
- Immutable release отделён от shared mutable data (uploads, cache, logs, config, secrets).
- world-writable прав в production нет. Веб-процессу выдаётся минимум, проверяемый тестом.
- Отдельные database/schema и DB user на каждый сайт. Общая учётная запись запрещена.
- Installer и временные точки входа удаляются/блокируются сразу после успешной установки.
- Cron-задачи только из `blueprints/dle20/cron/jobs.yaml`: без дублей, с lock, timeout,
  логом и ограниченным retry.
- Любой PHP-файл проходит `php -l` перед сборкой (`factory build` делает это сам).
