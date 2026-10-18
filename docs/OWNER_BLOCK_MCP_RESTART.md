# Блок владельца: перезапуск `site-factory-mcp` на claude-control-01

Одно действие. Нужно затем, чтобы правка авторства накладки (`c8eb270`) начала
работать: служба держит код **2026-10-12 17:42Z**, а правка записана
**2026-10-18 20:39Z**. Пока служба не перезапущена, публикации описаний на семи
витринах Lords/Zona остаются на паузе.

**Почему не делаю сам.** `systemctl` не входит в профиль сессии
(`UNATTENDED_SAFE`), а в `inventory/ssh-hosts.yaml: sudo_allowlist` разрешены
только `nginx -t`, `systemctl reload nginx` и перезапуск восьми витрин
`nova-*` на k2-zomro-01 — `site-factory-mcp` там нет. Ограничения доступа ради
своей команды я не меняю.

## Подготовка — выполнена, можно не повторять

| проверка | результат 2026-10-18 21:13Z |
| --- | --- |
| правка в рабочем каталоге службы | да: `состав_правок(живые, [], остальные)` в `/home/claude/wt-portable-site-cell-01/factory/qwen/editorial.py`, mtime 20:39:16Z |
| проверки в том же дереве | `pytest tests/unit/test_editorial_overlay_authorship.py tests/unit/test_editorial_fix_installed.py` → **30 passed** |
| служба принадлежит systemd | pid 1499831, PPid 1, cgroup `/system.slice/site-factory-mcp.service` — постороннего процесса на порту нет |
| операция в полёте | нет: незакрытых прогонов редактора 0, последний завершён 19:33:35Z, шлюз в 21:10 ответил `run: false` (удержание доли до 21:15:20Z) |
| расхождение с юнитом | живой процесс запущен БЕЗ `--read-only`, хотя юнит (от 03.10) этот флаг объявляет — systemd держит устаревшее описание в памяти |

## Действия

На **claude-control-01** (этот же сервер, где лежит рабочее дерево):

```bash
# 1. До: зафиксировать, что перезапускаем и что ничего не идёт
systemctl show -p MainPID,ActiveState,ExecMainStartTimestamp site-factory-mcp
tail -1 /home/claude/wt-portable-site-cell-01/var/editor-runs/gate.jsonl

# 2. Перечитать описание юнита и перезапустить
sudo systemctl daemon-reload
sudo systemctl restart site-factory-mcp

# 3. После: процесс новый и соответствует юниту
systemctl show -p MainPID,ActiveState,ExecMainStartTimestamp site-factory-mcp
tr '\\0' ' ' < /proc/$(systemctl show -p MainPID --value site-factory-mcp)/cmdline; echo
```

Ожидаемый результат шага 3: `ActiveState=active`, `MainPID` ОТЛИЧАЕТСЯ от
1499831, `ExecMainStartTimestamp` — сегодняшний, и в командной строке процесса
появляется **`--read-only`** (его сейчас нет).

`daemon-reload` нужен именно из-за последней строки: без него systemd снова
запустит процесс по описанию, которое держит в памяти с 12.10.

## Приёмка, которую сделаю я

```bash
cd /home/claude/wt-nova-publish-memory-02
python3 automation/local/service-code-freshness.py --unit site-factory-mcp.service
cd /home/claude/wt-portable-site-cell-01
python3 automation/local/editorial-fix-installed.py
```

Ожидается: первая — «код не новее запуска»; вторая — «правка подтверждена».
Возраст процесса и дата файлов — диагностика; подтверждением считается вторая
проверка плюс публикация ниже.

## Что идёт сразу после приёмки

1. линия SEO снимает техническую паузу с **zonafilm.space** (одна витрина, не
   все семь);
2. одна разрешённая публикация описания;
3. `editorial-overlay-before-after --compare` обязан дать код 0 и
   «подменено авторство: 0»; я проверяю опубликованный текст на живой странице;
4. при ненуле публикации останавливаются и вывод присылается мне: значит есть
   третий путь записи состава, которого я не нашёл;
5. остальные витрины — по одной, с той же сверкой. **lordserials22.info — не
   раньше 21.10** (действующая пауза оценки), независимые ограничения
   замороженных домéнов и опыты T075, T087, T191 сохраняются.

## Цена и риск

Перезапуск обрывает соединения моста на время старта (`RestartSec=5`). Сейчас
ни одна партия редактора не идёт, поэтому обрывать нечего; если запускать после
21:15Z, стоит повторить шаг 1 и убедиться, что `gate` отвечает `run: false`.
`Restart=on-failure` и `StartLimitBurst=5` на месте: неудачный старт systemd
повторит, а после пяти неудач остановится — это видно в `ActiveState`.
