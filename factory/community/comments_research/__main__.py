"""CLI: python3 -m factory.community.comments_research collect ..."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from factory.community.comments_research.collector import collect_corpus
from factory.community.comments_research.corpus_store import default_paths


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m factory.community.comments_research",
        description="COMMUNITY-COMMENTS-01 DERIVED_ONLY research corpus collector",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    collect_p = sub.add_parser("collect", help="Collect ACCEPTED_RESEARCH observations")
    collect_p.add_argument("--target", type=int, default=1000)
    collect_p.add_argument("--repo-root", type=Path, default=None)
    collect_p.add_argument("--out-dir", type=Path, default=None)
    collect_p.add_argument("--checkpoint", type=Path, default=None)
    collect_p.add_argument("--rate-rps", type=float, default=0.2)
    collect_p.add_argument("--max-per-title", type=int, default=10)
    collect_p.add_argument("--dry-run", action="store_true")
    collect_p.add_argument(
        "--allow-synthetic-fixture",
        action="store_true",
        help="Also write SYNTHETIC_RESEARCH_FIXTURE rows (do NOT count as ACCEPTED_RESEARCH)",
    )
    collect_p.add_argument("--synthetic-count", type=int, default=0)

    args = parser.parse_args(argv)
    if args.cmd == "collect":
        root = args.repo_root or _repo_root()
        paths = default_paths(root, out_dir=args.out_dir)
        summary = collect_corpus(
            repo_root=root,
            paths=paths,
            target=args.target,
            checkpoint_path=args.checkpoint or paths.checkpoint,
            rate_rps=args.rate_rps,
            max_per_title=args.max_per_title,
            dry_run=args.dry_run,
            allow_synthetic_fixture=args.allow_synthetic_fixture,
            synthetic_count=args.synthetic_count,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        accepted = int(summary.get("RESEARCH_OBSERVATIONS_ACCEPTED", 0))
        if accepted >= args.target:
            return 0
        # Partial is success-with-reasons, not a hard fail for CI of the tool itself.
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
