"""Черновик комментария: устойчивое имя, чтение своего текста, передача редактору.

Повод — отчёт готовящей стороны (Qwen) от 10 октября 2026. Он получал от
`prepare_comment` поля `state`, `chars`, `url`, `quality_problems` и
`next_action`, и этого не хватало на три вещи:

* **имени у работы не было.** Черновик лежал в хранилище по слагу, но наружу
  идентификатор не возвращался: сослаться на черновик было нечем, и отличить
  «создан» от «уже был» — тоже;
* **своего текста он прочитать не мог.** Подготовка возвращала длину, а тела не
  отдавал ни один инструмент: убедиться, что записалось именно то, что
  отправляли, можно было только публикацией — то есть необратимым действием;
* **передать работу было некуда.** Каноническая редакционная очередь роли
  `qwen` закрыта решением владельца (ей разрешены `prepare`, `posts-prepare`,
  `comment-prepare`), а никакого другого способа сообщить редактору о готовом
  черновике не существовало.

Отчёт был верен: это отсутствие механизма, а не отсутствие прав на существующий.
Здесь сторожится добавленный минимум и — отдельно — что разделение прав от него
не пострадало: готовит и передаёт одна сторона, решает и публикует другая.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.qwen import actors, comments, editorial  # noqa: E402

ТЕКСТ = ("У путешествия команды есть конкретная цель, и в этой завязке "
         "привлекает именно масштаб общего дела: за поиском клада интересно "
         "следить как за совместным приключением.")
ДРУГОЙ = ("Второй вариант того же наблюдения, записанный иначе и той же "
          "длины, чтобы проверка видела смену отпечатка текста.")


class Сайт:
    """Площадка без сети: проверяется хранилище черновиков, а не витрина."""
    site_id = "yummy-org"
    domain = "yummyani.org"
    adapter = "yummy"
    account = "yummyani-org"


@pytest.fixture()
def стенд(tmp_path, monkeypatch):
    s = Сайт()
    monkeypatch.setattr(comments, "_сайт", lambda site: s)
    monkeypatch.setattr(comments, "_каталог", lambda сайт: tmp_path)
    monkeypatch.setattr(comments, "_требует_семейство", lambda сайт: None)
    monkeypatch.setattr(comments, "способ", lambda сайт: "app")
    monkeypatch.setattr(comments, "_адрес_карточки",
                        lambda сайт, slug: f"https://{s.domain}/anime/{slug}")
    # Ограничение роли проверяется настоящим модулем: подменять его здесь
    # значило бы проверить форму вызова вместо права.
    monkeypatch.delenv(actors.СНЯТИЕ, raising=False)
    return tmp_path


def test_подготовка_даёт_устойчивое_имя(стенд):
    первая = comments.подготовить("yummyani.org", "van-pis", ТЕКСТ,
                                  author="qwen/канал/run-1")
    assert первая["draft_id"].startswith("cd-")
    assert первая["created"] is True and первая["unchanged"] is False
    вторая = comments.подготовить("yummyani.org", "van-pis", ТЕКСТ,
                                  author="qwen/канал/run-2")
    assert вторая["draft_id"] == первая["draft_id"], (
        "повторная подготовка той же карточки дала другое имя: "
        "ссылаться на черновик стало бы нечем")
    assert вторая["created"] is False and вторая["unchanged"] is True
    # Второго черновика не появилось.
    файл = json.loads((стенд / comments.ЧЕРНОВИКИ).read_text(encoding="utf-8"))
    assert list(файл["items"]) == ["van-pis"]


def test_имя_разное_у_разных_карточек(стенд):
    а = comments.ид_черновика("yummyani.org", "van-pis")
    б = comments.ид_черновика("yummyani.org", "naruto")
    assert а != б


def test_готовящая_сторона_читает_своё_тело(стенд):
    подготовка = comments.подготовить("yummyani.org", "van-pis", ТЕКСТ,
                                      author="qwen/канал/run-1")
    прочитано = comments.черновик("yummyani.org", slug="van-pis")
    assert прочитано["body"] == ТЕКСТ, "прочиталось не то, что записывали"
    assert прочитано["body_digest"] == подготовка["body_digest"]
    assert прочитано["chars"] == len(ТЕКСТ)
    assert прочитано["handoff"]["state"] == "drafted"
    # По идентификатору — тот же ответ: имя действительно работает как ручка.
    по_ид = comments.черновик("yummyani.org", draft_id=подготовка["draft_id"])
    assert по_ид["body"] == ТЕКСТ and по_ид["slug"] == "van-pis"


def test_чтения_нет_там_где_нет_черновика(стенд):
    with pytest.raises(comments.ОперацияОтклонена) as ош:
        comments.черновик("yummyani.org", slug="нет-такого")
    assert "нет в хранилище" in str(ош.value)


def test_передача_отмечается_и_не_повторяется(стенд):
    comments.подготовить("yummyani.org", "van-pis", ТЕКСТ,
                         author="qwen/канал/run-1")
    первая = comments.передать("yummyani.org", "van-pis",
                               author="qwen/канал/run-1", note="проверить факты")
    assert первая["already"] is False
    assert первая["handoff"]["state"] == "submitted"
    assert первая["handoff"]["submitted_by"] == "qwen/канал/run-1"
    вторая = comments.передать("yummyani.org", "van-pis",
                               author="qwen/канал/run-2")
    assert вторая["already"] is True, (
        "повторная передача создала вторую заявку на проверку: "
        "очередь редактора состояла бы из повторов")
    assert вторая["handoff"]["submitted_at"] == первая["handoff"]["submitted_at"]


def test_передача_попадает_в_перечень_проверяющего(стенд):
    comments.подготовить("yummyani.org", "van-pis", ТЕКСТ, author="qwen/к/run-1")
    comments.передать("yummyani.org", "van-pis", author="qwen/к/run-1")
    перечень = comments.ожидают_проверки(site="yummyani.org")
    assert перечень["count"] == 1
    строка = перечень["pending"][0]
    assert строка["slug"] == "van-pis"
    assert строка["draft_id"] == comments.ид_черновика("yummyani.org", "van-pis")
    assert строка["submitted_by"] == "qwen/к/run-1"


def test_неподготовленное_не_передаётся(стенд):
    with pytest.raises(comments.ОперацияОтклонена) as ош:
        comments.передать("yummyani.org", "van-pis", author="qwen/к/run-1")
    assert "передавать нечего" in str(ош.value)


def test_черновик_с_замечаниями_не_передаётся(стенд, monkeypatch):
    """Передавать текст, который сам инструмент признал негодным, нельзя."""
    monkeypatch.setattr(comments, "проверить_текст", lambda т: ["выдуманное впечатление"])
    comments.подготовить("yummyani.org", "van-pis", ТЕКСТ, author="qwen/к/run-1")
    with pytest.raises(comments.ОперацияОтклонена) as ош:
        comments.передать("yummyani.org", "van-pis", author="qwen/к/run-1")
    assert "замечаниями качества" in str(ош.value)


def test_смена_текста_отменяет_прежнюю_передачу(стенд):
    """Передан был ДРУГОЙ текст — значит проверять надо заново."""
    comments.подготовить("yummyani.org", "van-pis", ТЕКСТ, author="qwen/к/run-1")
    comments.передать("yummyani.org", "van-pis", author="qwen/к/run-1")
    заново = comments.подготовить("yummyani.org", "van-pis", ДРУГОЙ,
                                  author="qwen/к/run-2")
    assert заново["unchanged"] is False
    assert заново["handoff_state"] == "drafted", (
        "после смены текста черновик остался «на проверке»: редактор принял бы "
        "один текст, а под карточкой оказался бы другой")


def test_решение_принадлежит_проверяющей_стороне(стенд):
    """Главное свойство разделения прав: Qwen не ставит решение сам."""
    comments.подготовить("yummyani.org", "van-pis", ТЕКСТ, author="qwen/к/run-1")
    comments.передать("yummyani.org", "van-pis", author="qwen/к/run-1")
    with pytest.raises(actors.ОперацияНеРазрешена) as ош:
        comments.решение("yummyani.org", "van-pis", author="qwen/к/run-1",
                         verdict="accepted")
    assert "comment-review" in str(ош.value)
    # Публиковать ему тоже нельзя — это не менялось.
    with pytest.raises(actors.ОперацияНеРазрешена):
        comments.опубликовать("yummyani.org", "van-pis", author="qwen/к/run-1")


def test_редактор_принимает_и_это_видно_готовящей_стороне(стенд):
    comments.подготовить("yummyani.org", "van-pis", ТЕКСТ, author="qwen/к/run-1")
    comments.передать("yummyani.org", "van-pis", author="qwen/к/run-1")
    итог = comments.решение("yummyani.org", "van-pis",
                            author="editor/claude/run-7", verdict="accepted",
                            note="факты подтверждены пакетом проверяющего")
    assert итог["handoff"]["state"] == "accepted"
    assert итог["handoff"]["reviewed_by"] == "editor/claude/run-7"
    видит = comments.черновик("yummyani.org", slug="van-pis")
    assert видит["handoff"]["state"] == "accepted"
    assert видит["handoff"]["review_note"].startswith("факты подтверждены")
    # Принятый черновик уходит из очереди проверяющего.
    assert comments.ожидают_проверки(site="yummyani.org")["count"] == 0


def test_отклонение_называет_причину_и_не_публикует(стенд):
    comments.подготовить("yummyani.org", "van-pis", ТЕКСТ, author="qwen/к/run-1")
    comments.передать("yummyani.org", "van-pis", author="qwen/к/run-1")
    итог = comments.решение("yummyani.org", "van-pis",
                            author="editor/claude/run-7", verdict="rejected",
                            note="нет источника на дату выхода")
    assert итог["handoff"]["state"] == "rejected"
    assert "не делается" in итог["next_action"]


def test_решение_по_непереданному_не_записывается(стенд):
    comments.подготовить("yummyani.org", "van-pis", ТЕКСТ, author="qwen/к/run-1")
    with pytest.raises(comments.ОперацияОтклонена) as ош:
        comments.решение("yummyani.org", "van-pis", author="editor/claude/run-7",
                         verdict="accepted")
    assert "не передавался" in str(ош.value)


def test_публикация_закрывает_черновик(стенд):
    """Иначе готовящая сторона видела бы «на проверке» у того, что уже вышло."""
    comments.подготовить("yummyani.org", "van-pis", ТЕКСТ, author="qwen/к/run-1")
    comments.передать("yummyani.org", "van-pis", author="qwen/к/run-1")
    comments.решение("yummyani.org", "van-pis", author="editor/claude/run-7",
                     verdict="accepted")
    comments.отметить_опубликованным(Сайт(), "van-pis", comment_id="cmv-1",
                                     author="editor/claude/run-7")
    видит = comments.черновик("yummyani.org", slug="van-pis")
    assert видит["handoff"]["state"] == "published"
    assert видит["handoff"]["comment_id"] == "cmv-1"


def test_решение_без_имени_проверяющего_не_записывается(стенд):
    """«Принято неизвестно кем» записью о решении не является.

    Поймано на живом проходе 10 октября: редактор отклонил черновик
    `cd-cc880b98d158` с подробной причиной, а `reviewed_by` остался пустым —
    застава роли пустое имя пропускает намеренно (роль без объявленных
    ограничений не трогается), и спросить о решении было бы некого.
    """
    comments.подготовить("yummyani.org", "van-pis", ТЕКСТ, author="qwen/к/run-1")
    comments.передать("yummyani.org", "van-pis", author="qwen/к/run-1")
    for пусто in ("", "   ", None):
        with pytest.raises(comments.ОперацияОтклонена) as ош:
            comments.решение("yummyani.org", "van-pis", author=пусто,
                             verdict="accepted")
        assert "именем проверяющего" in str(ош.value)
    # Состояние не изменилось: отказ наступил до записи.
    assert comments.черновик("yummyani.org", slug="van-pis")["handoff"]["state"] \
        == "submitted"


def test_передача_без_имени_не_записывается(стенд):
    comments.подготовить("yummyani.org", "van-pis", ТЕКСТ, author="qwen/к/run-1")
    with pytest.raises(comments.ОперацияОтклонена) as ош:
        comments.передать("yummyani.org", "van-pis", author="")
    assert "только с именем" in str(ош.value)
    assert comments.черновик("yummyani.org", slug="van-pis")["handoff"]["state"] \
        == "drafted"


def test_черновик_прежнего_кода_получает_имя(стенд):
    """Записи без `draft_id` в хранилище есть, и они обязаны получить имя.

    Поймано на живом проходе 10 октября: черновик «Ван-Пис», записанный
    прежней версией подготовки, при передаче дал `draft_id: null` — ту самую
    безымянность, ради устранения которой механизм и делался. Достраивание
    однозначно: имя вычисляется из домена и слага.
    """
    (стенд / comments.ЧЕРНОВИКИ).write_text(json.dumps({
        "site": "yummyani.org",
        "items": {"van-pis": {"slug": "van-pis", "body": ТЕКСТ,
                              "author": "Редакция",
                              "prepared_by": "qwen/канал/Редакция",
                              "prepared_at": "2026-10-10T09:34:00Z",
                              "body_digest": editorial.отпечаток(ТЕКСТ),
                              "quality_problems": []}}},
        ensure_ascii=False), encoding="utf-8")
    ожидаемое = comments.ид_черновика("yummyani.org", "van-pis")
    assert comments.черновик("yummyani.org", slug="van-pis")["draft_id"] == ожидаемое
    передача = comments.передать("yummyani.org", "van-pis", author="qwen/к/run-1")
    assert передача["draft_id"] == ожидаемое, "передача вернула безымянный черновик"
    решение = comments.решение("yummyani.org", "van-pis",
                               author="editor/claude/run-7", verdict="accepted")
    assert решение["draft_id"] == ожидаемое
    # Имя записано в хранилище, а не вычисляется заново каждым читателем.
    файл = json.loads((стенд / comments.ЧЕРНОВИКИ).read_text(encoding="utf-8"))
    assert файл["items"]["van-pis"]["draft_id"] == ожидаемое
    строки = [json.loads(с) for с in
              (стенд / editorial.ИСТОРИЯ).read_text(encoding="utf-8").splitlines() if с]
    assert all(з.get("draft_id") == ожидаемое for з in строки), строки


def test_журнал_хранит_оба_события(стенд):
    comments.подготовить("yummyani.org", "van-pis", ТЕКСТ, author="qwen/к/run-1")
    comments.передать("yummyani.org", "van-pis", author="qwen/к/run-1")
    comments.решение("yummyani.org", "van-pis", author="editor/claude/run-7",
                     verdict="accepted")
    строки = [json.loads(с) for с in
              (стенд / editorial.ИСТОРИЯ).read_text(encoding="utf-8").splitlines() if с]
    операции = [з.get("op") for з in строки]
    assert "submit-comment" in операции and "review-comment" in операции
