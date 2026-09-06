"""Сверка состояния витрины до и после операции.

Проверяется ровно то, что обязано сохраниться, и ровно то, что обязано
измениться. «Похоже, всё в порядке» здесь не ответ: после обновления каталога
шаблон обязан совпасть до последнего поля, а снимок каталога и номер релиза
обязаны отличаться — иначе это тот же релиз под новым именем.
"""

import json
import pathlib
import sys

СОХРАНЯЮТСЯ = ("tenant_id", "domain", "theme", "template_artifact_ref",
               "template_digest", "renderer_revision", "content_source",
               "production_authorized")
МЕНЯЮТСЯ = ("content_snapshot_id", "created_at")


def снимок(сайты):
    из = {}
    for сайт in сайты:
        ссылка = pathlib.Path("/srv/lords") / сайт / "current"
        релиз = ссылка.resolve()
        м = релиз / "release-manifest.json"
        из[сайт] = {"release": релиз.name,
                    "manifest": json.loads(м.read_text(encoding="utf-8")) if м.is_file() else None}
    return из


def сверить(до, после, *, ожидается_новый_релиз, сайт):
    беды = []
    a, b = до[сайт], после[сайт]
    if a["manifest"] is None or b["manifest"] is None:
        return [f"{сайт}: манифест отсутствует до или после"]
    for поле in СОХРАНЯЮТСЯ:
        if a["manifest"].get(поле) != b["manifest"].get(поле):
            беды.append(f"{сайт}: {поле} изменилось: "
                        f"{a['manifest'].get(поле)!r} -> {b['manifest'].get(поле)!r}")
    if ожидается_новый_релиз:
        if a["release"] == b["release"]:
            беды.append(f"{сайт}: релиз не сменился ({a['release']})")
        for поле in МЕНЯЮТСЯ:
            if a["manifest"].get(поле) == b["manifest"].get(поле):
                беды.append(f"{сайт}: {поле} не изменилось — это тот же релиз под новым именем")
        if b["manifest"].get("previous_release") != a["release"]:
            беды.append(f"{сайт}: предыдущий релиз указан как "
                        f"{b['manifest'].get('previous_release')!r}, а был {a['release']!r}")
        if not b["manifest"].get("rollback_target"):
            беды.append(f"{сайт}: цель отката пуста")
    else:
        if a["release"] != b["release"]:
            беды.append(f"{сайт}: релиз сменился, хотя не должен был: "
                        f"{a['release']} -> {b['release']}")
    return беды


if __name__ == "__main__":
    режим = sys.argv[1]
    файл = pathlib.Path(sys.argv[2])
    сайты = sys.argv[3].split(",") if len(sys.argv) > 3 else ["lords-01", "lords-02", "lords-03"]
    if режим == "save":
        файл.write_text(json.dumps(снимок(сайты), ensure_ascii=False, indent=2), encoding="utf-8")
        for с in сайты:
            м = снимок(сайты)[с]["manifest"] or {}
            print(f"{с:9} релиз={снимок(сайты)[с]['release']:14} "
                  f"шаблон={str(м.get('template_digest'))[:16]} "
                  f"снимок={м.get('content_snapshot_id')}")
    else:
        до = json.loads(файл.read_text(encoding="utf-8"))
        после = снимок(сайты)
        цель = sys.argv[4] if len(sys.argv) > 4 else "lords-02"
        новый = режим == "changed"
        беды = сверить(до, после, ожидается_новый_релиз=новый, сайт=цель)
        for с in сайты:
            if с == цель:
                continue
            беды += сверить(до, после, ожидается_новый_релиз=False, сайт=с)
        for с in сайты:
            м = после[с]["manifest"] or {}
            метка = "цель" if с == цель else "сосед"
            print(f"{с:9} [{метка}] релиз={после[с]['release']:14} "
                  f"шаблон={str(м.get('template_digest'))[:16]} "
                  f"снимок={м.get('content_snapshot_id')} "
                  f"откат={м.get('rollback_target')}")
        print()
        if беды:
            print("ПРОВАЛЫ:")
            for б in беды:
                print("  -", б)
            sys.exit(1)
        print("сверка пройдена: сохранилось то, что обязано, изменилось то, что должно")
