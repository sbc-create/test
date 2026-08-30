# Откат обновления каталога Lords

Откат должен вести в состояние, которое существует на диске, а не в намерение.
Здесь записано, что именно менялось, чем это откатывается и как проверить, что
откат состоялся.

## Что изменено 2026-08-30 (HOTFIX-LORDS-CONTENT-REFRESH-TIMER-01)

Разрешение владельца распространялось ровно на два юнита:
`lords-content-refresh.service` и `lords-content-refresh.timer`. Ничего другого
не трогалось.

| Что | Было | Стало |
| --- | --- | --- |
| `TimeoutStartSec` службы | 3 ч | **8 ч** |
| `OnUnitActiveSec` таймера | 10 мин (из основного юнита) + 120 мин | **9 ч**, со сбросом списка |
| состояние таймера | `enabled`, но `inactive` | `enabled` и `active` |
| источник drop-in | только диск, вне репозитория | `automation/host/systemd/dropins/` |

## Снимок состояния до правки

```
/var/lib/lords-content-refresh/rollback-20260830T181147Z/
  lords-content-refresh.service
  lords-content-refresh.timer
  lords-content-refresh.service.d/{timeout.conf,retention.conf}
  lords-content-refresh.timer.d/interval.conf
  timer-state.txt
```

Путь к последнему снимку лежит в
`/var/lib/lords-content-refresh/last-rollback-point`.

`timer-state.txt` фиксирует, чем всё было: `ActiveState=inactive`,
`UnitFileState=enabled`, `TimeoutStartUSec=3h`, `Result=timeout`.

## Как откатиться

```bash
SNAP=$(cat /var/lib/lords-content-refresh/last-rollback-point)
sudo cp -a "$SNAP/lords-content-refresh.service.d" /etc/systemd/system/
sudo cp -a "$SNAP/lords-content-refresh.timer.d"   /etc/systemd/system/
sudo systemctl daemon-reload
systemctl show lords-content-refresh.service -p TimeoutStartUSec --value   # ждём 3h
```

Откатывать ли при этом сам таймер в `inactive` — отдельное решение, и по
умолчанию **не надо**: неактивный таймер и был неисправностью, а не настройкой.
Если он всё же нужен остановленным:

```bash
sudo systemctl stop lords-content-refresh.timer
```

## Чего откат не трогает

Разложенные релизы. Они живут своей жизнью: у каждой витрины хранятся текущий и
предыдущий, и возврат к предыдущему — это переключение символической ссылки
`current`, без пересборки и простоя. Откат настроек службы на релизы не влияет.

## Как убедиться, что всё на месте

```bash
systemctl is-active  lords-content-refresh.timer     # active
systemctl is-enabled lords-content-refresh.timer     # enabled
systemctl list-timers lords-content-refresh.timer    # строка со временем, не пусто
python3 -m factory.lords.refresh_watchdog            # ok, код возврата 0
```

Последняя команда — сторож, который различает ровно три неисправности: таймер
включён при загрузке, но не запущен; таймер активен, но не тикает; обновлений
давно не было. Каждая даёт критический уровень и код возврата 2.
