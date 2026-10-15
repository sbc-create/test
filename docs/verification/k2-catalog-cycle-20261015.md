# Цикл регулярных обновлений каталога K2 — измерение 2026-10-15

§5 задания: подтвердить обе стороны цикла фактом, с расписанием и последним
результатом каждого таймера.

## Приёмщик — на узле витрин `k2-zomro-01` (root)

```
$ systemctl list-timers k2-catalog-apply.timer --all --no-pager
NEXT                        LEFT   LAST                        PASSED      UNIT
Thu 2026-10-15 12:29:45 UTC 10min  Thu 2026-10-15 12:14:45 UTC 4min 49s    k2-catalog-apply.timer
$ grep OnCalendar\|OnUnitActive\|OnBoot\|Persistent /etc/systemd/system/k2-catalog-apply.timer
OnBootSec=3min
OnUnitActiveSec=15min
Persistent=true
$ systemctl show k2-catalog-apply.service -p Result -p ExecMainStatus -p ExecMainExitTimestamp
Result=success
ExecMainStatus=0
ExecMainExitTimestamp=Thu 2026-10-15 12:14:45 UTC
```

Состояние — **active**, последний исход — успех с кодом 0. Расписание: через
3 минуты после загрузки, далее каждые 15 минут, пропущенный такт
догоняется (`Persistent=true`).

## Установленный каталог — все восемь витрин

```
$ python3 /home/k2deploy/stage/k2-catalog-state.py        # на узле, exit 0
lords-10 revision=7479a9a98cd6f1b90bcfda16046c2cb7 items=64734 installed_at=2026-10-15T11:44Z details_mib=84 incoming_pending=нет
lords-11 … 11:44Z   lords-12 … 11:44Z   lords-13 … 11:45Z
lords-14 … 11:45Z   lords-15 … 11:45Z   lords-16 … 11:45Z
lords-17 revision=7479a9a98cd6f1b90bcfda16046c2cb7 items=64734 installed_at=2026-10-15T11:46Z details_mib=84 incoming_pending=нет
итог: витрин 8, с проблемами 0
```

Ревизия одна и та же у всех восьми — так и должно быть: каталог общий, восемь
витрин получают один комплект. Свежесть — тот же день; необработанных
комплектов в `incoming/` нет; подробности на месте (84 МиБ на витрину).

## Отправитель — на управляющем узле `claude-control-01` (пользовательский юнит)

Файлы на месте, расписание объявлено:

```
$ ls -l ~/.config/systemd/user/k2-catalog-deliver.user.{service,timer}
-rw-rw-r-- 1 claude claude 2513 Oct 15 11:51 …/k2-catalog-deliver.user.service
-rw-rw-r-- 1 claude claude 1086 Oct 15 11:51 …/k2-catalog-deliver.user.timer
$ grep OnCalendar\|Persistent\|RandomizedDelay\|ExecStart ~/.config/systemd/user/k2-catalog-deliver.user.*
timer:   OnCalendar=*-*-* 05:20:00 UTC
timer:   Persistent=true
timer:   RandomizedDelaySec=300
service: ExecStart=/bin/bash automation/local/k2-deliver-catalog.sh lords-10 … lords-17
```

**Не включён**, и это измерено, а не предположено:

```
$ ls -l ~/.config/systemd/user/timers.target.wants/
seo-daily-cycle.timer -> …                      # чужой таймер SEO-сессии
seo-engine-topvisor-inventory.timer -> …        # чужой таймер SEO-сессии
# ссылки k2-catalog-deliver.user.timer здесь нет
```

Включение требует `systemctl --user`, а он в профиль UNATTENDED_SAFE не входит
(измерено в этой сессии: отказ и на `--user`). Одна строка оператору на
`claude-control-01` под учётной записью `claude`:

```bash
systemctl --user daemon-reload && \
  systemctl --user enable --now k2-catalog-deliver.user.timer && \
  systemctl --user list-timers k2-catalog-deliver.user.timer --no-pager
```

До включения доставка идёт разовым запуском сценария вручную — он и выполнен
сегодня (ревизии выше), поэтому отсутствие таймера свежесть каталога прямо
сейчас не ломает, но суточный цикл без него не самостоятелен.

## Полный цикл — проверен отдельно

Прогон доставки и установки одним комплектом: ревизия на узле сменилась,
приём занял 117 с при пределе `TimeoutStartSec=900` (запас семикратный).
Доказательство — `docs/verification/k2-eight-interfaces-20261014.md` и запись
в `docs/K2_PUBLIC_RELEASE_20261015.md`.
