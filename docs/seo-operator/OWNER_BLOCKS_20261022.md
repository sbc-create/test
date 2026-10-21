# Блоки владельца на 22.10: T262 (animedia.icu) и перезапуск MCP

Подготовила сессия wt-portable-site-cell-01-dc в ночь 21→22.10. Каждое ожидание ниже проверено на хосте этой ночью; где проверить нельзя, так и написано.

Оба блока исполняются на **claude-control-01** под пользователем `claude` (sudo — только где написано), в `bash`. Каждый блок начинается с `set -euo pipefail`: любая ошибка останавливает выполнение.

---

## 1. T262 — страницы жанров в карте animedia.icu

**Что выпускается.** Коммит f8327f9 уже на ветке выпуска: страницы жанров `/catalog/?genre=<код>` попадают в карту. CI на нём упал в 19.10 13:42Z (run 39262418279), и упала ровно одна проверка, `updater-conformity`: `FileNotFoundError …/animedia-01-update-state.json`. Без манифеста шаблона (как на раннере CI) обработчик обновления падал. Патч `T262_form_a.patch` меняет только `automation/animedia-data-update.py`: без манифеста карта пишется без жанров, а с манифестом ошибка не глушится.

**Репетиция 21.10 19:12–19:53Z (локальный клон, f8327f9, переменные как на раннере CI: `CI=true`, без манифеста шаблона и боевого снимка).**
- База: `checks/updater_conformity.py` падает с той же `FileNotFoundError …animedia-01-update-state.json`, что настоящий CI (run 39262418279).
- С патчем: полный `checks/run.sh` rc 0, без провалов.
- На хосте без этих переменных `sitemap-live` падает и на базе, и на патче: витрина требует `config/player.json`, если видит боевой снимок. Это свойство среды, а не патча: в CI `sitemap-live` проходила и на f8327f9.

**Состояние на 21.10 ≈19:40Z.**
- Живой выпуск — `releases/55c7b719a5df`.
- Ветка `claude/extract-animedia-icu-seo-01` на origin стоит на f8327f9.
- Последняя проверка доступа исполнителя — 19.10 07:18Z. Она действует 12 ч, поэтому её надо повторить (шаг 4). Без неё заявку отвергнут.
- `MemAvailable` 2,78 ГиБ при пороге 2,5 ГиБ.

```bash
set -euo pipefail
REPO=/home/claude/wt-portable-site-cell-01/var/site-repos/animedia-icu
PATCH=/home/claude/wt-portable-site-cell-01/var/patches/T262_form_a.patch
BR=claude/extract-animedia-icu-seo-01
BASE=f8327f9386156a5922e88dbe963ec759b666700c
PREV=55c7b719a5dfb468ae9de425a8bfa6ce07ae0973
PREV_DIGEST=sha256:ce437076917ab7fa61a3c95b8462e723d8abf2478eda4ed5fabd99a6c8d83323
WT=/home/claude/t262-release-$(date -u +%Y%m%dT%H%M%SZ)
cd /home/claude/wt-portable-site-cell-01

# 1. Исходная версия и патч
echo "aa2f30bfea254aceb5aeb7dadce4ee9fe3a766ca035d40df49155979f1e41c20  $PATCH" | sha256sum -c -
git -C "$REPO" fetch origin "$BR"
test "$(git -C "$REPO" rev-parse "origin/$BR")" = "$BASE"                 # ветка не сдвинулась
test "$(readlink /srv/animedia-icu/current)" = "/srv/animedia-icu/releases/${PREV:0:12}"   # живой — 55c7b719a5df

# 2. Изолированная рабочая копия (существующую копию сессии не трогаем)
git -C "$REPO" worktree add --detach "$WT" "$BASE"
cd "$WT"
test -z "$(git status --porcelain)"
git apply --check "$PATCH"
git apply "$PATCH"
test "$(git diff --name-only)" = "automation/animedia-data-update.py"     # ровно один файл
env -u LORDS_TEMPLATE_MANIFEST ANIMEDIA_TEMPLATE_MANIFEST=/nonexistent ANIMEDIA_RUNTIME_ROOT=/nonexistent \
    python3 checks/updater_conformity.py                                   # режим CI: должен пройти
python3 checks/updater_conformity.py                                       # режим хоста: должен пройти

# 3. Коммит только этого файла и обычный push (не force): если ветка сдвинулась, push откажет
git add -- automation/animedia-data-update.py
git commit -m "T262: обработчик обновления не падает без манифеста шаблона (раннер CI); с манифестом ошибка не глушится"
NEW=$(git rev-parse HEAD); echo "NEW=$NEW"
git push origin "HEAD:refs/heads/$BR"

# 4. CI именно этого коммита — ждать до завершения; не success — стоп
sleep 20
RUN=$(gh run list --repo sbc-create/site-animedia-icu --commit "$NEW" --workflow release --json databaseId --jq '.[0].databaseId')
test -n "$RUN"
gh run watch "$RUN" --repo sbc-create/site-animedia-icu --exit-status
test "$(gh run view "$RUN" --repo sbc-create/site-animedia-icu --json headSha,conclusion --jq '.headSha+" "+.conclusion')" = "$NEW success"

# 5. Свежая проверка доступа исполнителя (исполнитель разбирает очередь раз в минуту)
cd /home/claude/wt-portable-site-cell-01
python3 -m factory cell submit --site animedia-01 --cell-operation access-check
sleep 120
python3 - <<'EOF'
import glob, json, os, time
f = max(glob.glob('/var/lib/site-cells/results/animedia-01-access-*.json'), key=os.path.getmtime)
age = (time.time() - os.path.getmtime(f)) / 60
o = json.load(open(f))['outcome']
print(f, f'{age:.0f} мин', o)
assert age < 10 and o.get('repo_read') and o.get('actions_read'), 'доступ исполнителя не подтверждён'
EOF

# 6. Ресурсы непосредственно перед выпуском
python3 -c "import re;m=int(re.search(r'MemAvailable:\s+(\d+)',open('/proc/meminfo').read()).group(1));print('MemAvailable GiB',round(m/2**20,2));assert m>=2.5*2**20"
python3 -c "import shutil;f=shutil.disk_usage('/srv').free/2**30;print('свободно на /srv GiB',round(f,1));assert f>=5"
python3 -m factory cell trigger --site animedia-01 | tee /dev/stderr | grep -q "\"commit\": \"$NEW\""   # пробный прогон без записи: должен назвать $NEW

# 7. Выпуск
python3 -m factory cell trigger --site animedia-01 --confirm-activation
python3 - "$NEW" <<'EOF'
import os, sys, time
want = '/srv/animedia-icu/releases/' + sys.argv[1][:12]
for _ in range(60):
    if os.readlink('/srv/animedia-icu/current') == want: print('current ->', want); break
    time.sleep(30)
else:
    raise SystemExit('за 30 мин current не переключился на ' + want)
EOF

# 8. Живая приёмка
curl -fsS https://animedia.icu/sitemap.xml | grep -c '<loc>'
curl -fsS https://animedia.icu/sitemap-1.xml | grep -c 'genre=anime'      # ≥1, иначе стоп и откат
curl -fsS -o /dev/null -w '%{http_code}\n' 'https://animedia.icu/catalog/?genre=anime'   # 200
curl -fsS -o /dev/null -w '%{http_code}\n' https://animedia.icu/                           # 200
```

**Откат** — если шаг 8 не прошёл или после выпуска сломалось что-то видимое. Возвращается прежний выпуск 55c7b719a5df тем же сине-зелёным путём, данные сайта не трогаются:

```bash
set -euo pipefail
cd /home/claude/wt-portable-site-cell-01
python3 -m factory cell submit --site animedia-01 --cell-operation access-check   # если прошлой проверке больше 12 ч
sleep 120
python3 -m factory cell submit --site animedia-01 --cell-operation update \
  --commit 55c7b719a5dfb468ae9de425a8bfa6ce07ae0973 \
  --expect-digest sha256:ce437076917ab7fa61a3c95b8462e723d8abf2478eda4ed5fabd99a6c8d83323 \
  --reason "откат T262: <причина>"
# ждать: readlink /srv/animedia-icu/current  ->  /srv/animedia-icu/releases/55c7b719a5df
```

Ветку выпуска откат не трогает: коммит T262 остаётся на ней, а публикатор держит задачу в ожидании.

**Что делает сессия после выпуска.**
- Статус T262 → `live_verified`, с замером страниц жанров в карте: только те, что отдают `index` и canonical на себя.
- После этого в очередь идут T272, T274 и T273.

---

## 2. Перезапуск MCP (site-factory-mcp)

**Зачем.** Служба работает с 12.10 17:42:04Z (PID 1499831) на коде того момента. После этого в `factory/qwen/` было пять коммитов (ec3d12e, 68a32fd, 7f37574, e3f8366, 4ff8f35): `editorial.py` +371/−139, `comments.py` +32. Среди них — замок публикации сайта (4ff8f35) и сохранение авторства в накладке, то есть правки, ради которых стоит пауза публикаций на семи витринах. `/healthz` сам пишет: «правка, сделанная после запуска, в службе не действует до перезапуска».

**Фактическая конфигурация, прочитана 21.10 ≈19:33Z.**
- Юнит `/etc/systemd/system/site-factory-mcp.service`; `WorkingDirectory=/home/claude/wt-portable-site-cell-01`.
- Drop-in `10-write-mode.conf` заменяет `ExecStart` на запуск без `--read-only`.
- Drop-in `20-editorial-queue.conf` задаёт `SEO_OPERATOR_ROOT=/home/claude/wt-editorial-queue-repair-01`.
- `/healthz`: `read_only:false`, 43 инструмента, отпечаток 38af3933d4df1ac9.

**Активные операции.**
- Редакционный прогон `editor-run.timer` стартует каждые 5 минут. В 19:30:03Z шёл прогон 20261021T193003Z с тайм-аутом 1 500 с, и он работает через MCP.
- Признак «в gate.jsonl нет `"run": true`» ненадёжен: он бывает почти в каждом цикле.
- Надёжный признак — свободный flock `var/editor-runs/run.lock`. Поэтому таймер на время перезапуска останавливается.

```bash
set -euo pipefail
W=/home/claude/wt-portable-site-cell-01

# 0. Версия кода — та, что проверена
test "$(git -C $W log -1 --format=%H -- factory/)" = 4ff8f356218145c1b691ec12792a3f1e605f1be2
test -z "$(git -C $W status --short -- factory/)"
sha256sum -c - <<'EOF'
651c45b97b511ddfd981439a8cea6df0fb2c5242869680bdbf697d5527a7acd3  /home/claude/wt-portable-site-cell-01/factory/qwen/editorial.py
af602c772c5cb41986ab6f404e49843f22ee06616965e7eaf40ae335aa5cfcf2  /home/claude/wt-portable-site-cell-01/factory/qwen/mcp.py
EOF

# 1. Фактическая конфигурация
systemctl show -p MainPID,ActiveState,ExecMainStartTimestamp site-factory-mcp
systemctl cat site-factory-mcp | grep -n -E 'ExecStart|WorkingDirectory|SEO_OPERATOR_ROOT'
#   ожидание: последняя ExecStart — без --read-only; WorkingDirectory=/home/claude/wt-portable-site-cell-01

# 2. Остановить новые редакционные прогоны и дождаться текущего
sudo systemctl stop editor-run.timer
python3 - <<'EOF'
import fcntl, glob, time
def free(p):
    f = open(p, 'a+')
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(f, fcntl.LOCK_UN); return True
    except BlockingIOError:
        return False
for _ in range(60):                       # до 30 мин: тайм-аут прогона 1 500 с
    busy = [p for p in ['/home/claude/wt-portable-site-cell-01/var/editor-runs/run.lock',
                        *glob.glob('/srv/sites/*/runtime/overlays/*/.publish.lock')] if not free(p)]
    if not busy: print('замки свободны'); break
    print('заняты:', busy); time.sleep(30)
else:
    raise SystemExit('прогон не завершился за 30 мин — перезапуск отложить, таймер вернуть: sudo systemctl start editor-run.timer')
EOF

# 3. Перезапуск
sudo systemctl daemon-reload
sudo systemctl restart site-factory-mcp
sleep 5

# 4. После
systemctl show -p MainPID,ActiveState,ExecMainStartTimestamp site-factory-mcp   # active, MainPID ≠ 1499831, старт — сейчас
tr '\0' ' ' < /proc/$(systemctl show -p MainPID --value site-factory-mcp)/cmdline; echo
#   ожидание: /usr/bin/python3 -m factory.qwen.mcp --http 127.0.0.1:9000   (без --read-only)
curl -fsS http://127.0.0.1:9000/healthz | python3 -c "import json,sys;h=json.load(sys.stdin);print(h['read_only'],h['tools']['count'],h['environment']['code']['process_started_at']);assert h['read_only'] is False"

# 5. Вернуть редакционный таймер
sudo systemctl start editor-run.timer
systemctl is-active editor-run.timer
```

Если на шаге 4 служба не `active` или `/healthz` не отвечает: `journalctl -u site-factory-mcp -n 50 --no-pager`. Редакционный таймер оставьте остановленным (шаг 5 не выполнять) и передайте вывод сессии. Прежний процесс к этому моменту уже остановлен, а его код в рабочей копии не сохранился, поэтому «откат к старому процессу» невозможен. Безопасное состояние — служба остановлена, и публикаций нет, пока причина не найдена.

**Ограниченная публикация и приёмка (делает сессия, без владельца).**
1. Процесс новее правки: старт службы позже mtime `factory/qwen/editorial.py`. Сессия выполняет `automation/local/editorial-fix-installed.py`, ожидается код 0.
2. Снимок накладки zonafilm.space до публикации: `editorial-overlay-before-after.py --snapshot`.
3. zonafilm.space и только он снимается с `PAUSED_PUBLISH` и ставится в `ПЕРВАЯ_ПУБЛИКАЦИЯ` (`seo_operator/editor_run.py`).
4. После первой публикации:
   - `editorial-overlay-before-after.py --compare` — ни одного исчезнувшего ключа, поля или авторства;
   - `overlay-provenance-diff.py --domain zonafilm.space` — ни одной новой подмены сверх трёх исторических;
   - живая страница показывает опубликованный текст.
5. Только при успехе следующие витрины снимаются с паузы по одной, с той же проверкой. При провале zonafilm.space возвращается на паузу, и итог передаётся Архитектору.

**Второй перезапуск — только при фактической смене кода.** MOD-102 (b72229c, ветка `claude/nova-publish-memory-02`) меняет `подготовить` в `factory/qwen/editorial.py`: +91 строка, плюс `tests/unit/test_editorial_year_source.py`. Сессия переносит её cherry-pick'ом только после приёмки п. 4 и прогоняет `tests/unit -k "editorial or qwen or overlay"`. Затем называет новый sha256 `editorial.py`.

Второй перезапуск выполняется тем же блоком: шаги 0–5 с новым коммитом и новыми суммами. Если sha256 не изменился, второй перезапуск не нужен.
