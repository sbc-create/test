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


# --- поправки 26.10, пришедшие от линии SEO и проверенные измерением --------

def test_опыт_в_фазе_наблюдения_останавливает_отправку():
    """Отправка меняет обход, а опыт измеряет разницу выборки и контроля.

    По lords-05 в config/experiments.json два опыта в фазе canary — значит
    инструмент обязан отказать, пока решение не названо явно.
    """
    идёт, какой = инс.опыт_идёт("lords-05")
    assert идёт, "опыты lords-05 в реестре перестали находиться"
    assert "exp-lords" in какой


def test_витрина_без_опытов_не_блокируется():
    идёт, какой = инс.опыт_идёт("lords-02")
    assert not идёт and "нет" in какой


def test_пауза_сказанная_словами_инструменту_не_видна():
    """zonafilm.cc (zona-02): паузу до 28.10 назвали в переписке, в реестре её нет.

    Проверка закрепляет вывод, а не пропуск: пока записи нет, инструмент о
    паузе знать не может, и держать такое ограничение в сообщении нельзя.
    Как только запись появится — проверка упадёт, и это правильный сигнал
    поправить документ и сообщение.
    """
    идёт, _ = инс.опыт_идёт("zona-02")
    assert not идёт, ("по zona-02 появилась запись опыта — значит пауза внесена в "
                      "реестр: обнови docs/NETWORK_STATE_20261026.md и сними это ожидание")


def test_источник_режима_не_найден_это_не_закрыто(tmp_path):
    """Третий исход называется отдельно: у Yummy режим живёт в другом рантайме."""
    открыта, почему = инс.индексация_открыта({"domain": "yummyani.site"}, tmp_path / "нет")
    assert not открыта
    assert "ИСТОЧНИК РЕЖИМА НЕ НАЙДЕН" in почему
    assert "закрытым домен этим не объявляется" in почему


def test_готовность_читает_манифест_из_названного_дерева():
    """Артефакты из дерева службы, а конфигурация из моей ветви — это смесь.

    Измерено 26.10: animedia.icu есть в манифесте линии SEO и отсутствует в
    моём, поэтому инструмент обязан читать манифест из названного дерева и
    печатать, из какого именно.
    """
    сп = importlib.util.spec_from_file_location(
        "measurement_readiness", КОРЕНЬ / "automation" / "local" / "measurement-readiness.py")
    гот = importlib.util.module_from_spec(сп)
    сп.loader.exec_module(гот)
    дерево = pathlib.Path("/home/claude/wt-portable-site-cell-01")
    if not (дерево / "factory" / "topvisor" / "manifest.py").is_file():
        pytest.skip("дерева службы нет в этой машине")
    проект, ош = гот._проект_topvisor("animedia.icu", дерево)
    assert ош == "", ош
    assert проект is not None, "animedia.icu обязан находиться в манифесте дерева службы"
    свой, _ = гот._проект_topvisor("animedia.icu", КОРЕНЬ)
    assert свой is None, "в моей ветви проекта animedia.icu нет — на этом и стоит поправка"


# --- заморозка очереди: источник нашёлся в своей же ветке -------------------
#
# Линия SEO отказалась вносить паузу zonafilm.cc в config/experiments.json и
# была права: запись опыта потребовала бы выдуманных гипотезы, метрики и доли
# страниц. Источник оказался ближе — `config/domain-queues/<домен>.json`, где
# у задач стоит `blocked_by` с датой оценки. Проверки ниже закрепляют чтение
# ИМЕННО этого источника и даты, а не текста сообщения.

import datetime as _dt


def test_заморозка_читается_из_очереди_домена():
    """Дата фиксирована: иначе проверка сама развалится после 28.10."""
    заморожен, чем = инс.заморозка_очереди("zonafilm.cc", _dt.date(2026, 10, 26))
    assert заморожен, "заморозка zonafilm.cc перестала находиться в очереди"
    assert "2026-10-28" in чем and "Q-zonafilm.cc" in чем


def test_после_даты_оценки_заморозка_отпускает():
    заморожен, чем = инс.заморозка_очереди("zonafilm.cc", _dt.date(2026, 11, 1))
    assert not заморожен, чем


def test_домен_без_файла_очереди_не_заморожен():
    заморожен, чем = инс.заморозка_очереди("нет-такого-домена.test")
    assert not заморожен and "нет" in чем


def test_нечитаемая_очередь_считается_заморозкой(tmp_path, monkeypatch):
    """Проверить нечем — значит нельзя; иначе битый файл открывал бы отправку."""
    monkeypatch.setattr(инс, "ОЧЕРЕДИ", tmp_path)
    (tmp_path / "x.test.json").write_text("{битый", encoding="utf-8")
    заморожен, чем = инс.заморозка_очереди("x.test")
    assert заморожен and "считаю замороженным" in чем


def test_заморозка_без_даты_тоже_держит(tmp_path, monkeypatch):
    import json as _json

    monkeypatch.setattr(инс, "ОЧЕРЕДИ", tmp_path)
    (tmp_path / "y.test.json").write_text(_json.dumps({
        "domain": "y.test",
        "tasks": [{"id": "Q-1", "blocked_by": "НЕ ПРАВИТЬ до решения владельца"}],
    }, ensure_ascii=False), encoding="utf-8")
    заморожен, чем = инс.заморозка_очереди("y.test")
    assert заморожен and "без даты" in чем


def test_локальные_проверки_идут_раньше_сетевой():
    """Иначе отказ по заморозке не виден: сетевая проверка падает по таймауту.

    Проверяется порядок в коде, потому что именно он и был неверным: сначала
    стояла проверка файла ключа, и по zonafilm.cc вместо заморозки печатался
    таймаут.
    """
    текст = (КОРЕНЬ / "automation" / "local" / "indexnow-submit.py").read_text(encoding="utf-8")
    где_заморозка = текст.index("заморозка_очереди(а.domain)")
    где_опыты = текст.index("опыт_идёт(я.get(")
    где_файл = текст.index("файл_ключа_отдаётся(а.domain")
    assert где_заморозка < где_файл and где_опыты < где_файл
