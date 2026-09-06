"""Стенд флота: две витрины семейства и операторы на каждой.

Операторы заводятся здесь, а не в браузерном сценарии: приглашение — действие
администратора, и проверять надо путь после входа, а не заведение первого
человека каждый раз заново.
"""
import json
import pathlib
import shutil
import sys

КОРЕНЬ = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/stand-fleet")
РЕПО = pathlib.Path("/home/claude/wt-p8-20")
САЙТЫ = sys.argv[2].split(",") if len(sys.argv) > 2 else ["lords-01", "lords-02"]
ПАРОЛЬ = "длинный-пароль-для-проверки-1"

if КОРЕНЬ.exists():
    shutil.rmtree(КОРЕНЬ)
КОРЕНЬ.mkdir(parents=True)
for имя in ("factory", "tests", "schemas", "knowledge", "inventory", "docs", "blueprints"):
    источник = РЕПО / имя
    if источник.exists():
        (КОРЕНЬ / имя).symlink_to(источник)
shutil.copytree(РЕПО / "config", КОРЕНЬ / "config")
for под in ("var/state", "var/audit", "var/locks", "queue/inbox", "queue/done", "artifacts/jobs"):
    (КОРЕНЬ / под).mkdir(parents=True, exist_ok=True)
(КОРЕНЬ / "var" / "lords").symlink_to(pathlib.Path("/srv/site-factory/repo/var/lords"))

образец = json.loads((РЕПО / "config/site-profiles/lords-01.json").read_text(encoding="utf-8"))
названия = {"lords-01": "Первая витрина", "lords-02": "Вторая витрина",
            "lords-03": "Третья витрина", "site-a": "Портал", "site-b": "Пульс",
            "site-c": "Редакция"}
for сайт in САЙТЫ:
    d = dict(образец)
    d.update({
        "site_id": сайт,
        "domains": [f"{сайт}.test"],
        "canonical_host": f"{сайт}.test",
        "brand": {"name": названия.get(сайт, сайт), "colors": {"primary": "#1f4fd8"}},
        "keep_releases": 8,
    })
    (КОРЕНЬ / "config" / "site-profiles" / f"{сайт}.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

sys.path.insert(0, str(РЕПО))
from factory.paths import PATHS  # noqa: E402

PATHS.root = КОРЕНЬ
from factory.site_engine.operators import OperatorDirectory  # noqa: E402

каталог = OperatorDirectory(КОРЕНЬ)
for сайт in САЙТЫ:
    # Редактор нужен отдельно от администратора: утверждает решение второй
    # человек, и самоутверждение запрещено. Один оператор на сайт сделал бы
    # проверку утверждения невозможной.
    for роль, префикс in (("admin", "admin"), ("viewer", "viewer"), ("editor", "editor")):
        _, секрет = каталог.invite(
            email=f"{префикс}-{сайт}@test", roles=[роль],
            created_by="стенд", site_id=сайт,
        )
        каталог.accept_invite(secret=секрет, password=ПАРОЛЬ)
_, секрет = каталог.invite(
    email="super@test", roles=["admin"], created_by="стенд", super_admin=True)
каталог.accept_invite(secret=секрет, password=ПАРОЛЬ)

# Очередь разбора наполняется из каталога: пустая очередь сделала бы проверку
# пути публикации невозможной, а заводить записи руками — то же, что не иметь
# очереди.
from factory.site_engine import review_build  # noqa: E402

for сайт in САЙТЫ:
    try:
        итог = review_build.rebuild(
            КОРЕНЬ, сайт, env={"SITE_ENGINE_CATALOG_DIR": "var/lords/lords/catalog-cache"},
            limit=3000,
        )
        print("очередь", сайт, "->", итог["created"], "из", итог["scanned"])
    except review_build.ReviewBuildError as ошибка:
        # У витрины другого семейства каталога в этом кэше нет. Подсовывать ей
        # чужой каталог нельзя: зелёный прогон на выдуманных данных доказывает
        # только то, что данные выдуманы.
        print("очередь", сайт, "-> НЕТ КАТАЛОГА:", ошибка)

print("стенд:", КОРЕНЬ)
print("витрины:", САЙТЫ)
print("операторов:", каталог.list()["total"])
