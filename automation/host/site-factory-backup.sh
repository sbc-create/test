#!/usr/bin/env bash
# Backup of the control host's own state, with a restore that is proven, not assumed.
#
# This is the host-level counterpart of the per-site backup contract in
# `backup_policy` — it covers what the site packages do not: factory runtime
# state, host configuration, and the git history itself. It does not replace
# `automation/ansible/backup-site.yml`, which backs up a deployed site on a target.
#
# The repository rule applies here too: the existence of an archive is not proof
# of a restore. Every archive is extracted into a temporary directory and every
# file is compared by SHA-256 before the run is recorded as verified.
set -uo pipefail

REPO="${FACTORY_REPO:-/srv/site-factory/repo}"
BACKUP_DIR="${SITE_FACTORY_BACKUP_DIR:-/srv/backups}"
LOG_DIR="${SITE_FACTORY_LOG_DIR:-/var/log/site-factory}"
KEEP="${SITE_FACTORY_BACKUP_KEEP:-14}"
# Where the encrypted Secret Hub store lives. The registry is the source of truth;
# the literal is only the fallback for a host without one.
HUB_STORE_DIR="${SECRET_HUB_STORE_DIR:-$(
  python3 -c 'import json,sys
try:
    print(json.load(open(sys.argv[1], encoding="utf-8")).get("store_dir", ""))
except Exception:
    pass' "$REPO/config/secret-hub.json" 2>/dev/null
)}"
HUB_STORE_DIR="${HUB_STORE_DIR:-/var/lib/site-factory-secret-hub}"
# Never prune below this many verified backups, whatever the retention says.
KEEP_FLOOR=3

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { echo "BACKUP FAILED: $*" >&2; exit 1; }

mkdir -p "$BACKUP_DIR" "$LOG_DIR" || fail "не удалось создать каталоги"

ARCHIVE="$BACKUP_DIR/host-$STAMP.tar.gz"
# The git bundle is a rolling mirror, not a dated copy: this repository's
# history is ~300 MB, and one bundle per run would fill a 70 GB disk in two
# weeks. Two generations are kept so there is never a moment without one.
BUNDLE="$BACKUP_DIR/repo-latest.bundle"
BUNDLE_PREV="$BACKUP_DIR/repo-previous.bundle"
RECORD="$BACKUP_DIR/host-$STAMP.verified.json"

# ---------------------------------------------------------------------------
# 1. Collect. Secrets are excluded by pattern, not by hoping none are present.
# ---------------------------------------------------------------------------
STAGE="$WORK/stage"
mkdir -p "$STAGE"

# Plaintext consumer credentials are excluded by NAME taken from the Secret Hub
# registry, not by a pattern that happens to match today. `secrets/` covered the
# Lords consumers only because their directory is called that; the Yami consumer
# lives in `runtime/cdnvideohub/` and matched nothing, so rsync walked into a
# root-only file, got EACCES, and failed the whole backup — which then aged out
# the health check. Deriving the list from the registry keeps a new consumer from
# reopening the same hole silently; tests/unit/test_backup_excludes_consumer_credentials.py
# fails if any registry file name is not covered here.
CONSUMER_EXCLUDES=()
while IFS= read -r name; do
  [ -n "$name" ] && CONSUMER_EXCLUDES+=( "--exclude=$name" )
done < <(python3 - "$REPO/config/secret-hub.json" <<'PYEOF'
import json, sys
try:
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    sys.exit(0)          # no registry -> no derived excludes, static ones still apply
names = set()
for portfolio in cfg.get("portfolios", []):
    for consumer in portfolio.get("consumers", []):
        files = consumer.get("files", {})
        names.update(files.values() if isinstance(files, dict) else files)
for name in sorted(n for n in names if n and "/" not in n):
    print(name)
PYEOF
)

collect() {
  local src="$1" dest="$2"
  [ -e "$src" ] || return 0
  mkdir -p "$(dirname "$STAGE/$dest")"
  rsync -a --quiet \
        --exclude='*.pem' --exclude='*.key' --exclude='.env' --exclude='.env.*' \
        --exclude='secrets/' --exclude='*staging-auth*' --exclude='node_modules/' \
        --exclude='.venv/' --exclude='__pycache__/' \
        --exclude='*.password' --exclude='db/' \
        "${CONSUMER_EXCLUDES[@]}" \
        "$src" "$STAGE/$dest" || fail "rsync $src"
}

collect "$REPO/var/"            "factory-var/"
collect /etc/site-factory/      "etc-site-factory/"
collect /etc/nginx/sites-available/ "etc-nginx-sites/"
collect /srv/sites/             "srv-sites/"

# Данные ЯЧЕЕК. До 2026-10-13 их здесь не было вовсе: сбор шёл по
# `/srv/sites/`, а каталоги данных ячеек живут в `/srv/<учётная запись>/data` —
# это другой путь, и ни одна из 28 ячеек в архив не попадала. Восстановить
# оценки, комментарии и опубликованные правки редактора было бы нечем.
#
# Берётся не весь каталог: измерено, что данные ячеек весят 1,81 ГиБ, а
# невосстановимая их часть — 25,74 МиБ (1,39 %). Остальное заново положит
# производитель. План сбора строит `backup_cell_data.py` по КОНТРАКТУ ДАННЫХ
# каждой витрины, поэтому новая ячейка попадает в копию сама, без правки этого
# файла. Отказ плана (элемент контракта уводит за пределы каталога данных)
# останавливает прогон: это вход из репозитория витрины, и доверять ему нельзя.
CELL_PLAN="$WORK/cell-data-plan.tsv"
if ! python3 "$REPO/automation/host/backup_cell_data.py" \
        >"$CELL_PLAN" 2>"$WORK/cell-data-plan.log"; then
  tail -5 "$WORK/cell-data-plan.log" >&2 || true
  fail "план сбора данных ячеек не построен — см. $WORK/cell-data-plan.log"
fi
CELL_ITEMS=0
while IFS=$'\t' read -r cell_id cell_dir cell_item; do
  [ -n "$cell_id" ] || continue
  if [ "$cell_item" = "*" ]; then
    # Витрина без объявленного контракта: каталог целиком, минус поставляемое.
    [ -d "$cell_dir" ] || continue
    mkdir -p "$STAGE/srv-cells/$cell_id"
    rsync -a --quiet \
          --exclude='*-catalog.json' --exclude='*-details.json' \
          --exclude='*-details.nums.json' \
          --exclude='*.pem' --exclude='*.key' --exclude='.env' \
          "${CONSUMER_EXCLUDES[@]}" \
          "$cell_dir/" "$STAGE/srv-cells/$cell_id/" \
      || fail "rsync данных ячейки $cell_id"
    CELL_ITEMS=$((CELL_ITEMS + 1))
    continue
  fi
  [ -e "$cell_dir/$cell_item" ] || continue
  mkdir -p "$STAGE/srv-cells/$cell_id"
  rsync -a --quiet \
        --exclude='*.pem' --exclude='*.key' --exclude='.env' \
        "${CONSUMER_EXCLUDES[@]}" \
        "$cell_dir/$cell_item" "$STAGE/srv-cells/$cell_id/" \
    || fail "rsync $cell_id/$cell_item"
  CELL_ITEMS=$((CELL_ITEMS + 1))
done < "$CELL_PLAN"
# Строка в журнал прогона — обычным echo: функции `log` в этом сценарии нет,
# и вызов несуществующей свалил бы весь бэкап на украшении отчёта.
echo "данные ячеек: собрано элементов $CELL_ITEMS из плана $(wc -l < "$CELL_PLAN")"
# Сводка уходит в запись о проверке. Иначе «данные ячеек в копии» пришлось бы
# принимать на слово: архив и запись лежат под root, и заглянуть внутрь
# снаружи нечем. Число в записи проверяемо и без доступа к архиву.
CELL_SITES="$(find "$STAGE/srv-cells" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l)"
CELL_KB="$(du -sk "$STAGE/srv-cells" 2>/dev/null | awk '{print $1}')"
CELL_KB="${CELL_KB:-0}"
# The encrypted Secret Hub store. Without it a restore has no way to regenerate
# the consumer files excluded above, and the backup would only look complete.
# Ciphertext is safe to archive precisely because the master key is not: it lives
# in /etc/site-factory/secrets/, which the `secrets/` exclude keeps out of here.
#
# The store is 0700 root:root by design, so an unprivileged run cannot read it.
# That must be said plainly rather than surfaced as a bare rsync EACCES: the
# operator needs to know which privilege is missing, and skipping the directory
# to make the run "succeed" would produce an archive that cannot restore the
# consumers. Fail here, loudly, and leave the previous verified backup in place.
if [ -e "$HUB_STORE_DIR" ] && [ ! -r "$HUB_STORE_DIR" ]; then
  fail "нет доступа к $HUB_STORE_DIR (запуск от $(id -un), каталог $(stat -c '%a %U:%G' "$HUB_STORE_DIR" 2>/dev/null || echo '0700 root:root')). Шифрованное хранилище Secret Hub обязано входить в бэкап: без него восстановление consumer-файлов невозможно. Юнит должен запускаться с достаточными правами; исключать этот каталог нельзя."
fi
collect "$HUB_STORE_DIR/"       "secret-hub-store/"

mkdir -p "$STAGE/host-facts"
{
  echo "# generated $STAMP — no secrets"
  echo "## systemd site-factory units"; systemctl list-unit-files 'site-factory*' --no-pager 2>/dev/null
  echo "## ufw"; ufw status verbose 2>/dev/null || echo "(нет прав на ufw)"
  echo "## packages"; dpkg -l | awk '/^ii/{print $2"="$3}'
} > "$STAGE/host-facts/inventory.txt" 2>/dev/null

# git bundle: the repository history, recoverable without GitHub.
#
# `safe.directory` объявляется явно, а не наследуется из чьего-то ~/.gitconfig.
# Юнит работает от root, а рабочее дерево принадлежит claude, и git отказывается
# трогать чужой репозиторий: `detected dubious ownership`. Ошибка приходит уже
# после того, как всё собрано, и выглядит как «BACKUP FAILED: git bundle» —
# причина в ней не названа вовсе. Зависеть здесь от HOME тем более нельзя: под
# ProtectHome и systemd-окружением он не тот, что в интерактивной сессии.
# Доверие выдаётся ровно одному каталогу — тому, который и так читается ниже.
GIT_SAFE=(-c "safe.directory=$REPO")
if [ -d "$REPO/.git" ]; then
  git "${GIT_SAFE[@]}" -C "$REPO" bundle create "$WORK/repo.bundle" --all >/dev/null 2>&1 \
    || fail "git bundle: не удалось собрать историю репозитория $REPO"
  git "${GIT_SAFE[@]}" -C "$REPO" bundle verify "$WORK/repo.bundle" >/dev/null 2>&1 \
    || fail "git bundle не проходит проверку"
  # Replace only after the new bundle verified, and keep the previous one:
  # a failed run must never leave the host without a recoverable history.
  [ -f "$BUNDLE" ] && mv -f "$BUNDLE" "$BUNDLE_PREV"
  mv -f "$WORK/repo.bundle" "$BUNDLE"
  chmod 0640 "$BUNDLE"
fi

# ---------------------------------------------------------------------------
# 1b. Хватит ли места — решается здесь, до упаковки.
#
# Дальше на диске одновременно живут три вещи: staging, архив и распакованная
# копия для доказательства восстановления. 2026-09-03 прогон это выяснил на
# последнем шаге: `tar: No space left on device` после трёх с половиной минут
# работы и уже записанного архива на 1.13 GB, который затем остался сиротой.
# Отказ был предсказуем ещё до `tar`, и отказать заранее дешевле — предыдущий
# подтверждённый бэкап при этом остаётся нетронутым.
# Политика вынесена в backup-space-precheck.sh и проверяется на числах:
# tests/unit/test_backup_space_precheck.py.
# ---------------------------------------------------------------------------
STAGE_KB="$(du -sk "$STAGE" | awk '{print $1}')"
WORK_AVAIL_KB="$(df -Pk "$WORK" | awk 'NR==2{print $4}')"
BACKUP_AVAIL_KB="$(df -Pk "$BACKUP_DIR" | awk 'NR==2{print $4}')"
# Одна ли под ними файловая система. На этом хосте — да: `/tmp` и `/srv/backups`
# лежат на одном `/`, и свободное место у них общее. Проверять два требования
# порознь означало бы разрешить раскладку, которой на самом деле не хватает.
SAME_FS=0
if [ "$(stat -c %d "$WORK" 2>/dev/null)" = "$(stat -c %d "$BACKUP_DIR" 2>/dev/null)" ]; then
  SAME_FS=1
fi
bash "$(dirname "$0")/backup-space-precheck.sh" \
     "$STAGE_KB" "$WORK_AVAIL_KB" "$BACKUP_AVAIL_KB" "$SAME_FS" \
  || fail "упаковка не начиналась: места не хватает уже сейчас, предыдущий подтверждённый бэкап цел"

# ---------------------------------------------------------------------------
# 2. Archive with a manifest of checksums taken from the source, before packing.
# ---------------------------------------------------------------------------
( cd "$STAGE" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum ) > "$WORK/manifest.sha256" \
  || fail "не удалось посчитать контрольные суммы"
FILE_COUNT="$(wc -l < "$WORK/manifest.sha256")"

tar -czf "$ARCHIVE" -C "$STAGE" . || fail "не удалось создать архив"
chmod 0640 "$ARCHIVE"

# ---------------------------------------------------------------------------
# 3. Prove the restore. Extract elsewhere and compare every checksum.
# ---------------------------------------------------------------------------
RESTORE="$WORK/restore"
mkdir -p "$RESTORE"
tar -xzf "$ARCHIVE" -C "$RESTORE" || fail "архив не распаковывается"

MISMATCH="$(cd "$RESTORE" && sha256sum --quiet -c "$WORK/manifest.sha256" 2>&1 | head -20)"
if [ -n "$MISMATCH" ]; then
  fail "восстановление не совпало с источником: $MISMATCH"
fi

RESTORED_COUNT="$(cd "$RESTORE" && find . -type f | wc -l)"
if [ "$RESTORED_COUNT" -lt "$FILE_COUNT" ]; then
  fail "в восстановленном наборе $RESTORED_COUNT файлов против $FILE_COUNT в источнике"
fi

# ---------------------------------------------------------------------------
# 4. Record. Only now is the backup allowed to count as verified.
# ---------------------------------------------------------------------------
python3 - "$RECORD" "$ARCHIVE" "$BUNDLE" "$FILE_COUNT" "$STAMP" \
         "$CELL_SITES" "$CELL_ITEMS" "$CELL_KB" <<'PYEOF'
import hashlib, json, os, sys
record, archive, bundle, count, stamp = sys.argv[1:6]
cell_sites, cell_items, cell_kb = sys.argv[6:9]
def sha(p):
    if not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
json.dump({
    "backup": "control-host",
    "created_at": stamp,
    "archive": archive,
    "archive_sha256": sha(archive),
    "archive_bytes": os.path.getsize(archive),
    "git_bundle": bundle if os.path.exists(bundle) else None,
    "git_bundle_sha256": sha(bundle),
    "files": int(count),
    "restore_verified": True,
    "restore_method": "extract to temp dir + sha256sum -c against source manifest",
    # Покрытие данных ячеек. Ноль витрин здесь — это НЕ «ячеек нет»: до
    # 2026-10-13 данные ячеек в архив не попадали вовсе, и отличить одно
    # состояние от другого по самому архиву было нечем. Поле отвечает числом.
    "cell_data": {
        "sites": int(cell_sites or 0),
        "items": int(cell_items or 0),
        "kib": int(cell_kb or 0),
        "selected_by": "data_contract.user_writable витрины; поставляемые снимки исключены",
    },
}, open(record, "w"), ensure_ascii=False, indent=2)
PYEOF
chmod 0640 "$RECORD"

# A run that produced no verification record is a failed run, whatever the exit
# status of the steps above says. `check_backups` in site-factory-health.sh dates
# the last good backup by these files alone, so a missing or truncated record
# silently ages the host out of its SLA while the unit reports success.
if [ ! -s "$RECORD" ]; then
  fail "запись о проверке $RECORD не создана или пуста — бэкап не считается подтверждённым"
fi
python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$RECORD" \
  || fail "запись о проверке $RECORD не разбирается как JSON"

# ---------------------------------------------------------------------------
# 5. Retention. Вынесено в `backup-retention.sh` целиком.
#
# Правило удержания должно быть проверяемо на подставном каталоге: внутри этого
# скрипта до него полторы минуты rsync по живому хосту, и до 2026-09-03 его не
# проверял никто. Дефект, который там жил, стоил суток без подтверждённого
# бэкапа: удалялись только полные тройки, а архив упавшего прогона не имел
# записи о проверке и не попадал в список удаления никогда.
# См. tests/unit/test_backup_retention_prunes_orphan_archives.py.
# ---------------------------------------------------------------------------
SITE_FACTORY_BACKUP_KEEP="$KEEP" \
SITE_FACTORY_BACKUP_KEEP_FLOOR="$KEEP_FLOOR" \
  bash "$(dirname "$0")/backup-retention.sh" "$BACKUP_DIR" \
  || echo "retention: удержание отработало с ошибкой, архивы оставлены как есть" >&2

echo "OK: $ARCHIVE ($FILE_COUNT файлов) — восстановление подтверждено, запись $RECORD"
