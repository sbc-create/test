#!/usr/bin/env bash
set -u
S=/tmp/claude-1001/-home-claude/9e5d5d7c-1b72-454b-9239-dbb120e73b48/scratchpad
W=/home/claude/wt-lords-template-consolidation-01
for prof in lords-general lords-new lords-curated lords-anime lords-dorama lords-animation lords-genre; do
  pkill -f "lords-frontend[.]py --port 9190" 2>/dev/null
  sleep 2
  rm -rf "$S/np-$prof"
  d=$(python3 -c "import json;print(json.load(open('$S/registry-preview.json'))and'')" 2>/dev/null)
  python3 - "$S/registry-preview.json" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
if p.is_file():
    d = json.loads(p.read_text(encoding="utf-8")); d["cells"] = []
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
PY
  cd "$W"
  if ! python3 -m factory cell newsite --site lords-90 --domain lords90.example \
      --template "$prof" --port 9190 --site-name "Предпросмотр" \
      --remote https://github.com/sbc-create/site-lords90-example \
      --destination "$S/np-$prof" --registry "$S/registry-preview.json" >/dev/null 2>&1; then
    echo "$prof: ГЕНЕРАЦИЯ НЕ УДАЛАСЬ"; continue
  fi
  cp /srv/lords/.frontend/releases/20260923T190000Z-community-2-2-12/community.py "$S/np-$prof/src/community.py"
  install -m 0600 /srv/lords/.frontend/player-lords-01.json "$S/np-$prof/config/player.json"
  cd "$S/np-$prof"
  nohup env LORDS_90_COMMUNITY_MODERATOR_KEY=k python3 run.py --port 9190 \
    --data-dir "$S/mix-data" > "$S/np-$prof.log" 2>&1 &
  for i in $(seq 1 30); do curl -sf http://127.0.0.1:9190/healthz -o /dev/null && break; sleep 1; done
  echo "$prof: $(python3 "$S/check_preview.py" 2>&1 | tail -1)"
done
pkill -f "lords-frontend[.]py --port 9190" 2>/dev/null
