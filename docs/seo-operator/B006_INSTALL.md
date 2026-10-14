# B006 — самостоятельный цикл технического SEO: установка на claude-control-01

Окончательная редакция — 14.10, вечер. Заменяет утреннюю. Всё, кроме блока команд root, сессия сделала и проверила сама; доказательства — в разделе «Что проверено до установки».

## Что получится после установки

| Звено | Служба | Модель | Что делает |
| --- | --- | --- | --- |
| Подготовка | `seo-tech-run.service` по таймеру `seo-tech-run.timer` | да | берёт следующую задачу `queued`, Claude Code без интерфейса готовит ветку в отдельной рабочей копии, вердикт по следам (VERIFIED / INCOMPLETE) |
| Пополнение | внутри подготовки, когда очередь пуста (не чаще раза в час) | нет | ставит задачи из диагностики регулярной проверки, аудита ссылок и страниц (раз в сутки) и переносов (`port_to`) в `var/seo-tech/auto-tasks.json` |
| Выпуск | `seo-tech-publish.service` по таймеру `seo-tech-publish.timer` | нет | выпускает VERIFIED штатным путём: fast-forward ветки выпуска → CI → `factory cell trigger` → итог исполнителя → проверка работающего сайта |

**Ритм.** Следующая задача начинается через минуту после завершения предыдущей (`OnUnitInactiveSec=1min`). Страховка — запуск раз в 15 минут. Пустая очередь проверяется командой `seo-tech-next --peek` без модели, около секунды.

**Один исполнитель.** `flock` на `var/seo-tech/run.lock`; второй запуск выходит с кодом 75. Systemd не запускает второй экземпляр активного oneshot.

**Подготовка и выпуск разделены.**
- У подготовки нет учётных данных git: `InaccessiblePaths=~/.config/gh, ~/.ssh`.
- У выпуска нет модели.
- **VERIFIED** — проверенная подготовка, а не публикация.
- **Опубликовано** — исполнитель установил выпуск (stage `live_verified`) и работающий сайт прошёл проверку здоровья.
- **`live_verified` задачи** — проверка работающего сайта по полю `live_check`. Без `live_check` итог честно `released`.

**Изменения Архитектора (Zona, publisher_id).** Выпуск ждёт, а не выпускает, если:
- на ветке выпуска есть невыпущенный коммит, например чужой publisher_id;
- голова ветки выпуска не равна живому коммиту;
- общий клон грязный или не на живом коммите.

Если ветка задачи не стоит на живом коммите, задача уходит на повторную подготовку (SUPERSEDED), а не перебазируется вслепую. Если правка уже на сайте через чужой выпуск, она только проверяется.

## Восстановление и ошибки

| Случай | Что происходит |
| --- | --- |
| Тайм-аут модели | `timeout -k 60 1500`: SIGTERM, через 60 с SIGKILL; вердикт INCOMPLETE записан, попытка засчитана |
| Зависла проверка | вердикт под `timeout -k 60 2400`; если его добили — следующий прогон закрывает захват как INTERRUPTED |
| `systemctl stop`, тайм-аут юнита, OOM, перезагрузка | systemd убивает все процессы юнита. Захват несёт pid, время старта и boot_id владельца, поэтому мёртвый владелец освобождает задачу сразу: INTERRUPTED, попытка засчитана. Предел сверху — 2 ч, даже если владелец жив, но завис |
| Погиб только сценарий, а процесс модели остался | модель держит `run.lock` до своего тайм-аута (≤ 1 560 с), второго исполнителя не возникает; затем задача восстанавливается как выше |
| Повторы | не больше 3 неудачных попыток (INCOMPLETE, INTERRUPTED, CLAIM_FAILED) на задачу; дальше она в `var/seo-tech/attention.json` для сессии, а очередь идёт дальше |
| Захват одной задачи невозможен (нет репозитория, git отказал) | записывается CLAIM_FAILED, берётся следующая задача |
| Нет файла задания, исполнителя, git, timeout, модуля | код 70 **до** захвата: попытка не тратится |
| Состояние недоступно для записи, файл блокировки не открывается | код 73 — не путается с «занято» (75) |

## Что проверено до установки (сессия, 14.10)

- **Тесты.** `tests/unit/test_seo_tech_b006.py` и `tests/unit/test_seo_tech_run.py` — 51 passed: восстановление, счёт попыток, устойчивость очереди, слияние задач пополнения, решения выпуска (в том числе «чужой невыпущенный коммит» и «клон не на живом»), пополнение, коды обёртки 73/75/70.
- **Имитация полного цикла настоящей обёрткой** — `automation/local/seo-tech-b006-sim.py`, модель подменена, всё остальное штатное:
  - две задачи подряд, вторая через 61 с после первой без ручного запуска;
  - SIGKILL всего прогона → INTERRUPTED → та же задача доведена до VERIFIED;
  - пустая очередь — код 0 без модели.
  - Отчёт — `var/test-seo-tech/sim/20261014T173501-15dc/report.json` (повтор: `python3 automation/local/seo-tech-b006-sim.py`).
- **Приёмочный сценарий** `automation/local/seo-tech-acceptance.py` проверен на этой имитации: rc 0.
- **Выпуск — сухой прогон на настоящем состоянии** (`seo-tech-publish --dry-run`): уже опубликованные сессией T078–T089 не трогаются, чужие коммиты распознаются.
- **Пополнение на настоящих данных:** 0 задач. Сайты по автоматическим признакам чисты: 84 проверенные ссылки и 15 страниц на двух сайтах, без отклонений; в тестах на заведомых дефектах задачи ставятся.

## Блок владельца (root на claude-control-01)

Выполнен 14.10 в 18:38:15Z (время — `var/seo-tech/b006-installed-at.txt`). Ниже — исправленная редакция для повторной установки: латинские имена переменных, юниты проверяются до установки, ошибка резервного копирования останавливает блок.

```bash
set -euo pipefail
INSTALLED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
REPO_ROOT=/home/claude/wt-portable-site-cell-01
UNIT_SRC="$REPO_ROOT/automation/host/editor"
UNITS="seo-tech-run.service seo-tech-run.timer seo-tech-publish.service seo-tech-publish.timer"
cd "$REPO_ROOT"

# 1. Источники: коммит, отпечатки, синтаксис, тесты, очередь, доступ к GitHub
sudo -u claude git -C "$REPO_ROOT" log -1 --format='%H %s'
sudo -u claude sha256sum -c "$UNIT_SRC/B006.sha256"
bash -n "$UNIT_SRC/seo-tech-run.sh"
bash -n "$UNIT_SRC/seo-tech-publish.sh"
sudo -u claude python3 -m pytest -q tests/unit/test_seo_tech_b006.py tests/unit/test_seo_tech_run.py
PEEK_RC=0
sudo -u claude python3 -m seo_operator.cli seo-tech-next --peek || PEEK_RC=$?
echo "peek rc=$PEEK_RC (10 — есть задачи, 0 — нет)"
[ "$PEEK_RC" = 0 ] || [ "$PEEK_RC" = 10 ]
sudo -u claude gh auth status

# 2. Юниты проверяются ДО установки — по исходным файлам
(cd "$UNIT_SRC" && systemd-analyze verify $UNITS)

# 3. Сохранить прежнюю конфигурацию; ошибка копирования останавливает блок
BACKUP_DIR=/root/systemd-backup-seo-tech-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$BACKUP_DIR"
for unit in $UNITS; do
  if [ -e "/etc/systemd/system/$unit" ]; then
    cp -a "/etc/systemd/system/$unit" "$BACKUP_DIR/"
    echo "сохранён $unit"
  else
    echo "прежнего $unit нет"
  fi
done
ls -la "$BACKUP_DIR"

# 4. Установка и повторная проверка установленных юнитов
for unit in $UNITS; do
  install -m 0644 "$UNIT_SRC/$unit" "/etc/systemd/system/$unit"
done
(cd /etc/systemd/system && systemd-analyze verify $UNITS)
systemctl daemon-reload

# 5. Включение таймеров и первый запуск
systemctl enable --now seo-tech-run.timer seo-tech-publish.timer
systemctl start --no-block seo-tech-run.service
echo "$INSTALLED_AT" | sudo -u claude tee "$REPO_ROOT/var/seo-tech/b006-installed-at.txt"
systemctl list-timers 'seo-tech-*' --no-pager
```

**Откат установки** (ошибки не скрываются):

```bash
set -euo pipefail
systemctl disable --now seo-tech-run.timer seo-tech-publish.timer
systemctl stop seo-tech-run.service seo-tech-publish.service
for unit in seo-tech-run.service seo-tech-run.timer seo-tech-publish.service seo-tech-publish.timer; do
  rm -f "/etc/systemd/system/$unit"
  if [ -e "$BACKUP_DIR/$unit" ]; then cp -a "$BACKUP_DIR/$unit" /etc/systemd/system/; fi
done
systemctl daemon-reload
```

## Приёмка после установки

Одного `timer=enabled` недостаточно. Нужны три подтверждения.

1. **Две задачи подряд без ручного запуска второй.** В очереди T090, T091, T092 (`queued`), каждая 5–15 минут. Примерно через 40 минут:
   ```bash
   sudo -u claude python3 /home/claude/wt-portable-site-cell-01/automation/local/seo-tech-acceptance.py --since "$(cat /home/claude/wt-portable-site-cell-01/var/seo-tech/b006-installed-at.txt)"
   ```
   Раздел A, `ok: true`: пара задач с `gap_s` ≤ 120.
2. **Восстановление после прерывания.** Пока идёт прогон (`systemctl is-active seo-tech-run.service` → `activating`), прервать его:
   ```bash
   systemctl kill --signal=SIGKILL seo-tech-run.service
   ```
   Через 2–3 минуты повторить приёмочный сценарий. Раздел B, `ok: true`: запись INTERRUPTED, и та же задача снова взята таймером.
3. **Состояние публикации.** Раздел C сценария: по каждой задаче — подготовка (вердикт) и выпуск (итог `seo-tech-publish`: `live_verified`, `released`, `waiting` с причиной). Журнал — `var/seo-tech/publish.jsonl`.

Сессия при следующем входе сама прогонит приёмку и отчитается по A, B, C.

## Известные ограничения

- `MemoryMax=3G` у подготовки — с запасом под стенд Animedia на полном снимке. Свободно около 5 ГиБ при исчерпанном swap. При OOM задача восстанавливается (INTERRUPTED), но повторяется до 3 раз.
- Yummy в пополнение и выпуск не входит: код страниц — в контейнере Next.js, вне ячеек (B016, T081 — действие владельца).
- Восемь новых доменов Lords — вне продвижения и вне цикла (CLOSED).
- Пополнение не придумывает работу: при чистых сайтах очередь пустеет. Задачи сессии и переносы (`port_to`) по-прежнему ставит сессия в `config/seo-tech-queue.json`.
