#!/usr/bin/env bash
# Полный комплект одной витрины для нового узла: бандл кода + данные каталога,
# с контрольными суммами и проверкой НА УЗЛЕ, после чего локальная копия данных
# удаляется.
#
# Зачем скриптом. Пар «спроецировать → сверить → доставить → сверить → убрать»
# восемь, и каждый шаг легко забыть. Локальные данные удаляются сразу: пара
# файлов витрины весит 100–135 МиБ, а на управляющем узле свободно около 14 ГиБ.
#
# Имена переменных только ASCII: кириллица в именах переменных оболочки падает
# в работе, а `bash -n` её пропускает (проверено на k2-trial-run.sh).
#
# Запуск:  stage-k2-site-payload.sh <site_id> <lords-films|lords-serials>
set -uo pipefail

site="${1:?нужен site_id}"
family="${2:?нужно семейство: lords-films или lords-serials}"
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
stage="$repo_root/var/k2-data"
host_ref="k2-zomro-01"
inventory="$repo_root/var/ansible/hosts.yml"

cd "$repo_root" || exit 1
mkdir -p "$stage/bundles" "$stage/front/$site"

echo "==> 1. проекция каталога семейства $family на $site"
python3 automation/local/project-family-catalog.py \
        --site "$site" --family "$family" --out "$stage/front/$site" || exit 1

echo "==> 2. бандл кода из var/new-sites/$site"
git -C "var/new-sites/$site" bundle create "$stage/bundles/$site.bundle" --all \
    >/dev/null 2>&1 || { echo "бандл не собрался"; exit 1; }
git -C "var/new-sites/$site" bundle verify "$stage/bundles/$site.bundle" \
    >/dev/null 2>&1 || { echo "бандл не проходит verify"; exit 1; }

echo "==> 3. суммы комплекта"
sums="$stage/$site.sha256"
( cd "$stage" && sha256sum "bundles/$site.bundle" "front/$site"/*.json \
    | sed "s| front/| data/|" > "$site.sha256" )
wc -l < "$sums"

echo "==> 4. доставка на узел"
ansible -i "$inventory" "$host_ref" -m copy \
    -a "src=$stage/bundles/$site.bundle dest=/home/k2deploy/stage/bundles/$site.bundle mode=0644" \
    >/dev/null || exit 1
ansible -i "$inventory" "$host_ref" -m copy \
    -a "src=$stage/front/$site/ dest=/home/k2deploy/stage/data/$site/ mode=0644 directory_mode=0755" \
    >/dev/null || exit 1
ansible -i "$inventory" "$host_ref" -m copy \
    -a "src=$sums dest=/home/k2deploy/stage/$site.sha256 mode=0644" \
    >/dev/null || exit 1

echo "==> 5. сверка НА УЗЛЕ"
out="$(ansible -i "$inventory" "$host_ref" -m raw \
       -a "cd /home/k2deploy/stage; sha256sum -c $site.sha256; echo rc=\$?" 2>&1)"
printf '%s\n' "$out" | grep -E ': OK|FAILED|rc=' | sed 's/^/   /'
if ! printf '%s\n' "$out" | grep -q "rc=0"; then
  echo "СВЕРКА НА УЗЛЕ НЕ ПРОШЛА: локальные данные НЕ удаляю"
  exit 1
fi

echo "==> 6. локальные данные убираются (на узле сверено, источник жив)"
rm -f "$stage/front/$site"/*.json
rmdir "$stage/front/$site" 2>/dev/null
df -Pm / | awk 'NR==2{print "   свободно на управляющем узле: " $4 " МиБ"}'
echo "готово: $site"
