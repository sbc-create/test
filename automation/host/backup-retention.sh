#!/usr/bin/env bash
# Удержание бэкапов control-host: подтверждённые тройки и осиротевшие архивы.
#
# Вынесено из `site-factory-backup.sh` отдельным файлом ровно затем, чтобы
# правило можно было прогнать на подставном каталоге. Внутри основного скрипта
# оно недостижимо для теста: до него полторы минуты rsync по живому хосту.
#
# Правило первое (было и раньше). Удаляются только полные тройки
# `host-<stamp>.tar.gz` + `host-<stamp>.verified.json`, начиная с самых старых,
# и никогда ниже пола подтверждённых копий.
#
# Правило второе (появилось после отказа 2026-09-03). Архив без записи о
# проверке — продукт упавшего прогона. Прежнее удержание перебирало только
# `*.verified.json`, поэтому такой архив не попадал ни в один список удаления
# **никогда**: он оставался на диске гигабайтом навсегда и сам приближал
# следующий отказ. Так и вышло: диск 90 %, распаковка для доказательства
# восстановления упала на `No space left on device`, запись не создалась,
# архив на 1.13 GB остался, health начал падать каждые 15 минут по возрасту
# подтверждённой копии. Это положительная обратная связь, а не разовый сбой.
#
# Почему у второго правила обязателен возраст. Архив прогона, идущего прямо
# сейчас, тоже ещё не имеет записи о проверке. Удалить его — значит сломать
# живой бэкап. Порог по умолчанию — сутки: заведомо больше длительности прогона
# (минуты) и не больше периода таймера.
#
# Почему второе правило требует хотя бы одну подтверждённую копию. Если
# подтверждённых копий нет вовсе, неподтверждённый архив — единственное, что
# вообще есть у оператора. Пусть лучше кончится место, чем исчезнет последнее.
set -uo pipefail

BACKUP_DIR="${1:-${SITE_FACTORY_BACKUP_DIR:-/srv/backups}}"
KEEP="${SITE_FACTORY_BACKUP_KEEP:-14}"
KEEP_FLOOR="${SITE_FACTORY_BACKUP_KEEP_FLOOR:-3}"
ORPHAN_MIN_AGE_HOURS="${SITE_FACTORY_BACKUP_ORPHAN_MIN_AGE_HOURS:-24}"

[ -d "$BACKUP_DIR" ] || { echo "retention: каталог $BACKUP_DIR не существует" >&2; exit 0; }

# --- правило первое: подтверждённые тройки сверх KEEP -----------------------
mapfile -t VERIFIED < <(find "$BACKUP_DIR" -maxdepth 1 -name 'host-*.verified.json' | sort)
TOTAL=${#VERIFIED[@]}
if [ "$TOTAL" -gt "$KEEP" ] && [ "$TOTAL" -gt "$KEEP_FLOOR" ]; then
  DROP=$(( TOTAL - KEEP ))
  [ $(( TOTAL - DROP )) -lt "$KEEP_FLOOR" ] && DROP=$(( TOTAL - KEEP_FLOOR ))
  for (( i = 0; i < DROP; i++ )); do
    base="$(basename "${VERIFIED[$i]}" .verified.json)"
    rm -f "$BACKUP_DIR/$base.tar.gz" "${VERIFIED[$i]}"
    echo "retention: удалён $base"
  done
fi

# --- правило второе: осиротевшие архивы ------------------------------------
# Пересчёт после первого правила: удалять сирот можно только пока остаётся
# хотя бы одна подтверждённая копия.
REMAINING="$(find "$BACKUP_DIR" -maxdepth 1 -name 'host-*.verified.json' | wc -l)"
if [ "$REMAINING" -lt 1 ]; then
  echo "retention: подтверждённых копий нет — осиротевшие архивы сохранены"
  exit 0
fi

ORPHAN_MIN_AGE_MIN=$(( ORPHAN_MIN_AGE_HOURS * 60 ))
while IFS= read -r archive; do
  [ -n "$archive" ] || continue
  base="$(basename "$archive" .tar.gz)"
  [ -e "$BACKUP_DIR/$base.verified.json" ] && continue
  rm -f "$archive"
  echo "retention: удалён осиротевший архив $base (нет записи о проверке)"
done < <(find "$BACKUP_DIR" -maxdepth 1 -name 'host-*.tar.gz' -mmin "+$ORPHAN_MIN_AGE_MIN" | sort)
