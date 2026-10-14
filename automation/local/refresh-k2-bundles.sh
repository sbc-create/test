#!/usr/bin/env bash
# Обновить на узле ТОЛЬКО код витрин: бандлы из текущих коммитов репозиториев.
#
# Зачем отдельно от полного комплекта. Данные каталога уже доставлены и сверены
# (104 МиБ на витрину), и гонять их заново ради правки в разметке — это полчаса
# и лишний износ диска. Код весит 230 КиБ.
#
# Проверка не формальная: после доставки бандл на узле КЛОНИРУЕТСЯ и в клоне
# ищется признак правки. Сумма доказывает, что доехали те же байты; признак —
# что доехала нужная версия.
#
# Имена переменных только ASCII.
#
# Запуск:  refresh-k2-bundles.sh <признак> <site_id> [site_id ...]
#   признак — строка, которая обязана быть в доставленном коде (например
#   имя новой функции). Без неё проверка превратилась бы в «файл есть».
set -uo pipefail

marker="${1:?нужен признак правки, например _контакт_подвала}"
shift
sites="$*"
[ -n "$sites" ] || { echo "нужен хотя бы один site_id" >&2; exit 2; }

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
inventory="$repo_root/var/ansible/hosts.yml"
host_ref="k2-zomro-01"
work="$repo_root/var/k2-data/bundles"
mkdir -p "$work"
cd "$repo_root" || exit 1

ok=0
bad=0
for site in $sites; do
  src="var/new-sites/$site"
  head_sha="$(git -C "$src" rev-parse --short=12 HEAD)"
  dirty="$(git -C "$src" status --porcelain | wc -l)"
  if [ "$dirty" != "0" ]; then
    echo "[x] $site: $dirty незакоммиченных файлов — бандл не собираю"
    bad=$((bad + 1)); continue
  fi
  git -C "$src" bundle create "$work/$site.bundle" --all >/dev/null 2>&1 || {
    echo "[x] $site: бандл не собрался"; bad=$((bad + 1)); continue; }
  sum="$(sha256sum "$work/$site.bundle" | cut -d' ' -f1)"

  ansible -i "$inventory" "$host_ref" -m copy \
      -a "src=$work/$site.bundle dest=/home/k2deploy/stage/bundles/$site.bundle mode=0644" \
      >/dev/null || { echo "[x] $site: доставка не удалась"; bad=$((bad + 1)); continue; }

  out="$(ansible -i "$inventory" "$host_ref" -m raw -a "
    cd /home/k2deploy/stage;
    echo sum=\$(sha256sum bundles/$site.bundle | cut -d' ' -f1);
    rm -rf /tmp/verify-$site;
    git clone --quiet bundles/$site.bundle /tmp/verify-$site;
    echo head=\$(git -C /tmp/verify-$site rev-parse --short=12 HEAD);
    echo marker=\$(grep -c '$marker' /tmp/verify-$site/src/lords-frontend.py);
    rm -rf /tmp/verify-$site" 2>&1)"
  got_sum="$(printf '%s' "$out" | sed -n 's/.*sum=\([0-9a-f]*\).*/\1/p' | head -1)"
  got_head="$(printf '%s' "$out" | sed -n 's/.*head=\([0-9a-f]*\).*/\1/p' | head -1)"
  got_marker="$(printf '%s' "$out" | sed -n 's/.*marker=\([0-9]*\).*/\1/p' | head -1)"
  if [ "$got_sum" = "$sum" ] && [ "$got_head" = "$head_sha" ] && [ "${got_marker:-0}" -gt 0 ]; then
    echo "$site: голова $head_sha, сумма сошлась, признак «$marker» найден ($got_marker раз)"
    ok=$((ok + 1))
  else
    echo "[x] $site: сумма '$got_sum' против '$sum'; голова '$got_head' против '$head_sha'; признак '$got_marker'"
    bad=$((bad + 1))
  fi
done

echo "обновлено витрин: $ok; отказов: $bad"
[ "$bad" = 0 ] || exit 1
