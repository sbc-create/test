# Аварийное восстановление

## Что нужно для восстановления фабрики

| Компонент | Где хранится | Как восстановить |
|-----------|--------------|------------------|
| Код фабрики | git-репозиторий | `git clone` |
| База знаний | `knowledge/` + `KNOWLEDGE_FREEZE.yaml` | из git; целостность — `factory knowledge verify` |
| Site packages | `sites/` | из git (без секретов) |
| Секреты | внешнее хранилище / переменные окружения | по `secret_ref` из пакета и inventory |
| Дистрибутив DLE | вне git | из личного кабинета владельца лицензии; сверить SHA-256 |
| Бэкапы сайтов | `var/backups/` и целевые хосты | по `backup.ref` из результата задания |
| Состояние заданий | `var/state/` | восстанавливается из очереди и артефактов |

`var/` намеренно вне git: это runtime-состояние. Потеря `var/` не мешает восстановить
сайты — сборка детерминирована и воспроизводится из пакета.

## Порядок

```bash
git clone <repo> && cd <repo>
pip3 install -r requirements.txt
python3 -m factory knowledge verify           # база знаний цела
python3 -m factory env-report                 # чего не хватает на хосте
bash tests/run-all.sh                         # фабрика работоспособна
python3 -m factory build --site <id>          # тот же build_id, что и до аварии
```

Совпадение `build_id` с последним успешным результатом задания — доказательство того,
что воспроизведён тот же релиз.

## Worker как сервис

```ini
# /etc/systemd/system/dle-factory.service
[Unit]
Description=DLE Site Factory worker
After=network-online.target

[Service]
Type=oneshot
User=factory
WorkingDirectory=/srv/factory
Environment=FACTORY_CLOSED_WORLD=1
ExecStart=/usr/bin/python3 -m factory resume
```

```ini
# /etc/systemd/system/dle-factory.timer
[Unit]
Description=Run DLE Site Factory worker regularly

[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
AccuracySec=30s

[Install]
WantedBy=timers.target
```

`Type=oneshot` вместо бесконечного цикла: каждый запуск конечен, идемпотентен и
продолжает с последнего checkpoint. После перезагрузки таймер поднимает worker сам.

## Проверка восстановимости

Плановая, по `backup_policy.restore_test` (`each_release` для пилота):
`tests/integration/test_backup_restore.py` разворачивает архив во временный каталог и
сравнивает содержимое. Наличие файла бэкапа доказательством не считается.
