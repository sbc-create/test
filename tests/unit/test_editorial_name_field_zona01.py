"""Передача 114: подтверждённое русское название переживает публикацию описаний.

Повод — заявка сессии zona-01 (`coordination/v1/handoffs/114-zona-01-to-architect-editorial-name-field.md`).
Проверено по коду: в ветке `editorial-queue` функция `editorial._доставить`
собирала ПОЛНЫЙ состав файла правок из одних описаний
(`{"fields": {"description": …}}`), а файл заменяется целиком. Значит запись
`name`, сделанная другой сессией, исчезала на первой же публикации описания —
или эта публикация вообще отказывала, потому что `_чужая_правка` видит чужой
отпечаток живого файла.

Хранилище правок при этом `name` принимает давно (`editorial_store.ПОЛЯ`), то
есть не хватало ровно сохранения состава.

Сторожится путь ЗАПИСИ для zona-01 (zonafilm.space): состав, который уходит
исполнителю, и авторство записей. Чтение накладки витриной проверяется отдельно
(`test_zona_editorial_title_overlay.py` — на выложенном модуле zonafilm.cc) и
здесь не дублируется.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import editorial_store  # noqa: E402
from factory.qwen import editorial, registry  # noqa: E402

ИД = "01a1252c-9a84-7175-bcf2-ec7cea1cf1b0"
НАЗВАНИЕ = "История наших отношений"
ОРИГИНАЛ = "Silsila Badalte Rishton Ka"


class Сайт:
    site_id = "zona-01"
    domain = "zonafilm.space"
    adapter = "lords"
    account = "zonafilm-space"


@pytest.fixture()
def стенд(tmp_path, monkeypatch):
    """Живой файл правок zona-01 в песочнице: боевой не затрагивается."""
    живой = tmp_path / "editorial-overrides.json"
    живой.write_text(json.dumps({
        "schema_version": 1,
        "site_id": "zona-01",
        "overrides": {
            ИД: {"fields": {"name": НАЗВАНИЕ, "original_name": ОРИГИНАЛ},
                 "actor": "zona-01/posters-titles/run-7",
                 "reason": "подтверждено по ru-статье и Wikidata (путь D200)"},
            "dorohedoro-2-2": {"fields": {"description": "Прежнее описание."},
                               "actor": "editor/claude-auto/run-1",
                               "reason": "описание"},
        },
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(registry, "путь_доставки", lambda s: str(живой))
    monkeypatch.setattr(registry, "механизм", lambda s: "editorial-queue")
    return живой


def test_живой_файл_читается_по_записям(стенд):
    записи = editorial._живые_правки(Сайт())
    assert set(записи) == {ИД, "dorohedoro-2-2"}
    assert записи[ИД]["fields"]["name"] == НАЗВАНИЕ


def test_чужой_по_сайту_файл_состава_не_даёт(стенд):
    """Файл другого сайта в своём месте — перепутанная область, не состав."""
    стенд.write_text(json.dumps({"site_id": "zona-03",
                                 "overrides": {ИД: {"fields": {"name": "Чужое"}}}},
                                ensure_ascii=False), encoding="utf-8")
    assert editorial._живые_правки(Сайт()) == {}


def test_состав_сохраняет_название_и_добавляет_описание(стенд, monkeypatch):
    """Главное свойство передачи 114: публикация описания не стирает `name`."""
    поданное = {}

    def перехват(s, правки, *, author, reason):
        поданное.update({"правки": правки, "author": author, "reason": reason})
        return {"request_id": "zona-01-edit-проба", "status": "accepted"}

    monkeypatch.setattr(editorial, "_подать_правки", перехват)
    monkeypatch.setattr(editorial, "_записать_атомарно", lambda *а, **к: None)
    monkeypatch.setattr(editorial, "_каталог", lambda s: стенд.parent)
    monkeypatch.setattr(editorial, "_чужая_правка", lambda s: "")

    новое = [{"title_id": "dorohedoro-2-2", "body": "Новое описание дорохедоро."}]
    editorial._доставить(Сайт(), новое, новое, поколение="g-1",
                         author="editor/claude-auto/run-9", reason="описание")

    правки = поданное["правки"]
    # 1. Запись с названием осталась, и её поля не тронуты.
    assert правки[ИД]["fields"]["name"] == НАЗВАНИЕ
    assert правки[ИД]["fields"]["original_name"] == ОРИГИНАЛ
    assert "description" not in правки[ИД]["fields"]
    # 2. Авторство чужой записи сохранено, а не переписано на редактора.
    assert правки[ИД]["actor"] == "zona-01/posters-titles/run-7"
    assert "Wikidata" in правки[ИД]["reason"]
    # 3. Своё описание записано.
    assert правки["dorohedoro-2-2"]["fields"]["description"] == \
        "Новое описание дорохедоро."


def test_описание_не_теряет_прочие_поля_той_же_записи(стенд, monkeypatch):
    """Описание к записи, у которой есть название, добавляется, а не замещает."""
    поданное = {}
    monkeypatch.setattr(editorial, "_подать_правки",
                        lambda s, правки, *, author, reason: поданное.update(
                            {"правки": правки}) or {"request_id": "x"})
    monkeypatch.setattr(editorial, "_записать_атомарно", lambda *а, **к: None)
    monkeypatch.setattr(editorial, "_каталог", lambda s: стенд.parent)
    monkeypatch.setattr(editorial, "_чужая_правка", lambda s: "")

    новое = [{"title_id": ИД, "body": "Описание сериала."}]
    editorial._доставить(Сайт(), новое, новое, поколение="g-2",
                         author="editor/claude-auto/run-9", reason="описание")
    поля = поданное["правки"][ИД]["fields"]
    assert поля["name"] == НАЗВАНИЕ, поля
    assert поля["original_name"] == ОРИГИНАЛ, поля
    assert поля["description"] == "Описание сериала.", поля


def test_хранилище_принимает_название_и_хранит_авторство():
    """Состав, который уйдёт исполнителю, сохраняет и поля, и авторство."""
    содержимое = editorial_store.собрать(
        "zona-01",
        {ИД: {"fields": {"name": НАЗВАНИЕ, "original_name": ОРИГИНАЛ},
              "actor": "zona-01/posters-titles/run-7", "reason": "подтверждено"},
         "dorohedoro-2-2": {"fields": {"description": "Текст."}}},
        actor="editor/claude-auto/run-9", reason="описание")
    записи = содержимое["overrides"]
    assert записи[ИД]["fields"]["name"] == НАЗВАНИЕ
    assert записи[ИД]["actor"] == "zona-01/posters-titles/run-7"
    assert записи[ИД]["reason"] == "подтверждено"
    # Запись без своего авторства получает авторство вызывающего — как прежде.
    assert записи["dorohedoro-2-2"]["actor"] == "editor/claude-auto/run-9"


def test_поля_поставщика_по_прежнему_отвергаются():
    """Расширение состава не открыло запись чужих полей."""
    with pytest.raises(editorial_store.StoreRejected) as ош:
        editorial_store.собрать("zona-01",
                                {ИД: {"fields": {"sources": [{"provider": "kp"}]}}},
                                actor="a", reason="b")
    assert "поставщику" in str(ош.value)
