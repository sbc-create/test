#!/usr/bin/env bash
# Завершение создания репозитория нового сайта: git init, первый коммит, push.
#
#   bash automation/host/finish-new-site-repo.sh --dry-run var/site-repos/an1meg0-site
#   bash automation/host/finish-new-site-repo.sh var/site-repos/an1meg0-site
#
# Зачем отдельный сценарий. Дерево проекта сайта готовит фабрика, но превратить
# его в репозиторий сессия агента не может: `git init` вне её профиля
# разрешений. Раньше это заканчивалось списком из трёх-четырёх команд в отчёте, и
# каждая пересборка списка давала шанс опечататься в имени ветки или remote.
# Здесь ветка, remote и домен берутся ИЗ КОНФИГУРАЦИИ САЙТА и реестра ячеек.
#
# Имена переменных латиницей. Оболочка не считает идентификатором имя из
# кириллицы и молча выполняет строку `target=...` как команду: `target=:
# command not found`. Эта ошибка записана в журнале как повторы №9, №10, №11 и
# №14, и теперь её ловит tests/unit/test_host_scripts_ascii.py.
#
# Что сценарий НЕ делает: не создаёт репозиторий на GitHub (отдельное право) и
# не выкладывает сайт.
set -euo pipefail

dry_run=0
target=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=1 ;;
    -*) echo "неизвестный ключ: $arg" >&2; exit 2 ;;
    *) target="$arg" ;;
  esac
done
[ -n "$target" ] || { echo "нужен путь к дереву проекта сайта" >&2; exit 2; }

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tree="$(cd "$root/$target" 2>/dev/null && pwd || true)"
[ -n "$tree" ] || { echo "нет каталога $target" >&2; exit 2; }
[ -f "$tree/config/site.json" ] || {
  echo "$target: нет config/site.json — это не дерево проекта сайта" >&2; exit 2; }

read -r domain site_id < <(python3 - "$tree" <<'META'
import json, sys
from pathlib import Path
d = json.loads((Path(sys.argv[1]) / "config" / "site.json").read_text(encoding="utf-8"))
print(d["domain"], d["site_id"])
META
)
remote="$(python3 - "$root" "$domain" <<'META'
import json, sys
from pathlib import Path
cells = json.loads((Path(sys.argv[1]) / "config" / "site-cells.json").read_text(encoding="utf-8"))["cells"]
for c in cells:
    if c["domain"] == sys.argv[2]:
        print((c.get("repo") or {}).get("remote") or "")
        break
META
)"
branch="claude/extract-${domain//./-}"

echo "дерево  : $target"
echo "домен   : $domain   site_id: $site_id"
echo "ветка   : $branch"
echo "remote  : ${remote:-НЕ ОБЪЯВЛЕН В РЕЕСТРЕ}"

if [ -d "$tree/.git" ]; then
  echo "уже репозиторий: git init не нужен"
elif [ "$dry_run" = 1 ]; then
  echo "[сухой прогон] git init -b $branch && git add -A && git commit"
else
  git -C "$tree" init -q -b "$branch"
  git -C "$tree" add -A
  git -C "$tree" commit -q -m "экземпляр сайта $domain ($site_id) из закреплённого шаблона

Дерево подготовлено фабрикой: свой домен, порт, данные, счётчик и проект
мониторинга. Чужие идентификаторы не подставлены.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
  echo "создан репозиторий, ветка $branch, коммит $(git -C "$tree" rev-parse --short HEAD)"
fi

if [ -z "$remote" ]; then
  echo "remote в реестре не объявлен — отправлять некуда, это отдельный вход"
  exit 0
fi
if [ "$dry_run" = 1 ]; then
  echo "[сухой прогон] git remote add origin $remote && git push -u origin $branch"
  exit 0
fi
git -C "$tree" remote get-url origin >/dev/null 2>&1 \
  || git -C "$tree" remote add origin "$remote"
# Отказ «repository not found» означает, что репозитория на GitHub ещё нет: это
# отдельное право, а не ошибка дерева. Называем причину, а не код возврата.
if git -C "$tree" push -u origin "$branch"; then
  echo "ветка отправлена: $branch -> $remote"
else
  echo "push не удался. Если причина «repository not found», репозиторий на GitHub" >&2
  echo "ещё не создан — это отдельный шаг владельца, а не ошибка дерева." >&2
  exit 3
fi
