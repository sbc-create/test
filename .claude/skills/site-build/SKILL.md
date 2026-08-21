---
name: site-build
description: Детерминированно собрать сайт из пакета, blueprint и темы. Использовать после успешной валидации, до любого деплоя.
allowed-tools: Read, Grep, Glob, Bash(python3 -m factory build *), Bash(python3 -m factory plan *), Bash(php -l *)
---

# site-build

1. `python3 -m factory plan --site <site_id>` — план без мутаций. Убедись, что
   `mutations: 0` и перечень шагов соответствует ожиданию.
2. `python3 -m factory build --site <site_id>`:
   - `build_id` считается от нормализованного пакета + версии blueprint + версии темы;
   - повторный запуск с теми же входами даёт тот же `build_id` (идемпотентность);
   - результат — `var/build/<site_id>/<build_id>/` и `build-manifest.json`.
3. Сборка обязана провалиться, а не подставить умолчание, если:
   отсутствует `alt` у публикуемого изображения; тип страницы не описан в матрице;
   шаблон требует поле, которого нет в пакете; профиль путей DLE не заполнен.
4. Проверь `artifacts/build/<site_id>/<build_id>/report.json`: счётчики страниц по типам,
   список пропущенных материалов с причинами.
