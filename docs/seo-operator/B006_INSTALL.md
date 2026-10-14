# B006 — установка seo-tech-run на claude-control-01 (один блок для владельца)

Подготовлено 14.10. Всё, кроме двух команд `sudo`, сессия проверила сама. Установка — действие root, потому что юнит ставится в `/etc/systemd/system`.

## Что ставится

- **Учётная запись запуска:** `claude:claude`. Это не root; прогоны редактора идут под ней же.
- **Рабочий каталог:** `/home/claude/wt-portable-site-cell-01`.
- **Сценарий:** `automation/host/editor/seo-tech-run.sh` (полный текст — ниже).
- **Юнит:** `automation/host/editor/seo-tech-run.b006.service`. Взят §7 Архитектора (`ca37c4e`), запись разрешена только в `~/.claude` и `var/` репозитория. Добавлен запрет доступа к `/etc/site-factory`.
- **Таймер:** `automation/host/editor/seo-tech-run.b006.timer`, каждые 30 минут в :12 и :42. Это вне сетки editor-run. Если задачи `queued` нет, прогон выходит за секунды и модель не вызывает.

## Свойства, подтверждённые сессией

| Свойство | Как обеспечено | Доказательство |
| --- | --- | --- |
| Берёт следующую задачу | `tech_run.candidates()`: статус `queued`, без вердикта, без живого захвата, попыток меньше 3; порядок — по долям направлений | тесты `test_next_task_skips_live_claim_retries_and_done`, `test_order_follows_allocation_lagging_direction_first`; 14.10 вручную взяты подряд T078 → T079 → T080, T083 → T084, T088 → T089 |
| Сохраняет прогресс | `var/seo-tech/claims.jsonl`, `runs.jsonl`, `next.json` и ветка с коммитом в `.git` витрины; всё на диске, перезапуск не теряет | 14.10 вердикты T083 записаны и пересчитаны повторно по тем же следам |
| Нет одновременных дублей | `flock -n` на `var/seo-tech/run.lock` — второй запуск выходит с кодом 75; атомарный захват задачи; зависший захват старше 2 ч снимается один раз | замер 14.10 15:37Z: при занятом замке rc=75, захвата нет; тесты `test_claim_is_atomic_second_claim_refused`, `test_stale_lock_is_reclaimed_once`, `test_run_id_cannot_claim_twice` |
| Ошибки | нет задания — 70 до захвата; сбой захвата — 70; модель не справилась или тайм-аут 1 500 с — вердикт INCOMPLETE, код 2, попытка засчитана (не больше 3); итог решает проверка по следам, а не самоотчёт | тесты `test_wrapper_refuses_before_claim_without_prompt`, `test_no_commit_is_not_verified`, `test_exit_code_2_is_unusable`; 14.10 T083 INCOMPLETE ×2 → дефект найден и исправлен (d080112) |
| Не публикует | учётные данные git закрыты юнитом; вердикт требует, чтобы ветки на удалённом не было | шаг `not_pushed` в каждом вердикте |
| Пустая очередь | выход 0 без вызова модели | замер 14.10 15:37Z: rc=0, записей прогона 0 |

Очередь к установке: T090, T091, T092 — перенос T086 на три Lords, `queued`. Сессия их не берёт: они оставлены для проверки первого цикла таймера.

## Команды владельца (claude-control-01, root)

```bash
# 1. Предусловия (§7 Архитектора; при невыполнении команда сама откажет)
bash -o pipefail -c '
КОРЕНЬ=/home/claude/wt-portable-site-cell-01
test -s "$КОРЕНЬ/config/seo-tech-queue.json" || { echo "ОТКАЗ: нет очереди"; exit 1; }
python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$КОРЕНЬ/config/seo-tech-queue.json" || { echo "ОТКАЗ: очередь не JSON"; exit 1; }
test -s "$КОРЕНЬ/automation/host/editor/seo-tech-run.sh" || { echo "ОТКАЗ: нет сценария"; exit 1; }
(cd "$КОРЕНЬ" && sudo -u claude python3 -m seo_operator.cli seo-tech-verify --help >/dev/null 2>&1) || { echo "ОТКАЗ: нет seo-tech-verify"; exit 1; }
echo "предусловия выполнены"'

# 2. Установка
sudo install -m 0644 /home/claude/wt-portable-site-cell-01/automation/host/editor/seo-tech-run.b006.service /etc/systemd/system/seo-tech-run.service
sudo install -m 0644 /home/claude/wt-portable-site-cell-01/automation/host/editor/seo-tech-run.b006.timer   /etc/systemd/system/seo-tech-run.timer
sudo systemd-analyze verify /etc/systemd/system/seo-tech-run.service /etc/systemd/system/seo-tech-run.timer
sudo systemctl daemon-reload
sudo systemctl enable --now seo-tech-run.timer && echo "ГОТОВО: таймер включён"

# 3. Проверка сразу после установки
systemctl list-timers seo-tech-run.timer --no-pager
```

## Проверка полного цикла без открытого чата

Через 30–60 минут после установки:

```bash
journalctl -u seo-tech-run.service --since "-2h" --no-pager | tail -40   # root или группа adm
tail -3 /home/claude/wt-portable-site-cell-01/var/seo-tech/gate.jsonl          # "trigger": "systemd-timer", next_rc 10
tail -1 /home/claude/wt-portable-site-cell-01/var/seo-tech/runs.jsonl          # T090: "verdict": "VERIFIED", "trigger": "systemd-timer"
systemctl --failed --no-pager | grep seo-tech || echo "сбоев юнита нет"
```

Признаки успешного цикла:
- в `gate.jsonl` запись с `"trigger": "systemd-timer"`;
- в `runs.jsonl` вердикт по T090 с тем же триггером;
- в репозитории lordfilm47-space локальная ветка `claude/seo-tech-t090-…`, без удалённого двойника.

Сессия проверит это по следам, когда получит доступ к чату. Выпуск подготовленной ветки остаётся за сессией (`cell trigger`), не за таймером.

## Известный риск

`MemoryMax=2G`. Ручные прогоны 14.10 шли без этого предела. Lords проверяются на урезанном снимке. Animedia поднимает стенд на полном снимке (~70 МБ JSON); если упрётся в предел, юнит упадёт по памяти (OOM в журнале). Тогда поднять предел до 3G.

## Полный текст сценария `automation/host/editor/seo-tech-run.sh`

```bash
#!/usr/bin/env bash
# Один прогон технического SEO: захват задачи → Claude Code без интерфейса готовит
# ветку в отдельной рабочей копии → вердикт ПО СЛЕДАМ (seo-tech-verify) → запись.
#
#   seo-tech-run.sh                 — штатно (из seo-tech-run.service)
#   CLAUDE_BIN=/path seo-tech-run.sh — подмена исполнителя для проверки обёртки
#
# Push, PR и выпуск прогону не принадлежат: учётные данные git закрыты юнитом
# (InaccessiblePaths), а вердикт требует, чтобы у ветки не было удалённого двойника.
# Коды: 0 — VERIFIED или честное «задач нет»; 2 — неполный (юнит падает — это
# уведомление); 75 — занято другим прогоном; 70 — шаг захвата неисправен.
set -uo pipefail

REPO=/home/claude/wt-portable-site-cell-01
STATE="$REPO/var/seo-tech"
CLAUDE_BIN="${CLAUDE_BIN:-/home/claude/.local/bin/claude}"
TRIGGER="${SEO_TECH_TRIGGER:-manual}"
LIMIT_S="${SEO_TECH_TIMEOUT:-1500}"

mkdir -p "$STATE"
cd "$REPO" || exit 1

exec 9>"$STATE/run.lock"
if ! flock -n 9; then
  echo "seo-tech-run: идёт другой прогон" >&2
  exit 75
fi

# Задание проверяется ДО захвата: без него прогон съел бы попытку исправной
# задачи (приёмка Архитектора 12.10, seo-tech-wrapper-audit.py).
test -s docs/seo-tech/SEO_TECH_RUN_PROMPT.md || { echo "seo-tech-run: нет файла задания" >&2; exit 70; }

# Секунды плюс PID: два прогона в одну секунду не делят один идентификатор
# (иначе вердикт уходил первой совпавшей задаче — измерено приёмкой).
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

NEXT="$(python3 -m seo_operator.cli seo-tech-next --run-id "$RUN_ID")"
NEXT_RC=$?
printf '{"at": "%s", "trigger": "%s", "run_id": "%s", "next_rc": %s}\n' "$STARTED" "$TRIGGER" "$RUN_ID" "$NEXT_RC" >> "$STATE/gate.jsonl"
case "$NEXT_RC" in
  10) ;;
  0) exit 0 ;;
  *) echo "seo-tech-run: захват неисправен (код $NEXT_RC): $NEXT" >&2; exit 70 ;;
esac

PROMPT="$(sed "s/{{RUN_ID}}/$RUN_ID/g" docs/seo-tech/SEO_TECH_RUN_PROMPT.md)"
timeout "$LIMIT_S" "$CLAUDE_BIN" -p "$PROMPT" --output-format json \
  --max-turns "${SEO_TECH_MAX_TURNS:-150}" \
  > "$STATE/$RUN_ID.claude.json" 2> "$STATE/$RUN_ID.stderr"
MODEL_RC=$?
FINISHED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

EXTRA="$(printf '{"trigger": "%s", "started_at": "%s", "finished_at": "%s", "model_exit": %s}' \
  "$TRIGGER" "$STARTED" "$FINISHED" "$MODEL_RC")"
python3 -m seo_operator.cli seo-tech-verify --run-id "$RUN_ID" --record --extra "$EXTRA" \
  > "$STATE/$RUN_ID.verify.json"
exit $(( $? == 0 ? 0 : 2 ))
```

## Полный текст `seo-tech-run.b006.service`

```ini
[Unit]
Description=Техническое SEO сети: один подготовительный прогон (seo-tech-run)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=oneshot
User=claude
Group=claude
WorkingDirectory=/home/claude/wt-portable-site-cell-01
Environment=HOME=/home/claude
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=SEO_TECH_TRIGGER=systemd-timer
ExecStart=/usr/bin/bash /home/claude/wt-portable-site-cell-01/automation/host/editor/seo-tech-run.sh
# 0 — VERIFIED или «задач нет»; 75 — занято другим прогоном (не сбой).
# 2 — неполный вердикт, 70 — неисправен шаг захвата: юнит падает и виден в systemctl --failed.
SuccessExitStatus=0 75
TimeoutStartSec=1800
Nice=10
CPUQuota=50%
MemoryMax=2G
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectKernelTunables=yes
RestrictSUIDSGID=yes
# «Только готовит ветку» — свойство юнита: без учётных данных git push невозможен.
InaccessiblePaths=/home/claude/.config/gh
InaccessiblePaths=/home/claude/.ssh
InaccessiblePaths=/etc/site-factory
# Пишет только: состояние Claude Code и var/ репозитория (очередь-состояние, рабочие копии, .git витрин).
ReadWritePaths=/home/claude/.claude
ReadWritePaths=/home/claude/wt-portable-site-cell-01/var

[Install]
WantedBy=multi-user.target
```

## Полный текст `seo-tech-run.b006.timer`

```ini
[Unit]
Description=Техническое SEO сети: прогон каждые 30 минут (seo-tech-run)

[Timer]
# :12 и :42 — вне пятиминутной сетки editor-run. Нет задачи queued — выход 0 за секунды, без модели.
OnCalendar=*:12/30
Persistent=false
AccuracySec=10s
Unit=seo-tech-run.service

[Install]
WantedBy=timers.target
```
