#!/usr/bin/env bash
# Обновление bestreciept.site и myfood.mobi одной командой владельца (root-шаг):
#
#   sudo bash /home/claude/wt-template-food-daily/automation/host/recipe-domains-apply.sh [--dry-run]
#
# Берёт комплекты из var/kits/recipe-domains-current/ (food-daily-<коммит>, food-baking-<коммит>), проверяет
# контрольные суммы и выполняет сценарий выкладки ИЗ САМОГО комплекта (версия сценария = версия кода):
# templates/food-daily/deploy/bestreciept-apply.sh, затем templates/food-baking/deploy/myfood-apply.sh.
# Первый сбой останавливает обновление; каждый сценарий сам откатывает службу при отказе /healthz,
# nginx меняется только после nginx -t. Соседние сайты не затрагиваются.
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KITS="${HERE}/var/kits/recipe-domains-current"
extra=()
[ "${1:-}" = "--dry-run" ] && extra=(--dry-run)
die() { printf '[x] %s\n' "$*" >&2; exit 1; }
[ -d "$KITS" ] || die "нет ${KITS}"
for pair in "food-daily bestreciept" "food-baking myfood"; do
  read -r tpl short <<<"$pair"
  mapfile -t kits < <(find -L "$KITS" -mindepth 1 -maxdepth 1 -type d -name "${tpl}-*")
  [ "${#kits[@]}" = 1 ] || die "в ${KITS} должен быть ровно один комплект ${tpl}-*"
  kit="${kits[0]}"
  (cd "$kit" && sha256sum -c --quiet SHA256SUMS) || die "контрольные суммы ${kit} не сходятся"
  script="$(mktemp)"
  trap 'rm -f "$script"' EXIT
  tar -xzOf "${kit}/code.tar.gz" "templates/${tpl}/deploy/${short}-apply.sh" >"$script"
  printf '==> %s: %s\n' "$short" "$(basename "$kit")"
  bash "$script" --kit "$kit" "${extra[@]}"
  rm -f "$script"
done
printf '==> готово: https://bestreciept.site/ и https://myfood.mobi/\n'
