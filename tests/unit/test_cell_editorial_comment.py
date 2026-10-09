"""Редакционный комментарий в хранилище сообщества ячейки.

Что именно проверяется и почему именно это.

Хранилище сообщества — не наш файл. В нём лежат сообщения ПОСЕТИТЕЛЕЙ, их
голоса и реакции, и правило владения данными (`docs/RUNTIME_DATA_OWNERSHIP.md`)
разрешает выпуску, сборке, установщику и откату только чтение. Решение
допустить одну редакционную запись записано в `knowledge/DECISIONS.md`
(2026-10-10) и ограничено ровно этим: ОДНА добавленная запись в ОДНОМ файле,
автор «Редакция», ни одно чужое сообщение не изменено и не потеряно.

Отсюда состав проверок:

* подготовка отвергает всё, что не является одной редакционной записью:
  пустой текст, чужую подпись, перебор длины, заявку без причины, снятие без
  идентификатора и публикацию с подставленным идентификатором;
* digest считается по канонической записи и не зависит от порядка ключей —
  иначе повтор той же работы заводил бы вторую операцию в очереди;
* исполнитель отказывает, если digest подготовленного не совпал с заявкой:
  заявка доказывает содержимое, а не называет путь;
* привилегированная запись идёт МОДУЛЕМ ЯЧЕЙКИ и сохраняет сообщения
  посетителей байт-в-байт, а новая запись видна (`approved`);
* снятие прячет СВОЮ запись и отказывается трогать чужую;
* защита данных разрешает операции `comment_publish` ровно один путь и
  отказывает ей же по соседнему файлу того же вида.

Проверки идут на СТЕНДЕ: временный каталог с копией модуля сообщества из
рабочей копии ячейки и подложным реестром. Копия, а не выдумка: формат файла
знает только тот модуль, который его пишет.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil

import pytest

from factory.cell import comment_store, privileged, protected

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
МОДУЛЬ_ЯЧЕЙКИ = КОРЕНЬ / "var" / "site-repos" / "an1mego-site" / "src" / "community.py"


@pytest.fixture()
def стенд(tmp_path, monkeypatch):
    """Ячейка со своим выпуском, хранилищем и сообщением посетителя."""
    if not МОДУЛЬ_ЯЧЕЙКИ.is_file():
        pytest.skip("рабочей копии ячейки с модулем сообщества нет")
    корень = tmp_path / "srv" / "cell-site"
    выпуск = корень / "app"
    (выпуск / "src").mkdir(parents=True)
    (выпуск / "config").mkdir(parents=True)
    shutil.copy2(МОДУЛЬ_ЯЧЕЙКИ, выпуск / "src" / "community.py")
    данные = корень / "data"
    (данные / "site-data").mkdir(parents=True)
    (выпуск / "config" / "site.json").write_text(json.dumps({
        "site_id": "cell-01",
        "environment": {"CELL_COMMUNITY_STORE": "<data>/site-data/community.json"},
    }, ensure_ascii=False), encoding="utf-8")
    (данные / "cell-01-details.json").write_text(json.dumps({
        "details": {"kartochka": {"id": "t-900"}}
    }, ensure_ascii=False), encoding="utf-8")
    # Сообщение посетителя — то, что обязано уцелеть.
    гость = {
        "id": "visitor0001", "name": "Гость", "text": "первым написал посетитель",
        "created_at": "2026-10-01T10:00:00Z", "author_key": "v-1",
        "status": "approved", "parent_id": "",
    }
    (данные / "site-data" / "community.json").write_text(json.dumps({
        "format": 3, "site": "cell-01",
        "titles": {"t-900": {"slug": "kartochka", "comments": [гость]}},
    }, ensure_ascii=False), encoding="utf-8")

    площадка = privileged.Площадка(
        site_id="cell-01", account=os.environ.get("USER") or "claude",
        root=корень, app=выпуск, data=данные,
        unit="nova-cell.service", previous_unit=None, port=9999)
    monkeypatch.setattr(privileged.Площадка, "из_реестра",
                        classmethod(lambda cls, site_id, **_: площадка))
    monkeypatch.setattr(privileged, "_нужен_root", lambda: None)
    monkeypatch.setenv("SITE_COMMENT_STAGING", str(tmp_path / "staging"))
    monkeypatch.setattr(comment_store, "БАЗА", tmp_path / "staging")
    monkeypatch.setattr(privileged, "КОРЕНЬ_СНИМКОВ_СООБЩЕСТВА",
                        tmp_path / "snapshots")
    return {"площадка": площадка, "store": данные / "site-data" / "community.json",
            "гость": гость, "данные": данные}


# --- подготовка ------------------------------------------------------------


def test_подготовка_требует_одну_редакционную_запись(tmp_path):
    общее = {"actor": "claude", "reason": "проба"}
    with pytest.raises(comment_store.StoreRejected):
        comment_store.собрать("c-1", slug="k", текст="   ", **общее)
    with pytest.raises(comment_store.StoreRejected):
        comment_store.собрать("c-1", slug="k", текст="x" * 1201, **общее)
    with pytest.raises(comment_store.StoreRejected):
        comment_store.собрать("c-1", slug="", текст="текст", **общее)
    with pytest.raises(comment_store.StoreRejected):
        comment_store.собрать("c-1", slug="k", текст="текст", actor="claude", reason=" ")
    # Публикация НЕ принимает идентификатор: его выдаёт модуль ячейки, и
    # принятый извне он означал бы правку существующей записи.
    with pytest.raises(comment_store.StoreRejected):
        comment_store.собрать("c-1", slug="k", текст="текст", comment_id="abc123",
                              **общее)
    # Снятие, наоборот, без идентификатора бессмысленно.
    with pytest.raises(comment_store.StoreRejected):
        comment_store.собрать("c-1", slug="k", действие="retract", **общее)


def test_подпись_всегда_редакция():
    запись = comment_store.собрать("c-1", slug="k", текст="мысль",
                                   actor="claude", reason="проба")
    assert запись["author"] == "Редакция"
    # Подставить имя посетителя нечем: поля для подписи в заявке нет вовсе.
    assert "name" not in запись


def test_digest_не_зависит_от_порядка_ключей():
    запись = comment_store.собрать("c-1", slug="k", текст="мысль",
                                   actor="claude", reason="проба")
    перемешанная = dict(reversed(list(запись.items())))
    assert comment_store.отпечаток(запись) == comment_store.отпечаток(перемешанная)


def test_чужое_подготовленное_не_применяется(tmp_path):
    comment_store.подготовить("c-1", slug="k", текст_комментария="мысль",
                              actor="claude", reason="проба", база=tmp_path)
    with pytest.raises(comment_store.StoreRejected):
        comment_store.прочитать_подготовленное("c-2", база=tmp_path)


# --- привилегированная запись ---------------------------------------------


def _содержимое(**поля):
    основа = {"schema_version": 1, "site_id": "cell-01", "slug": "kartochka",
              "action": "publish", "comment_id": "", "author": "Редакция",
              "text": "В первой серии город показан макетом, и это видно по швам.",
              "actor": "claude", "reason": "проба", "sources": []}
    основа.update(поля)
    return основа


def test_сухой_прогон_не_касается_хранилища(стенд):
    было = стенд["store"].read_bytes()
    итог = privileged.опубликовать_комментарий("cell-01", _содержимое(),
                                               dry_run=True)
    assert итог["dry_run"] is True
    assert итог["topic"] == "t-900"
    assert стенд["store"].read_bytes() == было


def test_запись_добавляется_и_чужое_уцелело(стенд):
    итог = privileged.опубликовать_комментарий("cell-01", _содержимое(),
                                               dry_run=False)
    assert итог["dry_run"] is False
    данные = json.loads(стенд["store"].read_text(encoding="utf-8"))
    записи = данные["titles"]["t-900"]["comments"]
    assert len(записи) == 2
    гость = [з for з in записи if з["id"] == стенд["гость"]["id"]]
    assert гость == [стенд["гость"]], "сообщение посетителя изменилось"
    наша = [з for з in записи if з["id"] == итог["comment_id"]][0]
    assert наша["name"] == "Редакция"
    assert наша["status"] == "approved", "запись на модерации на странице не видна"
    # Ключ автора лежит в хранилище в том виде, в каком его считает модуль:
    # `_посетитель` — хеш с солью витрины, а не переданная строка. Проверяется
    # именно соответствие постоянному редакционному ключу: по нему операция
    # снятия и отличает свою запись от чужой.
    import importlib.util
    спец = importlib.util.spec_from_file_location(
        "cell_community_test", стенд["площадка"].app / "src" / "community.py")
    модуль = importlib.util.module_from_spec(спец)
    import sys as _sys
    _sys.modules["cell_community_test"] = модуль
    спец.loader.exec_module(модуль)
    assert наша["author_key"] == модуль._посетитель("editorial:cell-01")
    # Снимок ДО записи сохранён, и в нём ещё нет нашей записи.
    снимок = json.loads(pathlib.Path(итог["snapshot"]).read_text(encoding="utf-8"))
    assert [з["id"] for з in снимок["titles"]["t-900"]["comments"]] == \
        [стенд["гость"]["id"]]


def test_повтор_того_же_текста_отвергает_модуль(стенд):
    privileged.опубликовать_комментарий("cell-01", _содержимое(), dry_run=False)
    with pytest.raises(privileged.PrivilegedRefused) as ош:
        privileged.опубликовать_комментарий("cell-01", _содержимое(), dry_run=False)
    assert "уже отправлено" in str(ош.value) or "через" in str(ош.value)


def test_чужая_подпись_не_публикуется(стенд):
    with pytest.raises(privileged.PrivilegedRefused):
        privileged.опубликовать_комментарий(
            "cell-01", _содержимое(author="Зритель Алексей"), dry_run=False)


def test_неизвестная_карточка_отказ(стенд):
    with pytest.raises(privileged.PrivilegedRefused) as ош:
        privileged.опубликовать_комментарий(
            "cell-01", _содержимое(slug="takoy-kartochki-net"), dry_run=False)
    assert "подробностях каталога" in str(ош.value)


def test_подготовлено_для_другого_сайта(стенд):
    with pytest.raises(privileged.PrivilegedRefused):
        privileged.опубликовать_комментарий(
            "cell-01", _содержимое(site_id="cell-02"), dry_run=False)


def test_снятие_прячет_свою_запись(стенд):
    опубликовано = privileged.опубликовать_комментарий(
        "cell-01", _содержимое(), dry_run=False)
    итог = privileged.опубликовать_комментарий(
        "cell-01", _содержимое(action="retract", text="",
                               comment_id=опубликовано["comment_id"]),
        dry_run=False)
    assert итог["action"] == "retract"
    записи = json.loads(стенд["store"].read_text(encoding="utf-8"))["titles"]["t-900"]["comments"]
    наша = [з for з in записи if з["id"] == опубликовано["comment_id"]][0]
    assert наша["status"] == "rejected"
    # Сообщение посетителя снятием не задето.
    assert [з for з in записи if з["id"] == стенд["гость"]["id"]] == [стенд["гость"]]


def test_чужую_запись_снять_нельзя(стенд):
    with pytest.raises(privileged.PrivilegedRefused) as ош:
        privileged.опубликовать_комментарий(
            "cell-01", _содержимое(action="retract", text="",
                                   comment_id=стенд["гость"]["id"]),
            dry_run=False)
    assert "не редакцией" in str(ош.value)
    записи = json.loads(стенд["store"].read_text(encoding="utf-8"))["titles"]["t-900"]["comments"]
    assert записи == [стенд["гость"]]


def test_хранилища_нет_значит_отказ(стенд):
    стенд["store"].unlink()
    with pytest.raises(privileged.PrivilegedRefused) as ош:
        privileged.опубликовать_комментарий("cell-01", _содержимое(),
                                            dry_run=False)
    assert "утрату данных" in str(ош.value)


def test_путь_хранилища_только_внутри_данных(стенд, monkeypatch):
    (стенд["площадка"].app / "config" / "site.json").write_text(json.dumps({
        "site_id": "cell-01",
        "environment": {"CELL_COMMUNITY_STORE": "/etc/passwd.json"},
    }, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(privileged.PrivilegedRefused) as ош:
        privileged.путь_сообщества("cell-01")
    assert "вне каталога данных" in str(ош.value)


# --- защита данных ---------------------------------------------------------


def test_защита_разрешает_только_сам_файл(стенд, monkeypatch):
    monkeypatch.setattr(protected, "_контрактные",
                        lambda site_id: [стенд["данные"] / "site-data"])
    хранилище, _ = privileged.путь_сообщества("cell-01")

    разрешено = protected.проверить_запись(
        "cell-01", "cell.example", хранилище, операция="comment_publish")
    assert разрешено["allowed"] is True

    # Соседний файл того же вида операции не принадлежит.
    for чужой in (стенд["данные"] / "site-data" / "cell-01-views.json",
                  стенд["данные"] / "site-data"):
        with pytest.raises(protected.ЗащитаДанных):
            protected.проверить_запись("cell-01", "cell.example", чужой,
                                       операция="comment_publish")

    # И само хранилище закрыто для тех, кто обязан только читать.
    for операция in ("release", "install", "rollback", "deliver"):
        with pytest.raises(protected.ЗащитаДанных):
            protected.проверить_запись("cell-01", "cell.example", хранилище,
                                       операция=операция)


def test_читатель_вида_объявлен():
    # Выпуск, потерявший модуль сообщества, перестаёт понимать формат файла,
    # который остаётся в хранилище.
    assert protected.ЧИТАТЕЛИ["community"] == ("src/community.py",)
    assert "community" not in protected.ВЛАДЕЛЬЦЫ_ВИДОВ, (
        "вид целиком не принадлежит ни одной операции фабрики: его пишет витрина")
