#!/usr/bin/env python3
"""Ворота обновления каталога: шаблон берётся из релиза, а не из рабочего дерева.

Три подкоманды, ровно по трём местам, где терялась выложенная работа.

    plan     — из какого артефакта отрисовывать эту витрину. Печатает путь.
    adopt    — завести манифест действующему релизу, закрепив ревизию, которой
               он фактически собран. Разовый шаг для витрин, выложенных до
               появления манифестов.
    finalize — записать манифест нового релиза и атомарно переключить `current`
               с проверкой ожидаемого предыдущего.

Сценарий обновления вызывает `plan` перед отрисовкой и `finalize` вместо
`ln -sfn`. Между ними он ничего не решает про шаблон: решение принято здесь и
записано.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.lords import refresh_release as рр  # noqa: E402
from factory.lords import release_manifest as рм  # noqa: E402
from factory.lords import template_artifact as та  # noqa: E402


def _рантайм(корень: str, сайт: str) -> Path:
    return Path(корень) / сайт


def команда_plan(args) -> int:
    рантайм = _рантайм(args.runtime_root, args.site)
    try:
        план = рр.план(рантайм, artifact_root=args.artifact_root)
    except (рр.RefreshRefused, рм.ManifestError, та.ArtifactError) as отказ:
        print(f"ОТКАЗ {args.site}: {отказ}", file=sys.stderr)
        return 3
    if args.json:
        печать = dict(план)
        печать.pop("manifest", None)
        print(json.dumps(печать, ensure_ascii=False))
    else:
        print(план["templateRoot"])
    return 0


def команда_adopt(args) -> int:
    """Манифест для релиза, выложенного до появления манифестов.

    Ревизия не угадывается: она передаётся явно и проверяется тем, что архив
    этой ревизии собирается. Артефакт складывается рядом с витриной, потому что
    релиз обязан оставаться восстановимым и после того, как рабочее дерево
    уедет вперёд.
    """
    рантайм = _рантайм(args.runtime_root, args.site)
    релиз = рр.текущий_релиз(рантайм)
    if релиз is None:
        print(f"ОТКАЗ {args.site}: нет действующего релиза", file=sys.stderr)
        return 3
    путь_манифеста = релиз / рр.МАНИФЕСТ
    if путь_манифеста.is_file() and not args.force:
        print(f"{args.site}: манифест уже есть — {путь_манифеста}")
        return 0

    хранилище = Path(args.artifact_root) / "templates"
    хранилище.mkdir(parents=True, exist_ok=True)
    архив = хранилище / f"{args.revision[:12]}.tar.gz"
    if not архив.is_file():
        собрано = та.собрать(args.repo, args.revision, архив)
        отпечаток = собрано["digest"]
    else:
        отпечаток = рм.отпечаток_файла(архив)

    тайтлы = релиз / "site" / "title"
    страниц = len(list(тайтлы.glob("*"))) if тайтлы.is_dir() else 0
    прежний = (рантайм / "previous")
    манифест = {
        "tenant_id": args.site,
        "domain": args.domain,
        "theme": args.theme,
        "template_package_ref": args.package_ref,
        "template_artifact_ref": f"templates/{архив.name}",
        "template_digest": отпечаток,
        "renderer_revision": args.revision,
        "content_snapshot_id": args.snapshot or f"adopted-{релиз.name}",
        "content_source": args.content_source,
        "content_count": args.content_count or страниц,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "created_by": f"adopt:{os.getenv('USER') or os.getuid()}",
        "previous_release": прежний.resolve().name if прежний.exists() else None,
        "rollback_target": прежний.resolve().name if прежний.exists() else None,
        "release_reason": "adopt-existing-release",
        "production_authorized": True,
        "manifest_version": рм.ВЕРСИЯ,
        "adopted": True,
        "adopted_note": (
            "манифест заведён действующему релизу задним числом: ревизия "
            "передана явно и подтверждена сборкой архива, счёт записей взят "
            "со страниц самого релиза"
        ),
    }
    беды = рм.нарушения(манифест, artifact_root=args.artifact_root)
    if беды:
        print(f"ОТКАЗ {args.site}: " + "; ".join(беды), file=sys.stderr)
        return 3
    путь_манифеста.write_text(json.dumps(манифест, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    print(f"{args.site}: манифест заведён, отпечаток шаблона {отпечаток[:16]}, "
          f"записей {манифест['content_count']}")
    return 0


def команда_finalize(args) -> int:
    рантайм = _рантайм(args.runtime_root, args.site)
    try:
        with рр.замок(рантайм, timeout=args.lock_timeout):
            план = рр.план(рантайм, artifact_root=args.artifact_root)
            цель = Path(args.target)
            рр.записать_манифест(
                цель, план,
                content_snapshot_id=args.snapshot,
                content_count=args.content_count,
                created_by=args.actor,
                artifact_root=args.artifact_root,
                release_reason=args.reason,
            )
            итог = рр.переключить(рантайм, цель,
                                  expected_current=план["currentRelease"],
                                  reason=args.reason, actor=args.actor)
    except (рр.RefreshRefused, рм.ManifestError, та.ArtifactError) as отказ:
        print(f"ОТКАЗ {args.site}: {отказ}", file=sys.stderr)
        return 3
    print(json.dumps(итог, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--runtime-root", default="/srv/lords")
    р.add_argument("--artifact-root", default="/srv/lords/.artifacts")
    под = р.add_subparsers(dest="команда", required=True)

    p = под.add_parser("plan")
    p.add_argument("site")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=команда_plan)

    a = под.add_parser("adopt")
    a.add_argument("site")
    a.add_argument("--revision", required=True, help="полный SHA ревизии отрисовщика")
    a.add_argument("--repo", default="/srv/site-factory/repo")
    a.add_argument("--domain", required=True)
    a.add_argument("--theme", required=True)
    a.add_argument("--content-source", required=True)
    a.add_argument("--package-ref", default="")
    a.add_argument("--snapshot", default="")
    a.add_argument("--content-count", type=int, default=0)
    a.add_argument("--force", action="store_true")
    a.set_defaults(func=команда_adopt)

    f = под.add_parser("finalize")
    f.add_argument("site")
    f.add_argument("--target", required=True)
    f.add_argument("--snapshot", required=True)
    f.add_argument("--content-count", type=int, required=True)
    f.add_argument("--actor", default="lords-content-refresh")
    f.add_argument("--reason", default="content-refresh")
    f.add_argument("--lock-timeout", type=float, default=300.0)
    f.set_defaults(func=команда_finalize)

    args = р.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
