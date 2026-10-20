"""Проверки поиска признака доступности видео.

Инструмент отвечает на вопрос приёмки MOD-97: есть ли ВООБЩЕ поле, которое
делит карточки по границе «играет / не играет». Ответ «признака нет» принимается
только от проверки, которая умеет ответить и «есть», поэтому положительный
контроль здесь обязателен и стоит первым.

Отрицательные контроли, названные заранее:

* уникальный идентификатор не считается признаком — сравниваются КЛАССЫ
  значений, иначе любое поле с id делило бы любую выборку;
* `data-player-contract` не выдаётся за оболочку плеера — именно на этом
  шаблоне (`\\bdata-player\\b` совпадает и с `data-player-contract`, потому что
  граница слова проходит по дефису) инструмент 20.10 печатал состояние `None`
  вместо `resolving`;
* поля с подписями и номером издателя в отчёт не попадают;
* непрочитанная страница даёт «не измерено», а не вывод.

Сеть не используется: ввод-вывод подменяется.
"""
from __future__ import annotations

import importlib.util
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_с = importlib.util.spec_from_file_location(
    "availability_signal_check",
    КОРЕНЬ / "automation/local/availability-signal-check.py")
ИНСТР = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ИНСТР)


def _карточка(*, состояние="resolving", агрегатор="cvh", ид="01a1-уник",
              плейлист=None, разметка_прочитана=True):
    разметка = {"код": 200, "data-state": состояние,
                "data-aggregator": агрегатор, "data-title-id": ид,
                "data-publisher-id": "10372",
                "data-src-candidates": f'[{{"aggregator":"{агрегатор}",'
                                       f'"id":"{ид}"}}]'}
    if not разметка_прочитана:
        разметка = {"не_прочитано": "страница ответила 404"}
    return {"адрес": f"https://zonafilm12.site/title/{ид}/",
            "витрина": "zonafilm12.site",
            "разметка": разметка,
            "кандидат": (агрегатор, ид),
            "плейлист": {"код": 200, "ответ": плейлист} if плейлист is not None
                        else {"не_прочитано": "плейлист ответил 0"}}


ФИЛЬМ = {"titleName": "Фильм", "isSerial": False,
         "items": [{"cvhId": "01a1-дорожка", "vkId": 1, "voiceStudio": "С",
                    "voiceType": "Многоголосый"}],
         "trailers": None}
СЕРИАЛ = {"titleName": "Сериал", "isSerial": True,
          "items": [{"cvhId": "01a1-дорожка", "vkId": 2, "voiceStudio": "С",
                     "voiceType": "Многоголосый", "season": 1, "episode": 1}],
          "trailers": None}


# --- положительный контроль: признак, который ЕСТЬ, находится ----------------

def test_существующий_признак_находится():
    итог = ИНСТР.разделяющие([_карточка(плейлист=ФИЛЬМ, ид="a"),
                              _карточка(плейлист=ФИЛЬМ, ид="b")],
                             [_карточка(плейлист=СЕРИАЛ, ид="c")])
    assert "плейлист.isSerial" in итог["разделяющие"]
    assert итог["разделяющие"]["плейлист.isSerial"] == ("логическое=False",
                                                        "логическое=True")


def test_признак_в_разметке_находится():
    итог = ИНСТР.разделяющие([_карточка(плейлист=ФИЛЬМ, состояние="playable")],
                             [_карточка(плейлист=ФИЛЬМ, состояние=None)])
    assert "разметка.data-state" in итог["разделяющие"]


def test_код_возврата_3_когда_признак_найден(monkeypatch, capsys):
    _подменить(monkeypatch, {"a": ФИЛЬМ, "c": СЕРИАЛ})
    код = ИНСТР.main(["--plays", "https://zonafilm12.site/title/a/",
                      "--fails", "https://zonafilm12.site/title/c/"])
    assert код == 3
    вывод = capsys.readouterr().out
    assert "КАНДИДАТЫ В ПРИЗНАК" in вывод
    assert "неиграющая карточка одна" in вывод


# --- признака нет -------------------------------------------------------------

def test_одинаковые_карточки_признака_не_дают():
    итог = ИНСТР.разделяющие([_карточка(плейлист=ФИЛЬМ, ид="a"),
                              _карточка(плейлист=ФИЛЬМ, ид="b")],
                             [_карточка(плейлист=ФИЛЬМ, ид="c")])
    assert итог["разделяющие"] == {}
    assert итог["сравнено_полей"] > 5


def test_уникальный_идентификатор_не_признак():
    """Отрицательный контроль: id различается у всех, признаком быть не может."""
    итог = ИНСТР.разделяющие([_карточка(плейлист=ФИЛЬМ, ид="уник-1")],
                             [_карточка(плейлист=ФИЛЬМ, ид="уник-2")])
    assert "разметка.data-title-id" not in итог["разделяющие"]
    assert итог["разделяющие"] == {}


def test_агрегатор_не_признак_если_играют_оба():
    итог = ИНСТР.разделяющие([_карточка(плейлист=ФИЛЬМ, агрегатор="cvh", ид="a"),
                              _карточка(плейлист=ФИЛЬМ, агрегатор="kp", ид="b")],
                             [_карточка(плейлист=ФИЛЬМ, агрегатор="cvh", ид="c")])
    assert "разметка.data-aggregator" not in итог["разделяющие"]


def test_код_возврата_0_когда_признака_нет(monkeypatch, capsys):
    _подменить(monkeypatch, {"a": ФИЛЬМ, "c": ФИЛЬМ})
    код = ИНСТР.main(["--plays", "https://zonafilm12.site/title/a/",
                      "--fails", "https://zonafilm12.site/title/c/"])
    assert код == 0
    assert "ПРИЗНАКА НЕТ" in capsys.readouterr().out


# --- состояние берётся у элемента плеера --------------------------------------

РАЗМЕТКА = (
    '<html><head><style>[data-player-host]{position:absolute}</style></head>'
    '<body><section class="zpl" id="watch" data-player-contract="cdnvideohub-player-v1">'
    '<div class="zpl__f" data-player data-state="resolving">'
    '<div data-player-host data-src-candidates="[{&quot;aggregator&quot;:'
    '&quot;cvh&quot;,&quot;id&quot;:&quot;01a1-уник&quot;}]">'
    '<video-player data-publisher-id="10372" data-aggregator="cvh"'
    ' data-title-id="01a1-уник"></video-player></div></div></section></body></html>')


def test_состояние_берётся_у_элемента_с_data_state(monkeypatch):
    monkeypatch.setattr(ИНСТР, "_получить", lambda *а, **к: (200, РАЗМЕТКА))
    разметка = ИНСТР.разметка_страницы("https://zonafilm12.site/title/a/")
    assert разметка["data-state"] == "resolving"


def test_секция_с_data_player_contract_не_оболочка(monkeypatch):
    """Отрицательный контроль: ровно та ошибка, что печатала состояние None."""
    без_состояния = РАЗМЕТКА.replace(
        '<div class="zpl__f" data-player data-state="resolving">', "<div>")
    monkeypatch.setattr(ИНСТР, "_получить", lambda *а, **к: (200, без_состояния))
    разметка = ИНСТР.разметка_страницы("https://zonafilm12.site/title/a/")
    assert разметка["data-state"] == "элемента с data-state на странице нет"


def test_кандидат_читается_из_атрибута(monkeypatch):
    monkeypatch.setattr(ИНСТР, "_получить", lambda *а, **к: (200, РАЗМЕТКА))
    разметка = ИНСТР.разметка_страницы("https://zonafilm12.site/title/a/")
    assert ИНСТР.кандидат_источника(разметка) == ("cvh", "01a1-уник")


def test_кандидат_без_атрибута_берётся_из_title_id():
    разметка = {"data-src-candidates": None, "data-aggregator": "kp",
                "data-title-id": "12345"}
    assert ИНСТР.кандидат_источника(разметка) == ("kp", "12345")


def test_кандидата_нет_когда_нет_ни_того_ни_другого():
    assert ИНСТР.кандидат_источника({"data-src-candidates": "[]",
                                     "data-aggregator": None,
                                     "data-title-id": None}) is None


# --- закрытые поля и непрочитанные страницы -----------------------------------

def test_подписи_и_издатель_в_отчёт_не_попадают():
    с_подписью = dict(ФИЛЬМ)
    с_подписью["items"] = [{"cvhId": "x", "url": "https://c/v?sig=СЕКРЕТ",
                            "expires": 123}]
    без = dict(ФИЛЬМ)
    итог = ИНСТР.разделяющие([_карточка(плейлист=без, ид="a")],
                             [_карточка(плейлист=с_подписью, ид="c")])
    assert not any("sig" in п or "expires" in п or "publisher" in п
                   for п in итог["разделяющие"])


def test_непрочитанная_страница_не_даёт_вывода(monkeypatch, capsys):
    monkeypatch.setattr(ИНСТР, "_получить", lambda *а, **к: (404, ""))
    код = ИНСТР.main(["--plays", "https://zonafilm12.site/title/a/",
                      "--fails", "https://zonafilm12.site/title/c/"])
    assert код == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out


def test_поля_называют_класс_а_не_значение():
    плоско = ИНСТР.поля({"a": "строка", "b": 1, "c": None, "d": True,
                         "e": [1, 2, 3]})
    assert плоско["a"] == "строка"
    assert плоско["b"] == "число"
    assert плоско["c"] == "пусто"
    assert плоско["d"] == "логическое=True"
    assert плоско["e"] == "список[3]"


def _подменить(monkeypatch, плейлисты: dict):
    """Подменяет сеть: страница по слагу и плейлист по его записи."""
    def получить(адрес, заголовки=None):
        if "plapi" in адрес:
            for слаг, ответ in плейлисты.items():
                if f"id=01a1-{слаг}" in адрес:
                    import json
                    return 200, json.dumps(ответ, ensure_ascii=False)
            return 404, ""
        слаг = адрес.rstrip("/").rsplit("/", 1)[-1]
        if слаг not in плейлисты:
            return 404, ""
        return 200, РАЗМЕТКА.replace("01a1-уник", f"01a1-{слаг}")
    monkeypatch.setattr(ИНСТР, "_получить", получить)

# --- пустая группа сравнения --------------------------------------------------
#
# Отрицательный контроль на ошибку, измеренную 20.10 на zonafilm.cc: без
# неиграющих карточек каждое поле читается как «поля нет» на пустой стороне и
# попадает в «кандидаты». Инструмент напечатал пять кандидатов из рекламных
# полей и вернул 3 — уверенный ответ из отсутствия данных.

def test_без_неиграющих_карточек_кандидатов_не_печатает(monkeypatch, capsys):
    _подменить(monkeypatch, {"a": ФИЛЬМ, "b": СЕРИАЛ})
    код = ИНСТР.main(["--plays", "https://zonafilm12.site/title/a/",
                      "--plays", "https://zonafilm12.site/title/b/"])
    assert код == 2
    вывод = capsys.readouterr().out
    assert "сравнивать не с чем" in вывод
    assert "КАНДИДАТЫ" not in вывод


def test_без_играющих_карточек_тоже_не_измерено(monkeypatch, capsys):
    _подменить(monkeypatch, {"c": ФИЛЬМ})
    код = ИНСТР.main(["--fails", "https://zonafilm12.site/title/c/"])
    assert код == 2
    assert "прочитанных играющих карточек ноль" in capsys.readouterr().out


def test_непрочитанная_страница_не_считается_группой(monkeypatch, capsys):
    """Страница в группе есть, но не прочитана — это тоже пустая сторона."""
    _подменить(monkeypatch, {"a": ФИЛЬМ})
    код = ИНСТР.main(["--plays", "https://zonafilm12.site/title/a/",
                      "--fails", "https://zonafilm12.site/title/нет-такой/"])
    assert код == 2
    assert "сравнивать не с чем" in capsys.readouterr().out
