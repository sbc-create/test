"""ДОГОВОР ИЗМЕНЁН 24.10 решением владельца: рецензия материалов обязательна,
её выполняет отдельный проверяющий, допускающий вердикт требует названных
проверок и записанных источников, а публикация без принятой рецензии
отклоняется. Проверки ниже приведены к новому договору, а не ослаблены:
прежние вызовы с `accepted` без `checks` теперь отклоняются намеренно, и на
эти отказы добавлены отдельные проверки в конце файла.

Содержательная проверка материала: запись о прочтении, которую нельзя подделать.

Повод — разбор цепочки 2026-10-20. В журналах хранилищ 1 115 публикаций и ни
одной записи о том, что текст кто-то прочитал: было только `state: verified` от
машинных ворот, которые сами объявляют, что осмысленность текста и выдуманный
сюжет не ловят. Отличить прочитанный материал от непрочитанного было нечем.

Главное свойство операции — отзыв НЕЛЬЗЯ записать, не имея на руках того самого
текста: проверяющий передаёт отпечаток прочитанного, и он сверяется с
черновиком. Поэтому здесь проверяется не «функция пишет запись», а четыре вида
подмены:

* отзыв о ДРУГОЙ редакции за отзыв о текущей — отказ по отпечатку;
* отзыв без черновика — отказ, а не пустой успех;
* неизвестный вердикт за вердикт — отказ с перечнем допустимых;
* устаревший отзыв за свежий в записи публикации — помечается `устарел`, а не
  выдаётся за проверку нового текста.

И отдельно: отсутствие отзыва в журнале публикации обязано читаться как
«проверки не было», а не как «неизвестно».
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
if str(КОРЕНЬ) not in sys.path:
    sys.path.insert(0, str(КОРЕНЬ))

_с = importlib.util.spec_from_file_location(
    "qwen_editorial_review", КОРЕНЬ / "factory/qwen/editorial.py")
ED = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ED)

ТЕЛО = ("Подробное описание тайтла для проверки, в котором достаточно знаков, "
        "чтобы ворота качества не ругались на длину текста материала.")


class _Сайт:
    domain = "x.site"
    adapter = "editorial"
    handover_state = "released"
    handover_reason = ""


@pytest.fixture()
def хранилище(tmp_path, monkeypatch):
    """Каталог черновиков с одним подготовленным материалом."""
    monkeypatch.setattr(ED, "_сайт", lambda site, **кв: _Сайт())
    monkeypatch.setattr(ED, "_каталог", lambda s: tmp_path)
    отп = ED.отпечаток(ТЕЛО)
    (tmp_path / ED.ЧЕРНОВИКИ).write_text(json.dumps({
        "site": "x.site",
        "items": {"slug-a": {"slug": "slug-a", "body": ТЕЛО,
                             "body_digest": отп, "author": "qwen",
                             "state": "verified", "quality_problems": [],
                             # Источники появились в фикстуре 24.10: по
                             # заданию владельца допускающий вердикт без них
                             # отклоняется — подтверждать «факты
                             # подтверждены источниками» было бы нечем.
                             "sources": ["https://shikimori.io/animes/1"]}},
    }, ensure_ascii=False), encoding="utf-8")
    return tmp_path, отп


# --- запись отзыва ------------------------------------------------------------

def test_отзыв_записывается_и_попадает_в_журнал(хранилище):
    каталог, отп = хранилище
    итог = ED.рецензировать("x.site", "slug-a", reviewer="claude/review-01",
                            verdict="accepted", body_digest=отп,
                            checks={к: True for к in ED.ПРОВЕРКИ_РЕЦЕНЗИИ},
                            notes=["факты сверены с каталогом"])
    assert итог["review"]["verdict"] == "accepted"
    assert итог["review"]["reviewer"] == "claude/review-01"
    журнал = [json.loads(с) for с
              in (каталог / ED.ИСТОРИЯ).read_text(encoding="utf-8").splitlines()
              if с.strip()]
    отзывы = [з for з in журнал if з.get("op") == "review"]
    assert len(отзывы) == 1
    assert отзывы[0]["author"] == "claude/review-01"
    assert отзывы[0]["body_digest"] == отп
    assert отзывы[0]["notes"] == ["факты сверены с каталогом"]


def test_отзыв_ложится_в_черновик(хранилище):
    каталог, отп = хранилище
    ED.рецензировать("x.site", "slug-a", reviewer="claude/review-01",
                     verdict="accepted_with_notes", body_digest=отп,
                     checks={к: True for к in ED.ПРОВЕРКИ_РЕЦЕНЗИИ},
                     notes=["второй абзац слабый"])
    черновики = json.loads((каталог / ED.ЧЕРНОВИКИ).read_text(encoding="utf-8"))
    о = черновики["items"]["slug-a"]["review"]
    assert о["verdict"] == "accepted_with_notes"
    assert о["notes"] == ["второй абзац слабый"]


# --- четыре вида подмены ------------------------------------------------------

def test_отзыв_о_другой_редакции_отклоняется(хранилище):
    """Главный контроль: без прочитанного текста отзыв не записать."""
    with pytest.raises(ED.ОперацияОтклонена) as ош:
        ED.рецензировать("x.site", "slug-a", reviewer="claude/review-01",
                         verdict="accepted",
                         body_digest=ED.отпечаток("совсем другой текст"))
    assert "не совпал" in str(ош.value)


def test_отзыв_без_черновика_отклоняется(хранилище):
    _, отп = хранилище
    with pytest.raises(ED.ОперацияОтклонена) as ош:
        ED.рецензировать("x.site", "нет-такого", reviewer="claude/review-01",
                         verdict="accepted", body_digest=отп)
    assert "рецензировать нечего" in str(ош.value)


def test_неизвестный_вердикт_отклоняется(хранилище):
    _, отп = хранилище
    with pytest.raises(ED.ОперацияОтклонена) as ош:
        ED.рецензировать("x.site", "slug-a", reviewer="claude/review-01",
                         verdict="ну-ладно", body_digest=отп)
    assert "неизвестен" in str(ош.value)
    for допустимый in ("accepted", "accepted_with_notes", "rejected"):
        assert допустимый in str(ош.value)


def test_отказ_не_оставляет_следа(хранилище):
    """Отклонённая операция не должна выглядеть выполненной."""
    каталог, _ = хранилище
    with pytest.raises(ED.ОперацияОтклонена):
        ED.рецензировать("x.site", "slug-a", reviewer="claude/review-01",
                         verdict="accepted", body_digest="чужой")
    assert not (каталог / ED.ИСТОРИЯ).exists() or not [
        з for з in (каталог / ED.ИСТОРИЯ).read_text(
            encoding="utf-8").splitlines() if з.strip()]


# --- как отзыв попадает в запись публикации -----------------------------------

def test_без_отзыва_это_none_а_не_неизвестно():
    assert ED._отзыв_для_журнала({"body_digest": "a"}, "a") is None
    assert ED._отзыв_для_журнала(None, "a") is None
    assert ED._отзыв_для_журнала({}, "a") is None


def test_свежий_отзыв_попадает_в_запись_публикации():
    черновик = {"body_digest": "a",
                "review": {"reviewer": "claude/r", "verdict": "accepted",
                           "body_digest": "a", "at": "2026-10-20T08:00:00Z",
                           "notes": []}}
    о = ED._отзыв_для_журнала(черновик, "a")
    assert о["verdict"] == "accepted" and о["reviewer"] == "claude/r"
    assert "state" not in о


def test_устаревший_отзыв_помечается_а_не_выдаётся_за_проверку():
    """Отрицательный контроль: отзыв о прежнем тексте — не проверка нового."""
    черновик = {"body_digest": "b",
                "review": {"reviewer": "claude/r", "verdict": "accepted",
                           "body_digest": "a", "at": "2026-10-19T08:00:00Z"}}
    о = ED._отзыв_для_журнала(черновик, "b")
    assert о["state"] == "устарел"
    assert о["reviewed_digest"] == "a"
    assert "verdict" not in о


def test_перечень_вердиктов_объявлен():
    assert set(ED.ВЕРДИКТЫ) == {"accepted", "accepted_with_notes",
                                "rejected"}


# --- новый договор: без источников и без проверок допуска нет ----------------

def test_допускающий_вердикт_без_источников_отклоняется(хранилище):
    """«Факты подтверждены источниками» нечем подтвердить при пустых sources."""
    tmp_path, отп = хранилище
    данные = json.loads((tmp_path / ED.ЧЕРНОВИКИ).read_text(encoding="utf-8"))
    данные["items"]["slug-a"]["sources"] = []
    (tmp_path / ED.ЧЕРНОВИКИ).write_text(json.dumps(данные, ensure_ascii=False),
                                         encoding="utf-8")
    with pytest.raises(ED.ОперацияОтклонена) as ош:
        ED.рецензировать("x.site", "slug-a", reviewer="claude/review-01",
                         verdict="accepted", body_digest=отп,
                         checks={к: True for к in ED.ПРОВЕРКИ_РЕЦЕНЗИИ})
    assert "ни одного источника" in str(ош.value)


def test_допускающий_вердикт_без_проверок_отклоняется(хранилище):
    """Отзыв без названных проверок — подпись, а не проверка."""
    _, отп = хранилище
    with pytest.raises(ED.ОперацияОтклонена) as ош:
        ED.рецензировать("x.site", "slug-a", reviewer="claude/review-01",
                         verdict="accepted", body_digest=отп)
    assert "требует всех проверок" in str(ош.value)


def test_отказ_проверок_не_требует(хранилище):
    """У отказа причина в примечаниях: требовать перечень пройденного там,
    где что-то не прошло, значило бы требовать противоречия."""
    _, отп = хранилище
    итог = ED.рецензировать("x.site", "slug-a", reviewer="claude/review-01",
                            verdict="rejected", body_digest=отп,
                            notes=["имя персонажа не найдено в источнике"])
    assert итог["review"]["verdict"] == "rejected"


def test_роли_qwen_рецензия_закрыта_раньше_сравнения_личностей(хранилище):
    """Автор фикстуры — `qwen`, и отказ приходит РАНЬШЕ сравнения личностей.

    Порядок намеренный и важнее, чем кажется: право роли проверяется до того,
    как операция посмотрит, кто автор черновика. Поэтому роль, которой
    рецензия не разрешена, получает отказ о ПРАВЕ, а не о совпадении имён —
    иначе причина выглядела бы устранимой переименованием.
    """
    _, отп = хранилище
    with pytest.raises(ED.actors.ОперацияНеРазрешена) as ош:
        ED.рецензировать("x.site", "slug-a", reviewer="qwen",
                         verdict="accepted", body_digest=отп,
                         checks={к: True for к in ED.ПРОВЕРКИ_РЕЦЕНЗИИ})
    assert "review-material" in str(ош.value)


def test_автор_не_одобряет_свою_работу_при_разрешённой_роли(хранилище):
    """Совпадение личностей ловится у роли, которой рецензия РАЗРЕШЕНА."""
    tmp_path, отп = хранилище
    данные = json.loads((tmp_path / ED.ЧЕРНОВИКИ).read_text(encoding="utf-8"))
    данные["items"]["slug-a"]["author"] = "claude/review-01"
    (tmp_path / ED.ЧЕРНОВИКИ).write_text(json.dumps(данные, ensure_ascii=False),
                                         encoding="utf-8")
    with pytest.raises(ED.ОперацияОтклонена) as ош:
        ED.рецензировать("x.site", "slug-a", reviewer="claude/review-01",
                         verdict="accepted", body_digest=отп,
                         checks={к: True for к in ED.ПРОВЕРКИ_РЕЦЕНЗИИ})
    assert "совпадают" in str(ош.value)
