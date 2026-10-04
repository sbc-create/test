"""Служебные записи фабрики не требуют читателя на стороне сайта.

Ворота защищённых данных отвечают на один вопрос: перестанет ли выпускаемый
код читать то, что уже записано. Для редакционных правок защищается каталог
наложений целиком — и в нём лежат файлы ДВУХ разных владельцев:

* `title-overlays.json` — его читает ВЫПУСК сайта (`src/editorial_overlay.py`,
  `src/seo_overlay.py`). Выпуск без читателя перестал бы показывать
  опубликованные правки, и со стороны это неотличимо от потери данных;
* `drafts.json`, `history.jsonl`, `published.json`, `unpublished.json`,
  `delivered.json` — записи управляющего слоя (`factory.qwen.editorial`).
  Ни один репозиторий сайта их не читает: измерено 2026-10-04 по всем рабочим
  копиям, упоминание `drafts.json` есть только в самой фабрике.

Случай измерен на lords-02 (lordserial33.biz). Операция `prepare_material`
2026-10-01 положила в каталог наложений ОДИН подготовленный, но не
опубликованный материал — `drafts.json` и `history.jsonl`. Файла
`title-overlays.json` там нет и никогда не было. Ворота отклонили выпуск:
«не несёт читателей защищённых данных — editorial». Терять было нечего:
читаемого сайтом артефакта в каталоге нет, а служебные записи фабрики выпуск
и не должен читать. Требование читателя за них означало бы, что подготовка
черновика в управляющем слое запирает выпуск сайта.

Ворота от этого не слабеют. Перечень служебных имён ЗАКРЫТЫЙ: любой другой
файл — включая неизвестный — по-прежнему считается данными и требует читателя,
а нечитаемый каталог требует его тем более.
"""
from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

from factory.cell import protected


@pytest.fixture()
def стенд(tmp_path, monkeypatch):
    """Каталог правок семейства и рабочая копия БЕЗ читателя правок."""
    корень = tmp_path / "overlays"
    склад = корень / "сайт.test"
    склад.mkdir(parents=True)
    monkeypatch.setattr(protected, "_корни_наложений", lambda: {"lords": корень})
    # Прочие виды защищённых данных на стенде отсутствуют: предмет здесь —
    # только каталог правок.
    monkeypatch.setattr(protected, "_контрактные", lambda _: [])
    monkeypatch.setattr(protected, "КОРЕНЬ_ИНДЕКСАЦИИ", tmp_path / "нет-индексации")
    monkeypatch.setattr(protected, "КОРЕНЬ_NGINX_ЯЧЕЕК", tmp_path / "нет-nginx")

    репо = tmp_path / "repo"
    (репо / "src").mkdir(parents=True)
    (репо / "src" / "frontend.py").write_text("# витрина\n", encoding="utf-8")
    for команда in (["git", "init", "-q"], ["git", "config", "user.email", "t@t"],
                    ["git", "config", "user.name", "t"], ["git", "add", "-A"],
                    ["git", "commit", "-qm", "первый"]):
        subprocess.run(команда, cwd=репо, check=True)
    коммит = subprocess.run(["git", "rev-parse", "HEAD"], cwd=репо,
                            capture_output=True, text=True).stdout.strip()

    def ворота() -> dict:
        return protected.проверить_выпуск("lords-02", "сайт.test", репо, коммит,
                                          adapter="lords")

    return {"склад": склад, "ворота": ворота}


def test_только_служебные_записи_данными_не_считаются(стенд):
    (стенд["склад"] / "drafts.json").write_text(
        json.dumps({"items": {"1-11": {}}}), encoding="utf-8")
    (стенд["склад"] / "history.jsonl").write_text('{"op": "prepare"}\n',
                                                  encoding="utf-8")
    итог = стенд["ворота"]()
    assert итог["missing_readers"] == [], (
        "подготовка черновика в управляющем слое заперла бы выпуск сайта: "
        f"читаемого сайтом файла в каталоге нет — {итог}")
    assert итог["compatible"] is True, итог
    assert "editorial" in (итог.get("empty_kinds") or []), (
        "каталог существует, и отчёт обязан это называть")


def test_файл_который_читает_выпуск_это_данные(стенд):
    (стенд["склад"] / "drafts.json").write_text("{}", encoding="utf-8")
    (стенд["склад"] / "title-overlays.json").write_text(
        json.dumps({"site_id": "lords-02", "overrides": {}}), encoding="utf-8")
    with pytest.raises(protected.ЗащитаДанных) as отказ:
        стенд["ворота"]()
    assert "editorial: src/editorial_overlay.py" in str(отказ.value), (
        "опубликованные правки обязаны требовать читателя: выпуск без него "
        "перестал бы их показывать")


def test_неизвестный_файл_считается_данными(стенд):
    """Перечень служебных имён закрытый: что не названо — данные."""
    (стенд["склад"] / "что-то-новое.json").write_text("{}", encoding="utf-8")
    with pytest.raises(protected.ЗащитаДанных):
        стенд["ворота"]()


def test_пустой_каталог_данными_не_считается(стенд):
    итог = стенд["ворота"]()
    assert итог["missing_readers"] == [], итог
    assert "editorial" in (итог.get("empty_kinds") or [])


def test_нечитаемый_каталог_считается_данными(стенд, monkeypatch):
    """Отказ в чтении — это «каталог есть», а не «пуст»."""
    настоящий = pathlib.Path.iterdir

    def взрыв(self):
        if self == стенд["склад"]:
            raise PermissionError(13, "нет доступа")
        return настоящий(self)

    monkeypatch.setattr(pathlib.Path, "iterdir", взрыв)
    with pytest.raises(protected.ЗащитаДанных):
        стенд["ворота"]()


def test_служебные_имена_совпадают_с_писателем():
    """Перечень обязан совпадать с тем, что пишет управляющий слой.

    Иначе расхождение вернёт исходный отказ под другим именем файла.
    """
    текст = pathlib.Path("factory/qwen/editorial.py").read_text(encoding="utf-8")
    for имя in protected.СЛУЖЕБНЫЕ_ПРАВКИ:
        assert f'"{имя}"' in текст, (
            f"{имя} в перечне ворот есть, а управляющий слой его не пишет")
