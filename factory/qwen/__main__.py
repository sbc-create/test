"""Единая точка входа редактора: одна последовательность на все семейства.

    python3 -m factory.qwen sites
    python3 -m factory.qwen facts     --site <домен> [--slug <слаг>]
    python3 -m factory.qwen prepare   --site <домен> --slug <слаг> --body-file <файл>
    python3 -m factory.qwen publish   --site <домен> --slug <слаг> [--expect-generation <id>]
    python3 -m factory.qwen confirm   --site <домен> --slug <слаг>
    python3 -m factory.qwen unpublish --site <домен> --slug <слаг>
    python3 -m factory.qwen restore   --site <домен> --slug <слаг>
    python3 -m factory.qwen rollback  --site <домен>
    python3 -m factory.qwen status    --site <домен>
    python3 -m factory.qwen diagnose  --site <домен>
    python3 -m factory.qwen indexing  --site <домен>

Тело материала передаётся ФАЙЛОМ (`--body-file`) или стандартным вводом, а не
аргументом командной строки: текст пользователя в исполняемую строку не
попадает ни при каких условиях.

Вывод — JSON на стандартный вывод. Код возврата: 0 — операция подтверждена,
2 — отказ с названной причиной, 3 — записано, но НЕ подтверждено на странице.
"""
from __future__ import annotations

import argparse
import json
import sys

from factory.qwen import editorial, indexing, registry


#: Отказы обеих операций — одного рода: названная причина вместо трассы.
#: Перечислены кортежем, потому что ветвей обработки должно быть ровно одна:
#: два отдельных `except` с одинаковым телом расходятся при первой правке.
ОТКАЗЫ = (editorial.ОперацияОтклонена, indexing.Отказано)

#: Где лежат технические правила и какой они версии.
#:
#: Печатается в КАЖДОМ ответе, и это не украшение. Инструкция, которая просто
#: лежит на диске, подключением не является: новая сессия редактора о ней не
#: узнаёт, пока ей не скажут путь. А первой командой редактор всё равно
#: вызывает этот инструмент — значит инструмент и есть место, где путь нельзя
#: не заметить. Версия рядом с путём затем, чтобы устаревшая локальная копия
#: обнаруживалась сравнением, а не на последствиях.
ИНСТРУКЦИЯ = ("/srv/site-factory/qwen-seo-handover-2026-10-01/"
              "QWEN-CANONICAL.md")
ВЕРСИЯ_ИНСТРУКЦИИ = "2026-10-02.2"


def _со_ссылкой(данные: dict) -> dict:
    """Добавить к ответу путь к правилам и их версию."""
    return {**данные, "instruction": ИНСТРУКЦИЯ,
            "instruction_version": ВЕРСИЯ_ИНСТРУКЦИИ}


def _автор(args) -> str:
    return args.author or "qwen"


def главная(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="factory.qwen", description=__doc__)
    p.add_argument("операция", choices=[
        "sites", "facts", "prepare", "publish", "confirm", "unpublish",
        "restore", "rollback", "status", "diagnose", "indexing",
        "indexing-state", "indexing-set", "indexing-confirm",
        "indexing-rollback"])
    p.add_argument("--site")
    p.add_argument("--slug")
    p.add_argument("--body-file", help="файл с текстом; '-' — стандартный ввод")
    p.add_argument("--expect-generation")
    p.add_argument("--author")
    p.add_argument("--no-network", action="store_true",
                   help="sites: не опрашивать домены")
    p.add_argument("--mode", choices=["open", "closed"],
                   help="indexing-set: требуемый режим индексации")
    p.add_argument("--expect-release",
                   help="indexing-set: ожидаемый выложенный выпуск; "
                        "при несовпадении операция останавливается")
    args = p.parse_args(argv)

    def нужен(поле: str):
        if not getattr(args, поле.replace("-", "_")):
            print(json.dumps(_со_ссылкой({"ok": False,
                              "reason": f"операции {args.операция} нужен --{поле}"}),
                             ensure_ascii=False))
            raise SystemExit(2)

    try:
        if args.операция == "sites":
            сайты = registry.собрать(опрашивать_сеть=not args.no_network)
            print(json.dumps(_со_ссылкой({"ok": True, "total": len(сайты),
                              "sites": [s.as_dict() for s in сайты]}),
                             ensure_ascii=False, indent=1))
            return 0

        нужен("site")
        if args.операция == "facts":
            print(json.dumps(_со_ссылкой({"ok": True, **editorial.факты(args.site, args.slug)}),
                             ensure_ascii=False, indent=1))
            return 0
        if args.операция == "prepare":
            нужен("slug"); нужен("body-file")
            тело = (sys.stdin.read() if args.body_file == "-"
                    else open(args.body_file, encoding="utf-8").read())
            итог = editorial.подготовить(args.site, args.slug, тело,
                                         author=_автор(args))
            print(json.dumps(_со_ссылкой({"ok": not итог["quality_problems"], **итог}),
                             ensure_ascii=False, indent=1))
            return 0 if not итог["quality_problems"] else 2
        if args.операция == "publish":
            нужен("slug")
            тело = None
            if args.body_file:
                тело = (sys.stdin.read() if args.body_file == "-"
                        else open(args.body_file, encoding="utf-8").read())
            итог = editorial.публиковать(args.site, args.slug, author=_автор(args),
                                         expected_generation=args.expect_generation,
                                         тело=тело)
            print(json.dumps(_со_ссылкой({"ok": итог["state"] == "confirmed", **итог}),
                             ensure_ascii=False, indent=1))
            return 0 if итог["state"] == "confirmed" else 3
        if args.операция == "confirm":
            нужен("slug")
            итог = editorial.подтвердить(args.site, args.slug)
            print(json.dumps(_со_ссылкой({"ok": итог["confirmed"], **итог}),
                             ensure_ascii=False, indent=1))
            return 0 if итог["confirmed"] else 3
        if args.операция == "unpublish":
            нужен("slug")
            итог = editorial.снять(args.site, args.slug, author=_автор(args))
            print(json.dumps(_со_ссылкой({"ok": итог["state"] == "confirmed", **итог}),
                             ensure_ascii=False, indent=1))
            return 0 if итог["state"] == "confirmed" else 3
        if args.операция == "restore":
            нужен("slug")
            итог = editorial.восстановить(args.site, args.slug, author=_автор(args))
            print(json.dumps(_со_ссылкой({"ok": итог["state"] == "confirmed", **итог}),
                             ensure_ascii=False, indent=1))
            return 0 if итог["state"] == "confirmed" else 3
        if args.операция == "rollback":
            print(json.dumps(_со_ссылкой({"ok": True, **editorial.откатить(args.site, author=_автор(args))}),
                             ensure_ascii=False, indent=1))
            return 0
        if args.операция == "status":
            print(json.dumps(_со_ссылкой({"ok": True, **editorial.состояние(args.site)}),
                             ensure_ascii=False, indent=1))
            return 0
        if args.операция.startswith("indexing-"):
            if args.операция == "indexing-state":
                итог = indexing.состояние(args.site)
                print(json.dumps(_со_ссылкой({"ok": True, **итог}), ensure_ascii=False, indent=1))
                return 0
            if args.операция == "indexing-confirm":
                итог = indexing.подтвердить(
                    args.site,
                    ожидаемый=(args.mode or "").upper() if args.mode else "")
                готово = итог["confirmed"] is not False
                print(json.dumps(_со_ссылкой({"ok": готово, **итог}),
                                 ensure_ascii=False, indent=1))
                return 0 if готово else 3
            if args.операция == "indexing-set":
                нужен("mode")
                итог = indexing.установить(args.site, mode=args.mode,
                                      author=_автор(args),
                                      expect_release=args.expect_release or "")
                print(json.dumps(_со_ссылкой({"ok": bool(итог.get("confirmed")), **итог}),
                                 ensure_ascii=False, indent=1))
                return 0 if итог.get("confirmed") else 3
            if args.операция == "indexing-rollback":
                итог = indexing.откатить(args.site, author=_автор(args))
                print(json.dumps(_со_ссылкой({"ok": bool(итог.get("confirmed")), **итог}),
                                 ensure_ascii=False, indent=1))
                return 0 if итог.get("confirmed") else 3
        if args.операция in ("diagnose", "indexing"):
            from factory.qwen import diagnostics
            функция = (diagnostics.диагностика if args.операция == "diagnose"
                       else diagnostics.индексация)
            итог = функция(args.site)
            print(json.dumps(_со_ссылкой({"ok": итог.get("ok", True), **итог}),
                             ensure_ascii=False, indent=1))
            return 0 if итог.get("ok", True) else 3
    except ОТКАЗЫ as отказ:
        print(json.dumps(_со_ссылкой({"ok": False, "reason": str(отказ),
                          "safe_continuation":
                          "причина названа; повторять ту же операцию без "
                          "устранения причины нельзя"}),
                         ensure_ascii=False, indent=1))
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(главная())
