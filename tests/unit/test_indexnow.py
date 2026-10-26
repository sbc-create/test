"""IndexNow: отказы важнее отправок.

Метод документирован Яндексом и ничего не стоит, поэтому соблазн «отправить
побольше» прямой. Опасны ровно четыре вещи, и каждая проверяется:
закрытая индексация, чужой ключ, неотдаваемый файл ключа и внешняя запись без
подтверждения. Плюс — чтение режима индексации ИЗ ЕГО ИСТОЧНИКА: первая
редакция читала паспорт и объявляла закрытым домен, у которого в файле
состояния стоит OPEN с разрешением владельца.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_сп = importlib.util.spec_from_file_location(
    "indexnow_submit", КОРЕНЬ / "automation" / "local" / "indexnow-submit.py")
инс = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(инс)

РАНТАЙМ = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


def _состояние(tmp_path: pathlib.Path, домен: str, **поля) -> pathlib.Path:
    д = tmp_path / "indexing"
    д.mkdir(exist_ok=True)
    (д / f"{домен}.json").write_text(json.dumps({"site": домен, **поля},
                                                ensure_ascii=False), encoding="utf-8")
    return д


def test_открыто_только_при_разрешении_владельца(tmp_path):
    я = {"domain": "x.test"}
    корень = _состояние(tmp_path, "x.test", desired_state="OPEN", owner_authorized_open=True)
    открыта, почему = инс.индексация_открыта(я, корень)
    assert открыта and "разрешено владельцем" in почему


def test_open_без_разрешения_владельца_считается_закрытым(tmp_path):
    корень = _состояние(tmp_path, "x.test", desired_state="OPEN", owner_authorized_open=False)
    открыта, почему = инс.индексация_открыта({"domain": "x.test"}, корень)
    assert not открыта and "owner_authorized_open" in почему


def test_нет_файла_состояния_значит_закрыто(tmp_path):
    открыта, почему = инс.индексация_открыта({"domain": "x.test"}, tmp_path / "нет")
    assert not открыта and "fail-closed" in почему


def test_closed_в_файле_состояния_закрыт(tmp_path):
    корень = _состояние(tmp_path, "x.test", desired_state="CLOSED", owner_authorized_open=False)
    открыта, почему = инс.индексация_открыта({"domain": "x.test"}, корень)
    assert not открыта and "CLOSED" in почему


@pytest.mark.parametrize("ключ,годен", [
    ("abcdefgh", True), ("a" * 128, True), ("key-with-dash-123", True),
    ("abcdefg", False), ("a" * 129, False), ("ключ-кириллицей", False),
    ("key_with_underscore", False), ("key with space", False), ("", False),
])
def test_требования_протокола_к_ключу(ключ, годен):
    assert инс.ключ_годен(ключ) is годен


def test_рантайм_отдаёт_файл_ключа_только_по_точному_имени():
    """Иначе любой /<что-угодно>.txt стал бы подтверждением владения."""
    т = РАНТАЙМ.read_text(encoding="utf-8")
    assert 'путь == f"/{INDEXNOW_КЛЮЧ}.txt"' in т
    assert "_ключ_indexnow_годен(INDEXNOW_КЛЮЧ)" in т, "негодный ключ не должен отдаваться"
    assert 'INDEXNOW_КЛЮЧ = (os.environ.get("LORDS_INDEXNOW_KEY") or "").strip()' in т


def test_рантайм_и_инструмент_проверяют_ключ_одним_правилом():
    """Два написания одного требования разошлись бы на первой же правке."""
    т = РАНТАЙМ.read_text(encoding="utf-8")
    assert "8 <= len(ключ) <= 128" in т
    assert инс.ключ_годен("abcdefgh") and not инс.ключ_годен("abcdefg")


def test_генератор_объявляет_переменную_ключа_пустой():
    """Новый сайт рождается без ключа: ключ выдаётся домену отдельно."""
    т = (КОРЕНЬ / "factory" / "cell" / "newsite.py").read_text(encoding="utf-8")
    assert '"LORDS_INDEXNOW_KEY": ""' in т


def test_схема_требует_годный_ключ():
    import jsonschema

    с = json.loads((КОРЕНЬ / "schemas" / "site-cells.schema.json").read_text(encoding="utf-8"))
    поле = с["properties"]["cells"]["items"]["properties"]["indexing"]["properties"]["indexnow_key"]
    jsonschema.validate("abcdefgh", поле)
    jsonschema.validate(None, поле)
    for плохой in ("short", "ключ", "key_underscore"):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(плохой, поле)


def test_коды_ответа_взяты_из_справочника():
    """Смысл кода печатается, а не выдумывается при разборе."""
    assert инс.КОДЫ[200] == "принято"
    assert "проверку" in инс.КОДЫ[202]
    assert инс.КОДЫ[403].startswith("ключ не подошёл")
    assert 429 in инс.КОДЫ and 422 in инс.КОДЫ


def test_адреса_только_https_и_с_пределом(tmp_path):
    ф = tmp_path / "urls.txt"
    ф.write_text("https://x.test/a/\nhttps://x.test/b/\n# комментарий\n", encoding="utf-8")
    список, пояснение = инс.адреса(ф, 1)
    assert список == ["https://x.test/a/"] and "беру 1" in пояснение

    плохой = tmp_path / "bad.txt"
    плохой.write_text("http://x.test/a/\n", encoding="utf-8")
    список, пояснение = инс.адреса(плохой, 10)
    assert список == [] and "https://" in пояснение
