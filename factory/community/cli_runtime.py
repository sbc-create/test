#!/usr/bin/env python3
"""CLI helpers for community ratings Stage06 (kill switch / 1% enable / metrics)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root on path when invoked as script
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="community-ratings-ctl")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("serve", help="run HTTP gateway")
    sp = sub.add_parser("enable-1pct")
    sp.add_argument("--started-at", default="")
    sub.add_parser("disable-writes")
    kp = sub.add_parser("kill")
    kp.add_argument("--reason", required=True)
    sub.add_parser("flags")
    sub.add_parser("metrics")
    mp = sub.add_parser("dump-metrics")
    mp.add_argument("--out", required=True)

    args = p.parse_args(argv)
    from factory.community import metrics
    from factory.community.http_gateway import serve
    from factory.community.rollout import (
        as_public_dict,
        disable_public_writes,
        enable_1pct_canary,
        load_flags,
        trigger_kill_switch,
    )

    if args.cmd == "serve":
        serve()
        return 0
    if args.cmd == "enable-1pct":
        flags = enable_1pct_canary(started_at=args.started_at or None)
        print(json.dumps(as_public_dict(flags), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "disable-writes":
        print(json.dumps(as_public_dict(disable_public_writes()), indent=2))
        return 0
    if args.cmd == "kill":
        print(json.dumps(as_public_dict(trigger_kill_switch(args.reason)), indent=2))
        return 0
    if args.cmd == "flags":
        print(json.dumps(as_public_dict(load_flags()), indent=2))
        return 0
    if args.cmd == "metrics":
        flags = load_flags()
        print(
            json.dumps(
                metrics.snapshot(
                    kill_switch_state=int(flags.KILL_SWITCH),
                    rollout_percent=int(flags.PUBLIC_WRITE_ROLLOUT_PERCENT),
                ),
                indent=2,
            )
        )
        return 0
    if args.cmd == "dump-metrics":
        flags = load_flags()
        metrics.dump_daily(
            Path(args.out),
            kill_switch_state=int(flags.KILL_SWITCH),
            rollout_percent=int(flags.PUBLIC_WRITE_ROLLOUT_PERCENT),
        )
        print(args.out)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
