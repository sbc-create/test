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

## Восстановление управляющего сервера claude-control-01

Порядок для случая, когда потерян сам сервер, а не отдельный сайт. Конкретика
хоста — в [`INFRASTRUCTURE.md`](INFRASTRUCTURE.md).

### Что нужно иметь

| Компонент | Где лежит | Замечание |
| --- | --- | --- |
| Код и история | GitHub `sbc-create/test` | плюс `repo-latest.bundle` в `/srv/backups` — восстанавливает историю без GitHub |
| Состояние фабрики | `/srv/backups/host-<stamp>.tar.gz` | `var/`, конфигурация хоста, vhost'ы, `/srv/sites` |
| Доказательство восстановимости | `/srv/backups/host-<stamp>.verified.json` | архив без такой записи восстановимым не считается |
| Учётные данные стендов | **не в бэкапе** | генерируются заново идемпотентной провизией |
| Секреты интеграций | внешнее хранилище владельца | по `secret_ref`, в git их нет |

Бэкапы лежат на том же диске, что и сам сервер: **внешнего хранилища не
передано**. Потеря диска — потеря локальных бэкапов; уцелеет только то, что
есть в GitHub. Это открытый пункт, а не решённый.

### Порядок

```bash
# 1. Новый сервер: Ubuntu 22.04, пользователь claude с ключом, sudo.
# 2. Репозиторий.
sudo install -d -o claude -g claude /srv/site-factory /srv/sites /var/log/site-factory
sudo install -d -o claude -g claude -m 0750 /srv/backups
git clone https://github.com/sbc-create/test.git /srv/site-factory/repo
#    без GitHub: git clone /path/to/repo-latest.bundle /srv/site-factory/repo

# 3. Окружение (те же версии, что в CI).
cd /srv/site-factory/repo
uv venv --python 3.11 --seed .venv
SEO_SESSION_FORCE_SETUP=1 ./.claude/hooks/session-start.sh
npm ci
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers npx playwright install chromium firefox webkit

# 4. База стенда blueprint'а — иначе восемь шагов прогона упрутся в BLOCKED_INPUT.
sudo .venv/bin/python -m factory db provision --scope anime
sudo chown -R claude:claude var/db

# 5. Состояние из бэкапа (после проверки записи .verified.json).
tar -xzf /srv/backups/host-<stamp>.tar.gz -C /tmp/restore
rsync -a /tmp/restore/factory-var/ /srv/site-factory/repo/var/

# 6. Расписание и проверка.
sudo automation/host/install-units.sh
.venv/bin/python -m factory knowledge verify
./scripts/verify.sh
bash tests/run-all.sh
```

Совпадение `build_id` с последним успешным результатом задания — доказательство
того, что воспроизведён тот же релиз, а не похожий.

### Проверка самого бэкапа

`automation/host/site-factory-backup.sh` не считает архив бэкапом, пока не
распакует его во временный каталог и не сверит SHA-256 каждого файла с
манифестом, снятым с источника. Запись `.verified.json` появляется только после
этого. Health-check отдельно следит за возрастом последней такой записи и
поднимает алерт, если подтверждённого бэкапа нет вовсе.
