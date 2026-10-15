#!/usr/bin/env python3
"""Поддельный yummy-b016-check.py: код по $FAKE_CHECK_RC ({"compare:after-web-org.json": 1, ...})."""
import json
import os
import sys

a = sys.argv[1:]
rules = json.loads(os.environ.get("FAKE_CHECK_RC", "{}"))
key = a[0] + (":" + os.path.basename(a[-1]) if a[0] in ("snapshot", "compare") else ":" + a[-1])
if a[0] == "snapshot":
    open(a[1], "w").write("{}")
with open(os.environ["FAKE_CHECK_LOG"], "a") as f:
    f.write(" ".join(a) + "\n")
sys.exit(rules.get(key, 0))
