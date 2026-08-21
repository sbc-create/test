# Эксплуатация

## Ежедневные команды

```bash
python3 -m factory status                       # очередь и все задания
python3 -m factory status --site <id> --json
python3 -m factory report --site <id>           # последний результат задания
python3 -m factory resume                       # добрать очередь после простоя
python3 -m factory env-report                   # что доступно на управляющем хосте
tail -f var/audit/audit.jsonl                   # журнал мутаций (redacted)
```

## Одноразовый локальный стенд

Цель `local-disposable` поднимает сайт на `127.0.0.1` встроенным сервером PHP поверх
атомарных релизов и роутера `automation/local/router.php`. Роутер отдаёт статусы и
заголовки ровно по `routes.json`, поэтому пилот проверяет реальный SEO-контур, а не
просмотр файлов.

```bash
python3 -m factory deploy --site pilot-local          # поднять и проверить
python3 -m factory verify --site pilot-local          # ворота качества
python3 -m factory rollback --site pilot-local        # откат на предыдущий релиз
```

Учётные данные стенда лежат в `var/targets/local-disposable/<site_id>/staging-auth`
(права 0600, вне git). Они генерируются локально и не публикуются в отчётах.

## Непрерывная работа

Worker'ом служит `factory resume`, запускаемый супервизором (systemd timer, cron с
`flock` или внешний планировщик). Требования, заложенные в код:

- задание забирается из `queue/inbox` атомарным `rename` — двойной обработки нет;
- состояние живёт в `var/state/<job_id>.json` и переживает restart;
- зависшие в `processing` задания возвращаются в `inbox` (`--max-age`, по умолчанию час);
- завершённое задание при повторном запуске возвращает сохранённый результат;
- бесконечный shell-цикл не используется: каждый вызов конечен и идемпотентен.

Пример unit-файла — в `docs/DISASTER_RECOVERY.md`.

## Ретенция

`retention_policy` пакета задаёт сроки для бэкапов, логов и артефактов. Очистка —
внешняя задача по расписанию; фабрика ничего не удаляет за пределами `keep_releases`.
