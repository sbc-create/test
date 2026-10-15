#!/usr/bin/env bash
# Проверенная копия комплекта витрин на самом узле — для восстановления.
#
# Правило репозитория: наличие архива доказательством восстановления не
# считается. Поэтому архив не только создаётся, но и РАСПАКОВЫВАЕТСЯ в
# отдельный каталог, после чего каждый файл сверяется по SHA-256 из описи.
#
# Имена переменных только ASCII: кириллица в именах переменных оболочки падает
# в работе, а `bash -n` её пропускает.
#
# Запуск на узле:  k2-make-recovery-copy.sh [каталог хранения]
set -uo pipefail

stage="$HOME/stage"
dest="${1:-$HOME/recovery}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="$dest/k2-cells-$stamp.tar.gz"
sums="$dest/k2-cells-$stamp.sha256"
report="$dest/k2-cells-$stamp.verified.json"

[ -d "$stage/bundles" ] || { echo "error=нет $stage/bundles"; exit 2; }
[ -d "$stage/data" ] || { echo "error=нет $stage/data"; exit 2; }
# Каталог `player` включён с 2026-10-15: витрина без файла плеера не
# запускается вовсе, и копия без него восстанавливала бы неполный
# комплект. Значения в этих файлах публичны по устройству (атрибут
# `data-publisher-id`, D89/D138); токена поставщика в комплекте нет.
# Отсутствие каталога не делает копию невозможной: до назначения номеров
# его и не было, поэтому он не в списке обязательных проверок выше.
mkdir -p "$dest"

echo "stage_mib=$(du -sm "$stage" | cut -f1)"
echo "free_mib_before=$(df -Pm "$dest" | awk 'NR==2{print $4}')"

# 1. Опись ДО упаковки: суммы считаются по источнику, а не по распакованному.
( cd "$stage" && find bundles data player units nginx cells -type f 2>/dev/null \
    | sort | xargs sha256sum ) > "$sums"
echo "files_in_manifest=$(wc -l < "$sums")"

# 2. Архив.
tar -C "$stage" -czf "$archive" \
    --exclude="*.tar.gz" bundles data player units nginx cells 2>/dev/null
echo "archive=$archive"
echo "archive_mib=$(du -m "$archive" | cut -f1)"

# 3. Проверка восстановлением: распаковка в отдельный каталог и сверка сумм.
probe="$(mktemp -d)"
if ! tar -C "$probe" -xzf "$archive"; then
  echo "restore_verified=false"
  echo "error=архив не распаковался"
  rm -rf "$probe"
  exit 1
fi
cp "$sums" "$probe/SHA256SUMS"
restored=0
if ( cd "$probe" && sha256sum -c SHA256SUMS --quiet ); then restored=1; fi
echo "restore_verified=$([ "$restored" = 1 ] && echo true || echo false)"
echo "restored_files=$(find "$probe" -type f | wc -l)"

# 4. Запись о проверке — рядом с архивом, в машинном виде.
cat > "$report" <<EOF
{
  "schema_version": 1,
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "host": "$(hostname)",
  "archive": "$archive",
  "archive_bytes": $(stat -c %s "$archive"),
  "manifest": "$sums",
  "files": $(wc -l < "$sums"),
  "restore_verified": $([ "$restored" = 1 ] && echo true || echo false),
  "restore_probe_dir": "$probe",
  "note": "Суммы посчитаны по источнику ДО упаковки; проверка — распаковка в отдельный каталог и sha256sum -c по той же описи."
}
EOF
rm -rf "$probe"
echo "report=$report"
echo "free_mib_after=$(df -Pm "$dest" | awk 'NR==2{print $4}')"
[ "$restored" = 1 ] || exit 1
