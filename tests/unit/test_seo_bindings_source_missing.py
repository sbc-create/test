"""REQ-SEO-BINDINGS: недоступный источник называется, а не роняет запрос.

Выгрузка связей читает кэш каталога витрины. Когда файла нет — витрина новая,
кэш ещё не собран, каталог перенесён — чтение падало `FileNotFoundError` прямо
из адаптера. Наружу это выходит пятисоткой без причины: потребитель узнаёт, что
«что-то сломалось», и не узнаёт, что именно отсутствует.

Правило контура прежнее и здесь не новое: недоступный источник **называется**.
Пустая выгрузка тоже не годится — она утверждает, что связей нет, тогда как
на деле неизвестно, есть ли они.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS
from factory.site_engine.api import seo_bindings
from factory.site_engine.api.control import ControlApi

REPO = Path(__file__).resolve().parents[2]
ТОКЕН = "tok-seo"
ENV = {
    "SITE_ENGINE_CONTROL_TOKENS": f"{ТОКЕН}=read",
    "SITE_ENGINE_CATALOG_DIR": "var/lords/lords/catalog-cache",
}


@pytest.fixture
def песочница(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    seo_bindings._КЭШ.clear()
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8"))
    образец.update({"site_id": "lords-01", "domains": ["lords-01.test"]})
    (профили / "lords-01.json").write_text(json.dumps(образец, ensure_ascii=False),
                                           encoding="utf-8")
    # Источник связей описан настройкой — иначе отказ придёт раньше и не о том.
    (tmp_path / "config" / "seo-binding-sources.yaml").write_text(
        (REPO / "config" / "seo-binding-sources.yaml").read_text(encoding="utf-8"),
        encoding="utf-8")
    for под in ("var/audit", "var/state", "var/locks", "queue/inbox"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_выгрузка_без_кэша_называет_источник(песочница):
    with pytest.raises(seo_bindings.BindingSourceUnknown) as отказ:
        seo_bindings.выгрузка(песочница, "lords-01")
    сказано = str(отказ.value)
    assert "catalog" in сказано or "каталог" in сказано, сказано


def test_маршрут_отвечает_причиной_а_не_пятисоткой(песочница):
    api = ControlApi(root=песочница, env=ENV)
    ответ = api.handle("GET", "/api/v1/seo-bindings/lords-01",
                       headers={"Authorization": f"Bearer {ТОКЕН}"}, body=None)
    assert ответ.status == 404, f"получено {ответ.status}"
    assert (ответ.body["error"] or {})["code"] == "binding_source_unknown"


def test_пустая_выгрузка_не_выдаётся_за_ответ(песочница):
    # Ноль связей и «неизвестно, есть ли связи» — разные утверждения. Второе
    # нельзя записывать первым: потребитель примет решение по несуществующим
    # данным.
    api = ControlApi(root=песочница, env=ENV)
    ответ = api.handle("GET", "/api/v1/seo-bindings/lords-01",
                       headers={"Authorization": f"Bearer {ТОКЕН}"}, body=None)
    assert "bindings" not in (ответ.body or {})
