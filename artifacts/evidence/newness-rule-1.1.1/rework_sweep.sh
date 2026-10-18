#!/usr/bin/env bash
# Переработанные раскладки 1.2 семейств zona и animedia — тоже неопубликованные.
set -u
S=/tmp/claude-1001/-home-claude/9e5d5d7c-1b72-454b-9239-dbb120e73b48/scratchpad
for pair in "zona:1.2.0" "animedia:1.2.0" "animedia:1.2.2"; do
  fam=${pair%%:*}; ver=${pair##*:}
  pkill -f "lords-frontend[.]py --port 9190" 2>/dev/null
  sleep 2
  rm -rf "$S/rw-$fam-$ver"
  cp -r "$S/prev-lords-90" "$S/rw-$fam-$ver"
  python3 - "$S/rw-$fam-$ver" "$fam" "$ver" <<'PY'
import json, sys
from pathlib import Path
d = Path(sys.argv[1]) / "config" / "template-manifest.json"
м = json.loads(d.read_text(encoding="utf-8"))
м["template_family"] = sys.argv[2]
м["design_version"] = sys.argv[3]
d.write_text(json.dumps(м, ensure_ascii=False, indent=2), encoding="utf-8")
PY
  cd "$S/rw-$fam-$ver"
  nohup env LORDS_90_COMMUNITY_MODERATOR_KEY=k python3 run.py --port 9190 \
    --data-dir "$S/mix-data" > "$S/rw-$fam-$ver.log" 2>&1 &
  for i in $(seq 1 30); do curl -sf http://127.0.0.1:9190/healthz -o /dev/null && break; sleep 1; done
  echo "$fam $ver: $(python3 "$S/check_preview.py" 2>&1 | tail -1)"
done
pkill -f "lords-frontend[.]py --port 9190" 2>/dev/null
