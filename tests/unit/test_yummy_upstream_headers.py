"""Внутренний запрос витрины наверх не наследует согласование содержимого клиента.

Дефект, ради которого проверка написана и который она обязана не пустить назад.

Браузер предзагружает маршруты Next.js с заголовком ``RSC: 1``, прося не
разметку, а flight-полезную нагрузку. Витрина, собирая собственную страницу
«Топ», ходит наверх за обычным HTML — и пересылала туда все заголовки клиента,
включая ``RSC``. Наверху приходил не HTML, разбор оболочки срывался, страница
не собиралась, и запрос проваливался в общее проксирование: ``/top`` с
``RSC: 1`` отвечал 404.

Воспроизводилось устойчиво на всех трёх витринах Yummy::

    curl -H 'RSC: 1' https://yummyani.site/top   -> 404
    curl              https://yummyani.site/top   -> 200

Посетитель видел рабочую страницу при обычном заходе и ошибку в консоли при
клиентском переходе на «Топ».

Важно, что вырезание относится только к ВНУТРЕННЕМУ запросу. Общее
проксирование обязано отдавать наверх настоящий запрос клиента: там ``RSC``
уместен, и приложение само решает, чем ответить.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import re
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ФРОНТ = КОРЕНЬ / "automation" / "host" / "yummy-frontend.py"

МАНИФЕСТ_ДЛЯ_ТЕСТА = {
    "schema_version": "1.0", "template_family": "yummy", "design_version": "тест",
    "source_commit": "0" * 40, "build_id": "test", "artifact_sha256": "0" * 64,
    "profile": "test", "built_at": "2026-09-16T00:00:00Z",
}


@pytest.fixture(scope="module")
def посредник(tmp_path_factory):
    """Посредник со своим манифестом: от машины выкладки проверка не зависит."""
    путь = tmp_path_factory.mktemp("манифест") / "template-manifest.json"
    путь.write_text(json.dumps(МАНИФЕСТ_ДЛЯ_ТЕСТА, ensure_ascii=False), encoding="utf-8")
    import os
    прежний = os.environ.get("LORDS_TEMPLATE_MANIFEST")
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(путь)
    try:
        загрузчик = importlib.machinery.SourceFileLoader("yf_headers", str(ФРОНТ))
        модуль = importlib.util.module_from_spec(
            importlib.util.spec_from_loader("yf_headers", загрузчик)
        )
        загрузчик.exec_module(модуль)
        return модуль
    finally:
        if прежний is None:
            os.environ.pop("LORDS_TEMPLATE_MANIFEST", None)
        else:
            os.environ["LORDS_TEMPLATE_MANIFEST"] = прежний


def test_общие_вырезаемые_остались_прежними(посредник) -> None:
    assert {"host", "accept-encoding", "connection"} == посредник.ВЫРЕЗАЕМЫЕ_ОБЩИЕ


@pytest.mark.parametrize(
    "заголовок", ["rsc", "next-router-prefetch", "next-router-state-tree", "next-url"]
)
def test_заголовки_предзагрузки_не_уходят_во_внутренний_запрос(посредник, заголовок) -> None:
    assert заголовок in посредник.ВЫРЕЗАЕМЫЕ_ВНУТРИ, (
        f"{заголовок} снова пересылается наверх: страница «Топ» опять соберётся не из HTML"
    )


def test_согласование_содержимого_не_наследуется(посредник) -> None:
    """Accept клиента не должен решать, что получит витрина для сборки."""
    assert "accept" in посредник.ВЫРЕЗАЕМЫЕ_ВНУТРИ


def test_внутренний_набор_шире_общего(посредник) -> None:
    assert посредник.ВЫРЕЗАЕМЫЕ_ОБЩИЕ < посредник.ВЫРЕЗАЕМЫЕ_ВНУТРИ


def test_внутренний_запрос_задаёт_свой_accept() -> None:
    исходник = ФРОНТ.read_text(encoding="utf-8")
    тело = исходник[исходник.index("def _сырое_наверх"):]
    тело = тело[:тело.index("\n    def ", 1)]
    assert "ВЫРЕЗАЕМЫЕ_ВНУТРИ" in тело, "внутренний запрос перестал вырезать заголовки клиента"
    assert re.search(r'заг\["Accept"\]\s*=\s*"text/html', тело), (
        "внутренний запрос перестал явно просить разметку"
    )


def test_общее_проксирование_отдаёт_наверх_настоящий_запрос() -> None:
    """Там вырезать RSC нельзя: приложение само решает, чем ответить.

    Проверка именно на отсутствие: если внутренний набор попадёт и сюда,
    клиентская навигация Next.js сломается уже на маршрутах приложения.
    """
    исходник = ФРОНТ.read_text(encoding="utf-8")
    вхождения = исходник.count("ВЫРЕЗАЕМЫЕ_ВНУТРИ")
    assert вхождения == 2, (
        "ВЫРЕЗАЕМЫЕ_ВНУТРИ упоминается не дважды (объявление и внутренний запрос): "
        f"найдено {вхождения}"
    )
