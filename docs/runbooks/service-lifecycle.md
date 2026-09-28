# Эксплуатация управляющей службы

## Что где лежит

| Что | Путь |
|---|---|
| Юнит | `/etc/systemd/system/site-factory-control-api.service` |
| Настройки и токены | `/etc/site-factory/control-api.env` (root:claude 0640) |
| Релизы (неизменяемые) | `/srv/site-factory/control-api/releases/<полный SHA>/` |
| Действующая версия | `/srv/site-factory/control-api/current` → релиз |
| Предыдущая версия | `/srv/site-factory/control-api/previous` → релиз |
| Манифест | `/srv/site-factory/control-api/release-manifest.json` |
| Состояние фабрики | `/srv/site-factory/repo` (через `FACTORY_ROOT`) |

Код неизменяем, состояние общее. Иначе откат уносил бы вместе с кодом задания,
поставленные новой версией.

## Обычные действия

```bash
systemctl status site-factory-control-api
curl -s http://127.0.0.1:8790/api/v1/ready          # готовность
bash automation/host/deploy-control-api.sh status   # что сейчас работает
```

## Выкладка

```bash
bash automation/host/deploy-control-api.sh deploy <sha>
bash automation/host/deploy-control-api.sh deploy <sha> --dry-run   # только ворота
```

Порядок: сборка релиза из коммита → собственное окружение → отпечаток →
**протокол запуска как ворота** → подмена ссылки одним действием → перезапуск →
ожидание готовности. Если готовность не подтвердилась за 60 секунд, скрипт
откатывается сам и завершается ошибкой.

## Откат

```bash
bash automation/host/deploy-control-api.sh rollback            # на предыдущую
bash automation/host/deploy-control-api.sh rollback --to <sha> # на конкретную
```

Откат проходит **тот же** протокол запуска. Версия, не прошедшая проверку, не
станет рабочей только оттого, что она старая.

## Пробы

| Проба | Механизм | Что означает отказ |
|---|---|---|
| Запуск | `Type=notify`, `READY=1`, `TimeoutStartSec=90` | протокол не пройден либо сокет не открылся |
| Живость | `WatchdogSec=60`, отметка вдвое чаще | цикл обслуживания завис |
| Готовность | `GET /api/v1/ready` | идёт слив либо каталог состояния стал недоступен |

Готовность отвечает без токена и без подробностей: её опрашивает supervisor и
балансировщик, а не человек. Подробности — в `/api/v1/metrics`, где нужен токен.

## Завершение

`SIGTERM` → служба перестаёт принимать запросы (новые получают `503` с
`Retry-After`), дожидается начатых до `SITE_ENGINE_DRAIN_SECONDS` (25 с),
затем выходит. `TimeoutStopSec=40` намеренно больше слива.

## Разбор частых состояний

**Служба не поднимается.** `journalctl -u site-factory-control-api -n 40`.
Протокол печатает построчный отчёт; строка `FAIL` называет причину. Код возврата
70 — протокол не пройден, 65 — нет профилей, 64 — не задан `SITE_ENGINE_HTTP`.

**`config.writable: WARN`.** Каталог профилей закрыт на запись для учётной
записи службы. Это не поломка: чтение, задания и инвалидация работают, а
изменение настройки отвечает `503 config_read_only`. Включить запись —
осознанное решение владельца:
```bash
sudo chown claude:claude /srv/site-factory/repo/config/site-profiles
```

**Цикл перезапусков.** `StartLimitBurst=5` за `StartLimitIntervalSec=300`
останавливает службу вместо бесконечного перезапуска. Снять:
`systemctl reset-failed site-factory-control-api`.

**Предел частоты сработал не там, где ждали.** В ответе `429` есть `limit_key` —
он называет ключ: среда, витрина, действующее лицо или операция.

**Ответ `degraded: true` у предела.** Хранилище счётчика недоступно, действует
строгий счётчик в памяти. Смотреть `site_engine_ratelimit_degraded_total` и
права на `var/state`.
