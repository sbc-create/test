#!/usr/bin/env bash
# Пересоздать проверочный экземпляр lords-90 из текущего шаблона и поднять его.
set -euo pipefail
S=/tmp/claude-1001/-home-claude/9e5d5d7c-1b72-454b-9239-dbb120e73b48/scratchpad
W=/home/claude/wt-lords-template-consolidation-01
N=$S/new-lords-90
MOD=/srv/lords/.frontend/releases/20260923T190000Z-community-2-2-12/community.py

for pid in $(pgrep -f "lords-frontend.py --port 9190" || true); do kill "$pid" || true; done
sleep 1

cd "$W"
python3 -m factory cell newsite --site lords-90 --domain lords90.example \
  --template "${1:-lords-general}" --port 9190 --site-name "Проверочная витрина" \
  --destination "$N" --force > "$S/newsite.json"

# Настройка места и канонический модуль приезжают ОТДЕЛЬНО — так же, как на
# боевой ячейке: в артефакте их нет и быть не должно.
printf '{"publisher_id":"10555","source_mode":"provider-id"}\n' > "$N/config/player.json"
cp "$MOD" "$N/src/community.py"

cd "$N"
git init -q -b main 2>/dev/null || true
git add -A
git -c user.email=t@t -c user.name=t commit -q -m "lords-90: проект из шаблона" || true
echo "экземпляр пересобран: $(python3 -c "import json;print(json.load(open('$S/newsite.json'))['template_commit'][:12])")"
