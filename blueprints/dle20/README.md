# blueprints/dle20

Воспроизводимый blueprint DataLife Engine 20.0. **Лицензионный архив здесь не хранится**
(`.gitignore`: `blueprints/dle20/dist/`) — в git попадают только метаданные и контрольные суммы
(`inventory/dle-distributions.yaml`).

| Файл | Назначение |
|------|------------|
| `profiles/paths.template.yaml` | шаблон профиля путей и требований; копируется в `paths.yaml` и заполняется из официальной документации |
| `cron/jobs.template.yaml` | декларативный manifest cron-задач |
| `webserver/` | шаблоны конфигурации веб-сервера |

Проверка: `python3 -m factory blueprint check`.
Пока `profiles/paths.yaml` отсутствует или помечен `source_required: true`,
установка DLE возвращает `BLOCKED_INPUT` — это защита правила «не угадывать пути».
