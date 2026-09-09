"""Доказательство, что два новых параметра ничего не меняют по умолчанию.

Сравнивается не «похоже», а байты: снимок Lords, собранный кодом BASE_SHA, и
снимок, собранный текущим кодом, на одном и том же входе и с одним и тем же
временем наблюдения. Разойдись они хоть на байт — Lords пришлось бы
перевыкладывать, а задание этого не просило.
"""
import datetime as dt, hashlib, importlib.util, json, pathlib, subprocess, sys

КОРЕНЬ = "/home/claude/wt-core-ident-35"
BASE = "974a8bb65c766c3244b9f41cd4437bebdd3e5362"
sys.path.insert(0, КОРЕНЬ)

# Код базы достаётся из объекта git, а не из рабочего дерева: рабочее дерево
# уже изменено, и сравнение с ним сравнивало бы файл сам с собой.
исходник = subprocess.run(
    ["git", "show", f"{BASE}:factory/site_engine/route_snapshot.py"],
    cwd=КОРЕНЬ, capture_output=True, text=True, check=True).stdout
врем = pathlib.Path("/home/claude/ident-35-artifacts/route_snapshot_base.py")
врем.write_text(исходник, encoding="utf-8")
спец = importlib.util.spec_from_file_location("rs_base", врем)
база = importlib.util.module_from_spec(спец)
# Модуль обязан лежать в sys.modules ДО исполнения: dataclasses ищет
# там пространство имён класса и без записи падает на первом же
# декораторе.
sys.modules["rs_base"] = база
спец.loader.exec_module(база)

from factory.site_engine import route_snapshot as текущий
from factory.lords.live_catalog import slugify

сырьё = json.loads(pathlib.Path(
    "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json"
).read_text(encoding="utf-8"))
записи, метка = сырьё["items"], сырьё["mark"]


def адрес(name, external_id):
    return f"/title/{slugify(name) or external_id.lower()}/"


наблюдение = dt.datetime(2026, 9, 9, 23, 0, tzinfo=dt.timezone.utc)
общее = dict(site_id="lords-01", route_of=адрес, observed_at=наблюдение,
             producer_sha=BASE, source_digest="0" * 32,
             generation_reason="full-rebuild",
             tag_vocabulary=текущий.load_tag_vocabulary(КОРЕНЬ),
             source_observed_at=метка)

итог = {}
for имя, модуль in (("BASE_SHA", база), ("рабочее дерево", текущий)):
    снимок = модуль.build(записи, content_kind_of=модуль.catalog_kind, **общее)
    байты = json.dumps(снимок.as_dict(), ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode()
    итог[имя] = (hashlib.sha256(байты).hexdigest(), len(байты))
    print(f"{имя:16} sha256={итог[имя][0]}  байт={итог[имя][1]}")

совпало = итог["BASE_SHA"][0] == итог["рабочее дерево"][0]
print("\nснимок Lords идентичен побайтно:", совпало)
sys.exit(0 if совпало else 1)
