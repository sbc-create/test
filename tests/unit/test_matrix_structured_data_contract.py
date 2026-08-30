"""Объявленная матрицей разметка действительно выпускается — и не молча.

Пробел, который этот тест закрывает, дожил до боевых доменов: матрица для типа
`home` объявляет `structured_data: [WebSite, Organization]`, а три витрины
Lords отдавали только `WebSite`. Расхождение никто не заметил, потому что на
стороне фабрики связи «матрица объявила → страница выпустила» не существовало
вовсе. У Yummy такой контракт есть (`jsonld-matrix-contract.test.ts`), у
фабрики не было.

Честная граница покрытия. URL-шаблоны матрицы описывают схему
`/{category_slug}/{title_slug}/`, а витрины Lords используют `/title/{slug}/`:
сопоставлять типы страниц с путями по шаблону значило бы получать ложные
падения. Поэтому тест проверяет только те типы, для которых путь известен
однозначно, и явно перечисляет остальные.

Главное — второй тест: он падает, когда матрица объявляет **новый безусловный**
тип разметки, для которого в этом файле нет проверки. Именно молчание при
появлении нового объявления и позволило пробелу дожить до LIVE.
"""

from __future__ import annotations

import json
import re

import pytest
import yaml

from factory.lords import fixtures as fx
from factory.lords import render
from factory.paths import PATHS

SITES = ("lords-01", "lords-02", "lords-03")
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)

#: Типы страниц, для которых этот файл знает конкретный путь витрины Lords.
COVERED: dict[str, str] = {"home": "/"}

#: Типы, сознательно оставленные без проверки, с причиной. Молчаливого
#: пропуска быть не должно: причина видна в коде, а не в чьей-то памяти.
UNCOVERED: dict[str, str] = {
    "category": "адреса витрин не совпадают с шаблоном матрицы",
    "collection": "адреса витрин не совпадают с шаблоном матрицы",
    "title": "адреса витрин не совпадают с шаблоном матрицы",
    "season": "витрины Lords не строят страницы сезонов",
    "episode": "витрины Lords не строят страницы серий",
    "article": "раздел новостей витрин не соответствует шаблону /news/{slug}/",
    "news_index": "у витрин раздел называется /new/, а не /news/",
    "tag": "витрины не строят страницы тегов",
    "author": "витрины не строят страницы авторов",
    "paginated_page": "хлебные крошки постраничных списков проверяет seo-crawl",
    "legal": "юридические страницы витрин не входят в этот контракт",
    "service": "служебные страницы разметку не несут",
    "filter_indexable": (
        "фасет из allowlist: у витрин Lords индексируемых фасетов нет — "
        "все фасетные индексы неиндексируемы по плану, проверять нечего"
    ),
    "content_unavailable": (
        "страница материала без доступного видео: у витрин это обычная страница "
        "произведения, отдельного типа не возникает"
    ),
}

CONDITIONAL = ("_when_", "_or_")


def _unconditional(entries) -> list[str]:
    """Типы, объявленные безусловно: `X_when_available` — это не обещание."""
    return [e for e in (entries or []) if not any(mark in e for mark in CONDITIONAL)]


def _matrix_rows() -> list[dict]:
    raw = PATHS.root / "knowledge" / "SEO_INDEXABILITY_MATRIX.yaml"
    return yaml.safe_load(raw.read_text(encoding="utf-8"))["page_types"]


def _emitted_types(site_id: str, path: str) -> set[str]:
    pkg = yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))
    site = render.render_site(pkg, catalog=fx.build_catalog())
    body = site.pages[path].body
    out: set[str] = set()
    for raw in LD.findall(body):
        data = json.loads(raw)
        for node in (data if isinstance(data, list) else [data]):
            if isinstance(node, dict) and node.get("@type"):
                out.add(node["@type"])
    return out


@pytest.mark.parametrize("site_id", SITES)
def test_covered_page_types_emit_what_the_matrix_declares(site_id):
    rows = {r["id"]: r for r in _matrix_rows()}
    for page_type, path in COVERED.items():
        declared = _unconditional(rows[page_type].get("structured_data"))
        assert declared, f"матрица не объявляет разметку для {page_type} — проверять нечего"
        emitted = _emitted_types(site_id, path)
        missing = [t for t in declared if t not in emitted]
        assert not missing, (
            f"{site_id} {path}: матрица объявляет {declared}, страница выпускает "
            f"{sorted(emitted)}, не хватает {missing}"
        )


def test_no_declared_markup_stays_unchecked_silently():
    """Новый безусловный тип в матрице обязан попасть в COVERED или UNCOVERED."""
    unaccounted = []
    for row in _matrix_rows():
        page_type = row["id"]
        if not _unconditional(row.get("structured_data")):
            continue
        if page_type in COVERED or page_type in UNCOVERED:
            continue
        unaccounted.append((page_type, row.get("structured_data")))
    assert not unaccounted, (
        "матрица объявляет разметку, которую никто не проверяет и не объяснил: "
        + ", ".join(f"{t} → {d}" for t, d in unaccounted)
    )
