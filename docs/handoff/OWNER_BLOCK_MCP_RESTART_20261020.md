# Блок владельца: перезапуск `site-factory-mcp` (сверено SEO-сессией 20.10)

Основа — `docs/OWNER_BLOCK_MCP_RESTART.md` (ветка claude/nova-publish-memory-02). Здесь исправлено одно ожидание, которое
сорвало бы приёмку правильного перезапуска.

## Что проверено

| факт | значение | как установлено |
|---|---|---|
| сервер | **claude-control-01** | `/etc/hostname`; cgroup `/system.slice/site-factory-mcp.service` (сверка wt-nova-02) |
| юнит | `/etc/systemd/system/site-factory-mcp.service`, `User=claude`, **`WorkingDirectory=/home/claude/wt-portable-site-cell-01`** | файл юнита |
| строка запуска | базовый юнит: `… --read-only`; **дополнение `site-factory-mcp.service.d/10-write-mode.conf` заменяет её на запуск БЕЗ `--read-only`** (пишущие инструменты моста) | файлы юнита и дополнения |
| код после перезапуска | из рабочей копии `wt-portable-site-cell-01`, ветка `claude/nova-publish-memory-01`: правка авторства накладки (c8eb270 → перенос 7f37574), замок публикации (4ff8f35), проверка года в названии (e3f8366) | git; тесты editorial/editor/qwen/regular/mcp — 1009 passed |

**Поправка к блоку wt-nova-02:** после верного перезапуска `--read-only` в командной строке **НЕ появится** — его снимает
`10-write-mode.conf`, и так задумано: в режиме только чтения мост не сможет публиковать вовсе. Приёмка
`after-mcp-restart.py` в нынешнем виде требует `--read-only` и отметит правильный перезапуск как провал — её пункт 2
нужно читать как «строка запуска совпадает с действующим описанием юнита (с дополнениями)».

## Действия (на claude-control-01)

```bash
# 1. До: что перезапускаем и что ничего не идёт
systemctl show -p MainPID,ActiveState,ExecMainStartTimestamp site-factory-mcp
systemctl cat site-factory-mcp | grep -n 'ExecStart'          # ожидание: последняя ExecStart — без --read-only
tail -1 /home/claude/wt-portable-site-cell-01/var/editor-runs/gate.jsonl   # не должно быть "run": true
python3 - <<'EOF'
import fcntl, glob
занято = []
for п in glob.glob('/srv/sites/*/runtime/overlays/*/.publish.lock'):
    f = open(п, 'r')
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(f, fcntl.LOCK_UN)
    except BlockingIOError:
        занято.append(п)
print('замки публикации заняты:', занято or 'нет — перезапуск безопасен')
EOF

# 2. Перечитать описание юнита и перезапустить
sudo systemctl daemon-reload
sudo systemctl restart site-factory-mcp

# 3. После
systemctl show -p MainPID,ActiveState,ExecMainStartTimestamp site-factory-mcp
tr '\0' ' ' < /proc/$(systemctl show -p MainPID --value site-factory-mcp)/cmdline; echo
curl -s http://127.0.0.1:9000/healthz
```

Ожидание шага 3: `ActiveState=active`; `MainPID` ≠ 1499831; `ExecMainStartTimestamp` — сегодняшний; строка запуска
`/usr/bin/python3 -m factory.qwen.mcp --http 127.0.0.1:9000` **без** `--read-only`; `/healthz` — 200, `read_only: false`.

## Приёмка и снятие паузы (делает сессия)

1. Процесс новее правки: время старта службы > mtime `factory/qwen/editorial.py` в рабочей копии.
2. Первая публикация на одной витрине Lords/Zona (zonafilm.space — первой, по решению 19.10) → `overlay-provenance-diff.py --domain zonafilm.space`: ни одной новой подмены сверх 3 исторических.
3. Только после этого из `seo_operator/editor_run.py: PAUSED_PUBLISH` снимаются записи с причиной «MCP editorial.py затирает поля editorial-overrides.json» — по одной витрине, с той же проверкой после первой публикации на каждой. Другие паузы (lordserials22.info до 21.10, заморозки) не трогаются.

## После приёмки: второй перезапуск (MOD-102)

Согласовано с wt-nova-02 20.10. Правку `b72229c` (ветка `claude/nova-publish-memory-02`) переносим cherry-pick'ом только после приёмки первого перезапуска на zonafilm.space: она меняет `подготовить` в `factory/qwen/editorial.py` — черновик, у которого в `sources` есть shikimori-id, а `aired_on` расходится с годом снимка, получает отказ `BLOCKED_INPUT`. Перенос проверяется так:
- `tests/unit/test_editorial_year_source.py` — 13 проверок;
- `tests/unit -k "editorial or qwen or overlay"`.

После переноса — второй перезапуск по тому же блоку (шаги 1–3).
