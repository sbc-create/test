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

НОВОСТИ раздела `/posts` — отдельные операции над отдельным материалом:

    python3 -m factory.qwen posts-status    --site <домен>
    python3 -m factory.qwen posts-prepare   --site <домен> --slug <слаг> --post-file <файл>
    python3 -m factory.qwen posts-publish   --site <домен> --slug <слаг>
    python3 -m factory.qwen posts-unpublish --site <домен> --slug <слаг>

Новость и карточка аниме — РАЗНЫЕ материалы с разными адресами. `prepare`/
`publish` пишут накладку описания карточки (`/anime/<slug>`), `posts-*` —
новость (`/posts/<slug>`). Подмена одного другим даёт запись, которой не
соответствует ни одна страница: 404 на обоих адресах.

Тело материала передаётся ФАЙЛОМ (`--body-file`, для новости — `--post-file`)
или стандартным вводом, а не аргументом командной строки: текст пользователя
в исполняемую строку не попадает ни при каких условиях.

Вывод — JSON на стандартный вывод. Код возврата: 0 — операция подтверждена,
2 — отказ с названной причиной, 3 — записано, но НЕ подтверждено на странице.
"""
from __future__ import annotations

import argparse
import json
import sys

from factory.qwen import editorial, indexing, posts, registry


#: Отказы всех операций — одного рода: названная причина вместо трассы.
#: Перечислены кортежем, потому что ветвей обработки должно быть ровно одна:
#: два отдельных `except` с одинаковым телом расходятся при первой правке.
ОТКАЗЫ = (editorial.ОперацияОтклонена, indexing.Отказано,
          posts.ОперацияОтклонена)

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
ВЕРСИЯ_ИНСТРУКЦИИ = "2026-10-05.1"


def _со_ссылкой(данные: dict) -> dict:
    """Добавить к ответу путь к правилам и их версию."""
    return {**данные, "instruction": ИНСТРУКЦИЯ,
            "instruction_version": ВЕРСИЯ_ИНСТРУКЦИИ}


def _автор(args) -> str:
    return args.author or "qwen"


def главная(argv: list[str] | None = None) -> int:
    # Описание печатается КАК НАПИСАНО. Это не украшение: `--help` и есть та
    # поверхность, на которой сессия без инструментов узнаёт, какая операция
    # какой материал пишет. Форматировщик по умолчанию склеивал перечень
    # команд и таблицу материалов в один абзац, и различие новости и карточки
    # в нём терялось — ровно то различие, из-за которого новость попала в
    # накладку описания карточки.
    p = argparse.ArgumentParser(
        prog="factory.qwen", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("операция", choices=[
        "sites", "facts", "prepare", "publish", "confirm", "unpublish",
        "restore", "rollback", "status", "diagnose", "indexing",
        "indexing-state", "indexing-set", "indexing-confirm",
        "indexing-rollback",
        "posts-status", "posts-prepare", "posts-publish", "posts-unpublish"])
    p.add_argument("--site")
    p.add_argument("--slug")
    p.add_argument("--body-file", help="файл с текстом; '-' — стандартный ввод")
    p.add_argument("--post-file",
                   help="posts-prepare: файл JSON с полями новости "
                        "(title, excerpt, body, type, channel_name, "
                        "external_url, thumbnail_url); '-' — стандартный ввод")
    p.add_argument("--expect-generation")
    p.add_argument("--author")
    p.add_argument("--no-network", action="store_true",
                   help="sites: не опрашивать домены")
    p.add_argument("--mode", choices=["open", "closed"],
                   help="indexing-set: требуемый режим индексации")
    p.add_argument("--no-prove", action="store_true",
                   help="indexing: не поднимать выложенный релиз для "
                        "доказательства чтения конфигурации; статус "
                        "останется MECHANISM_UNPROVEN")
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
        if args.операция.startswith("posts-"):
            # НОВОСТИ. Отдельные команды, а не режим `prepare`: материал
            # другой, файл другой, адрес другой. Единая команда с флагом
            # привела бы к ровно той ошибке, ради которой эти четыре
            # появились, — новость, записанная в накладку карточки.
            if args.операция == "posts-status":
                итог = posts.состояние(args.site)
                print(json.dumps(_со_ссылкой({"ok": not итог["problems"], **итог}),
                                 ensure_ascii=False, indent=1))
                return 0 if not итог["problems"] else 3
            нужен("slug")
            if args.операция == "posts-prepare":
                нужен("post-file")
                сырое = (sys.stdin.read() if args.post_file == "-"
                         else open(args.post_file, encoding="utf-8").read())
                try:
                    поля = json.loads(сырое)
                except ValueError as ош:
                    raise posts.ОперацияОтклонена(
                        f"--post-file не читается как JSON: {ош}") from None
                if not isinstance(поля, dict):
                    raise posts.ОперацияОтклонена(
                        "--post-file: ожидается объект JSON с полями новости")
                абзацы = поля.get("body")
                if not isinstance(абзацы, list) or not абзацы:
                    raise posts.ОперацияОтклонена(
                        "body: список абзацев (строк). Пустой текст новостью "
                        "не является")
                итог = posts.подготовить(
                    args.site, args.slug,
                    title=str(поля.get("title") or ""),
                    excerpt=str(поля.get("excerpt") or ""),
                    body=[str(а) for а in абзацы],
                    author=(str(поля.get("author") or "").strip()
                            or args.author or "Редакция"),
                    тип=str(поля.get("type") or "news"),
                    channel=поля.get("channel_name") or None,
                    external_url=поля.get("external_url") or None,
                    thumbnail_url=поля.get("thumbnail_url") or None)
                print(json.dumps(_со_ссылкой({"ok": not итог["quality_problems"],
                                              **итог}),
                                 ensure_ascii=False, indent=1))
                return 0 if not итог["quality_problems"] else 2
            if args.операция == "posts-publish":
                итог = posts.опубликовать(args.site, args.slug,
                                          author=_автор(args))
                # Код 3 — ровно тот случай, под который он и объявлен в
                # заголовке файла: ЗАПИСАНО, но на странице НЕ подтверждено.
                # Прежде код считался по `status`, и запись при 404 на
                # публичном адресе давала 0 (измерено 2026-10-05).
                записано = итог["status"] in ("created", "updated",
                                              "nothing-to-do")
                подтверждено = bool(итог.get("public_confirmed"))
                print(json.dumps(_со_ссылкой({"ok": записано and подтверждено,
                                              "written": записано, **итог}),
                                 ensure_ascii=False, indent=1))
                if not записано:
                    return 2
                return 0 if подтверждено else 3
            if args.операция == "posts-unpublish":
                итог = posts.снять(args.site, args.slug, author=_автор(args))
                готово = итог["status"] in ("unpublished", "nothing-to-do")
                print(json.dumps(_со_ссылкой({"ok": готово, **итог}),
                                 ensure_ascii=False, indent=1))
                return 0 if готово else 3
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
        if args.операция == "indexing":
            # ВЕРДИКТ готовности, а не четыре сигнала. Прежний ответ отвечал
            # полем `ok` на вопрос «главная ответила 200», и для закрытого
            # домена без разрешения владельца это давало `ok: true` — отчёт по
            # сети получался противоречивым. Все прежние величины остались
            # внутри (`evidence.public`), ответ стал надмножеством.
            итог = indexing.готовность(args.site, доказать=not args.no_prove)
            print(json.dumps(_со_ссылкой(итог), ensure_ascii=False, indent=1))
            return 0 if итог.get("status") == "OPEN_CONFIRMED" else 3
        if args.операция == "diagnose":
            from factory.qwen import diagnostics
            итог = diagnostics.диагностика(args.site)
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
