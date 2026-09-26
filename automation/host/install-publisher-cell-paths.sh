#!/usr/bin/env bash
# Издателю каталога — право писать в хранилища ячеек.
#
#   sudo bash automation/host/install-publisher-cell-paths.sh [--dry-run]
#
# Что чинит
# ---------
#
# `nova-daily-refresh.service` объявляет `ProtectSystem=strict` и перечисляет в
# `ReadWritePaths` только СТАРЫЙ общий путь `/srv/lords`. Каталогов данных
# перенесённых витрин там нет ни одного, поэтому издатель падает на первой же
# доставке:
#
#     OSError: [Errno 30] Read-only file system:
#       '/srv/lordfilm47-space/data/lords-01-catalog.json.<pid>.tmp'
#
# Файловая система при этом `rw`: «read-only» — это песочница самого юнита.
# Следствие видно на публичных сайтах: у канонических витрин (lords-01,
# zona-01) каталог не обновлялся с 23 сентября, тогда как общий каталог свежий,
# а витрины на пятиминутном конвейере получают данные исправно — тот юнит так не
# ограничен.
#
# Почему drop-in, а не правка юнита
# ----------------------------------
#
# `ReadWritePaths` накапливается: drop-in ДОБАВЛЯЕТ пути, не отменяя прежние.
# Правка самого файла юнита затёрла бы чужое решение при следующем обновлении
# конвейера, а drop-in переживает его и виден в `systemctl cat`.
#
# Пути берутся из реестра ячеек, а не выписываются руками: витрина, добавленная
# завтра, не должна снова упереться в ту же песочницу.
set -Eeuo pipefail

dry_run=0
[ "${1:-}" = "--dry-run" ] && dry_run=1

SRC_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${SRC_ROOT}/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
UNIT=nova-daily-refresh.service
DROPIN_DIR="/etc/systemd/system/${UNIT}.d"
DROPIN="${DROPIN_DIR}/10-cell-data-paths.conf"

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"
[ -f "/etc/systemd/system/${UNIT}" ] || die "юнита ${UNIT} нет"

mapfile -t paths < <("$PY" - <<PYPATHS
import sys
sys.path.insert(0, "$SRC_ROOT")
from factory.cell import registry, runtime

видно = []
for site_id in sorted(registry.extracted_sites()):
    try:
        d = runtime.размещение(site_id).data_dir
    except Exception:
        continue
    if d and d not in видно:
        видно.append(d)
print("\n".join(видно))
PYPATHS
)
[ "${#paths[@]}" -gt 0 ] || die "в реестре нет ни одного каталога данных ячеек"

log "каталоги данных ячеек из реестра: ${#paths[@]}"
printf '   %s\n' "${paths[@]}"

# Проверяется не имя файла, а ФАКТ: объявлены ли уже эти пути кем-нибудь.
# Свой drop-in по своему имени — способ поставить второй такой же рядом с
# чужим: список сложится, но два файла об одном будут расходиться при
# следующей правке, и никто не узнает, какой из них главный.
missing=0
for p in "${paths[@]}"; do
  grep -qs -- "^ReadWritePaths=-${p}\b" "$DROPIN_DIR"/*.conf 2>/dev/null || missing=1
done
# Устаревший drop-in — сам по себе причина продолжить, даже если все пути
# объявлены новым файлом: systemd складывает оба, и старый список без дефисов
# продолжает валить юнит. Без этой строки «уже настроено» означало бы
# «настроено и сломано одновременно».
[ -f "$DROPIN_DIR/10-cell-data-dirs.conf" ] && missing=1
if [ "$missing" = 0 ] && [ -d "$DROPIN_DIR" ]; then
  log "все пути уже объявлены существующими drop-in — ничего не меняю"
  ls -1 "$DROPIN_DIR" | sed 's/^/   /'
  exit 0
fi

if [ "$dry_run" = 1 ]; then
  printf '   [сухой прогон] %s <- ReadWritePaths для перечисленных\n' "$DROPIN"
  exit 0
fi

install -d -m 0755 "$DROPIN_DIR"

# Прежние наши drop-in удаляются, а не оставляются рядом. systemd СКЛАДЫВАЕТ
# все файлы каталога, поэтому старый список продолжал действовать вместе с
# новым: после установки 26.09 рядом лежали 10-cell-data-dirs.conf (девять
# путей БЕЗ дефиса) и 10-cell-data-paths.conf (девять с дефисом), и три
# отсутствующих каталога из старого файла по-прежнему давали 226/NAMESPACE.
# Новое имя файла не отменяет старое — его надо убрать явно.
for stale in "$DROPIN_DIR"/10-cell-data-dirs.conf; do
  [ -f "$stale" ] || continue
  if [ "$dry_run" = 1 ]; then
    printf '   [сухой прогон] убрать устаревший %s\n' "$stale"
  else
    rm -f "$stale"
    log "убран устаревший drop-in: $stale"
  fi
done

{
  printf '# Издатель каталога пишет в хранилища выделенных витрин.\n'
  printf '# ProtectSystem=strict делает недоступным на запись всё, что не\n'
  printf '# объявлено; в самом юните перечислен только общий /srv/lords, и\n'
  printf '# доставка в ячейки падала с Errno 30 при исправной файловой системе.\n'
  printf '# Пути выведены из реестра ячеек, не выписаны руками.\n'
  printf '#\n'
  printf '# Дефис перед путём обязателен. Без него отсутствующий каталог валит\n'
  printf '# НЕ доставку в эту ячейку, а ВЕСЬ юнит: systemd не может собрать\n'
  printf '# пространство имён и отвечает 226/NAMESPACE ещё до запуска. Так и\n'
  printf '# вышло: в реестре есть ячейки, чьи каталоги создаёт первый выпуск\n'
  printf '# (yummyani-biz, yummyani-org, yummyani-site, animedia-icu), и пока\n'
  printf '# выпуска не было, суточное обновление не запускалось вовсе — у всех\n'
  printf '# семи витрин источник старел, хотя доставка была ни при чём.\n'
  printf '# `ReadWritePaths=-<путь>` делает отсутствие каталога безразличным\n'
  printf '# для запуска и превращает его в отсутствие права записи именно\n'
  printf '# туда, а это уже изолировано по ячейкам в самом издателе.\n'
  printf '[Service]\n'
  for p in "${paths[@]}"; do printf 'ReadWritePaths=-%s\n' "$p"; done
} > "$DROPIN"
chmod 0644 "$DROPIN"
systemctl daemon-reload
log "drop-in записан: $DROPIN"
systemctl cat "$UNIT" | grep -c '^ReadWritePaths=' | xargs -I{} echo "   строк ReadWritePaths после правки: {}"
echo
echo "Проверка: sudo systemctl start ${UNIT}; затем сверить mtime"
echo "/srv/<account>/data/<site>-catalog.json с /srv/lords/.frontend/."
