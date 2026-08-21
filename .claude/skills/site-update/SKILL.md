---
name: site-update
description: Обновить DLE, тему или плагины существующего сайта. Использовать для планового обновления и патчей безопасности.
allowed-tools: Read, Grep, Glob, Bash(python3 -m factory validate *), Bash(python3 -m factory build *), Bash(python3 -m factory deploy *), Bash(python3 -m factory verify *)
---

# site-update

1. Смена мажорной версии DLE требует отдельной compatibility-проверки и нового
   knowledge freeze (`/research-freeze`). Автоматический переход запрещён.
2. Backup БД и mutable data — до обновления. Проверь восстановимость, а не наличие файла.
3. Обновление идемпотентно: повторный запуск не создаёт дубль cron job, сертификата,
   DNS-записи или релиза.
4. Сначала staging: `build` → `deploy --environment staging` → полный `site-qa`.
5. Production — только после зелёного staging, при `production_authorized: true`,
   с готовым планом отката.
6. После обновления сравни матрицу индексируемости с фактическим рендером: изменения
   шаблонов не должны молча менять canonical, robots или пагинацию.
