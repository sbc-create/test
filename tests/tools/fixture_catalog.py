"""Набор записей стенда для витрин, чей пакет объявляет источник `fixture`.

Три семейства из пяти (`portal_light`, `pulse`, `editorial`) объявляют в своём
пакете `content_source.kind: fixture` и происхождение «синтетические записи
стенда, созданные внутри репозитория фабрики». Файла набора у них нет:
`content_package_ref: null`. Пока его нет, приёмка этих семейств упирается не в
админку, а в отсутствие того, чем управлять.

Этот сценарий создаёт набор **в корне стенда**, а не в репозитории: файл пакета
живой витрины принадлежит TEMPLATES (открыт handoff 032), и дописывать его
отсюда значило бы разойтись с чужой поставкой.

Записи заведомо синтетические и подписаны как таковые в каждом поле: набор
доказывает путь администратора, а не содержимое витрины. Часть записей
намеренно противоречива — объявленный вид расходится с названием, — иначе
очередь разбора окажется пустой и утверждать будет нечего.
"""
import hashlib
import json
import pathlib
import sys

import yaml

# Пятая часть записей — с расхождением: объявлен сериал, а в названии эпизод.
# Обе стороны названы, поэтому решение принимает человек, а не умолчание.
ШАГ_РАСХОЖДЕНИЯ = 5


def построить(site_id: str, count: int) -> dict:
    записи = []
    for н in range(1, count + 1):
        спорная = н % ШАГ_РАСХОЖДЕНИЯ == 0
        название = (
            f"Проверочная запись {н:03d} стенда {site_id}. Эпизод {н % 12 + 1}"
            if спорная
            else f"Проверочная запись {н:03d} стенда {site_id}"
        )
        записи.append(
            {
                "id": f"stand-{site_id}-{н:04d}",
                "title": название,
                "type": "movie" if спорная or not н % 2 else "tv",
                "year": 2000 + н % 25,
                "tags": ["стенд", "синтетика"] + (["ova"] if спорная else []),
                "external_ids": {"stand": f"{site_id}-{н:04d}"},
                "playback": None,
            }
        )
    return {
        "schema_version": 1,
        "generated_by": "tests/tools/fixture_catalog.py",
        "provenance": "Синтетические записи стенда, созданные внутри репозитория фабрики",
        "titles": записи,
    }


def записать(root: pathlib.Path, repo: pathlib.Path, site_id: str, count: int) -> dict:
    каталог = root / "sites" / site_id
    (каталог / "content").mkdir(parents=True, exist_ok=True)

    исходный = repo / "sites" / site_id / "package.yaml"
    пакет = yaml.safe_load(исходный.read_text(encoding="utf-8")) or {}

    тело = json.dumps(построить(site_id, count), ensure_ascii=False, indent=2)
    (каталог / "content" / "catalog.json").write_text(тело, encoding="utf-8")

    # Отпечаток объявляется всегда: без него перенос не сверяет ничего, и
    # подменённый набор попал бы на витрину молча.
    пакет["content_package_ref"] = "content/catalog.json"
    пакет["content_package_sha256"] = hashlib.sha256(тело.encode("utf-8")).hexdigest()
    (каталог / "package.yaml").write_text(
        yaml.safe_dump(пакет, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return {"siteId": site_id, "records": count}


if __name__ == "__main__":
    корень = pathlib.Path(sys.argv[1])
    репо = pathlib.Path("/home/claude/wt-p8-20")
    for сайт in sys.argv[2].split(","):
        print("набор", записать(корень, репо, сайт, int(sys.argv[3] if len(sys.argv) > 3 else 60)))
