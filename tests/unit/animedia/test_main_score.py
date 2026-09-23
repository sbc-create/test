"""Единый главный рейтинг: внешняя стартовая база плюс наши голоса.

Формула одна на весь сайт:

    main_score = (ВЕС_БАЗЫ * B + сумма_наших) / (ВЕС_БАЗЫ + число_наших)

Пяти фиктивных голосов при этом не заводится: вес живёт в формуле, а
native_count считает только реальные записи посетителей. Это проверяется
отдельно, потому что соблазн «просто добавить пять строк в votes» велик и
последствия его необратимы.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[3] / "factory" / "animedia" / "community.py"


def load():
    spec = importlib.util.spec_from_file_location("animedia_community_ms", MODULE)
    m = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


CM = load()
ТЕМА = "01a0b507-3280-7b2a-8af4-674dd73cff72"
ГОСТЬ, ДРУГОЙ, ТРЕТИЙ = "cookie-1", "cookie-2", "cookie-3"
ВНЕШНИЕ = {"shikimori": 8.0, "kp": 6.0, "imdb": 9.5}


@pytest.fixture()
def store(tmp_path):
    return CM.Хранилище(tmp_path / "c.json", витрина="animedia-01")


class TestВыборБазы:
    def test_берётся_первый_по_приоритету_а_не_максимум(self):
        основа = CM.выбрать_базу(ВНЕШНИЕ)
        assert основа["source"] == "shikimori", "выбран не первый по приоритету"
        assert основа["value"] == 8.0
        assert основа["value"] != 9.5, "выбран максимум ради красивого числа"

    def test_следующий_по_приоритету_если_первого_нет(self):
        assert CM.выбрать_базу({"kp": 6.0, "imdb": 9.5})["source"] == "kp"

    def test_шкала_приводится_к_десятке(self):
        основа = CM.выбрать_базу({"kp": {"value": 60, "scale": 100}})
        assert основа["value"] == 6.0
        assert основа["raw_value"] == 60 and основа["raw_scale"] == 100.0, (
            "исходное значение источника не сохранено как есть"
        )

    def test_источник_вне_приоритета_не_берётся(self):
        assert CM.выбрать_базу({"amd": 9.9}) is None, "оценка витрины взята как внешняя"
        assert CM.выбрать_базу(ВНЕШНИЕ, приоритет=("imdb",))["source"] == "imdb"

    def test_ноль_и_мусор_не_оценка(self):
        for плохое in ({"kp": 0}, {"kp": None}, {"kp": "нет"}, {"kp": -3}, {}):
            assert CM.выбрать_базу(плохое) is None, плохое


class TestЧетыреСостояния:
    def test_база_и_голоса(self, store):
        store.добавить_голос(ТЕМА, 10, ГОСТЬ, внешние=ВНЕШНИЕ)
        r = store.главный_рейтинг(ТЕМА, ВНЕШНИЕ)
        # (5*8 + 10) / (5 + 1) = 50/6 = 8.333…
        assert r["состояние"] == "base+votes"
        assert r["голосов"] == 1 and r["сумма"] == 10
        assert r["точное"] == pytest.approx(50 / 6)
        assert r["значение"] == 8.3

    def test_только_база(self, store):
        r = store.главный_рейтинг(ТЕМА, ВНЕШНИЕ)
        assert r["состояние"] == "base-only"
        assert r["значение"] == 8.0 and r["голосов"] == 0

    def test_только_голоса(self, store):
        store.добавить_голос(ТЕМА, 7, ГОСТЬ, внешние=None)
        store.добавить_голос(ТЕМА, 4, ДРУГОЙ, внешние=None)
        r = store.главный_рейтинг(ТЕМА, внешние=None)
        assert r["состояние"] == "votes-only"
        assert r["значение"] == 5.5 and r["голосов"] == 2

    def test_пусто_без_выдуманного_нуля(self, store):
        r = store.главный_рейтинг(ТЕМА, внешние=None)
        assert r["состояние"] == "empty"
        assert r["значение"] is None and r["точное"] is None, "подставлен ноль"
        assert r["голосов"] == 0


class TestВесНеГолоса:
    def test_вес_не_создаёт_записей_в_хранилище(self, store, tmp_path):
        store.добавить_голос(ТЕМА, 10, ГОСТЬ, внешние=ВНЕШНИЕ)
        данные = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))
        голоса = данные["titles"][ТЕМА]["votes"]
        assert len(голоса) == 1, f"в хранилище появились лишние голоса: {голоса}"

    def test_счётчик_показывает_только_живых(self, store):
        store.добавить_голос(ТЕМА, 10, ГОСТЬ, внешние=ВНЕШНИЕ)
        r = store.главный_рейтинг(ТЕМА, ВНЕШНИЕ)
        assert r["голосов"] == 1, "вес посчитан как голоса"
        assert r["вес"] == CM.ВЕС_БАЗЫ

    def test_вес_версионирован(self):
        assert isinstance(CM.ВЕС_БАЗЫ, int) and CM.ВЕС_БАЗЫ == 5
        assert CM.ВЕРСИЯ_РАСЧЁТА == "main-score/1.0"


class TestБазаФиксируется:
    def test_фиксируется_первым_голосом(self, store, tmp_path):
        store.добавить_голос(ТЕМА, 9, ГОСТЬ, внешние=ВНЕШНИЕ)
        база = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))[
            "titles"][ТЕМА]["base"]
        assert база["source"] == "shikimori" and база["value"] == 8.0
        assert база["fixed_by"] == "first-vote" and база["fixed_at"]
        assert база["weight"] == CM.ВЕС_БАЗЫ

    def test_обновление_внешнего_не_меняет_закреплённую(self, store):
        store.добавить_голос(ТЕМА, 9, ГОСТЬ, внешние=ВНЕШНИЕ)
        новые = {"shikimori": 3.0, "kp": 6.0}
        r = store.главный_рейтинг(ТЕМА, новые)
        assert r["база"]["value"] == 8.0, "закреплённая база подменена скрытно"
        assert r["точное"] == pytest.approx((5 * 8.0 + 9) / 6)
        assert r["база_разошлась"] is True, "расхождение не показано"
        assert r["внешняя_сейчас"]["value"] == 3.0, "текущая внешняя не показана"

    def test_до_первого_голоса_база_предварительная_и_не_пишется(self, store, tmp_path):
        r = store.главный_рейтинг(ТЕМА, ВНЕШНИЕ)
        assert r["база_предварительная"] is True
        данные = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))
        assert "base" not in (данные.get("titles") or {}).get(ТЕМА, {}), (
            "база записана без единого голоса"
        )

    def test_второй_голос_не_перефиксирует(self, store):
        store.добавить_голос(ТЕМА, 9, ГОСТЬ, внешние=ВНЕШНИЕ)
        store.добавить_голос(ТЕМА, 2, ДРУГОЙ, внешние={"shikimori": 1.0})
        r = store.главный_рейтинг(ТЕМА, ВНЕШНИЕ)
        assert r["база"]["value"] == 8.0
        assert r["точное"] == pytest.approx((5 * 8.0 + 11) / 7)


class TestМиграция:
    def _со_старыми_голосами(self, tmp_path):
        путь = tmp_path / "c.json"
        путь.write_text(json.dumps({
            "schema_version": 2, "site_id": "animedia-01",
            "titles": {ТЕМА: {"votes": {CM._посетитель(ГОСТЬ): 6},
                              "reactions": {}, "comments": []}},
        }), encoding="utf-8")
        return CM.Хранилище(путь, витрина="animedia-01")

    def test_миграция_закрепляет_базу_существующим_голосам(self, tmp_path):
        х = self._со_старыми_голосами(tmp_path)
        assert х.темы_без_базы() == [ТЕМА]
        итог = х.зафиксировать_базу(ТЕМА, ВНЕШНИЕ)
        assert итог["status"] == "fixed"
        assert итог["base"]["fixed_by"] == "migration"
        assert х.темы_без_базы() == []

    def test_миграция_идемпотентна(self, tmp_path):
        х = self._со_старыми_голосами(tmp_path)
        х.зафиксировать_базу(ТЕМА, ВНЕШНИЕ)
        первая = х.главный_рейтинг(ТЕМА, ВНЕШНИЕ)["база"]
        итог = х.зафиксировать_базу(ТЕМА, {"shikimori": 2.0})
        assert итог["status"] == "already"
        assert х.главный_рейтинг(ТЕМА, ВНЕШНИЕ)["база"] == первая

    def test_миграция_сохраняет_голоса(self, tmp_path):
        х = self._со_старыми_голосами(tmp_path)
        х.зафиксировать_базу(ТЕМА, ВНЕШНИЕ)
        с = х.состояние(ТЕМА, ГОСТЬ)
        assert с.голосов == 1 and с.мой_голос == 6, "миграция тронула голоса"

    def test_тему_без_голосов_миграция_пропускает(self, store):
        итог = store.зафиксировать_базу(ТЕМА, ВНЕШНИЕ)
        assert итог["status"] == "no-votes"
        assert store.главный_рейтинг(ТЕМА, ВНЕШНИЕ)["база_предварительная"] is True


class TestПравилоГолосаСохранено:
    def test_первая_оценка_окончательна(self, store):
        store.добавить_голос(ТЕМА, 8, ГОСТЬ, внешние=ВНЕШНИЕ)
        store.добавить_голос(ТЕМА, 8, ГОСТЬ, внешние=ВНЕШНИЕ)   # идемпотентно
        with pytest.raises(CM.ГолосЗакреплён):
            store.добавить_голос(ТЕМА, 3, ГОСТЬ, внешние=ВНЕШНИЕ)
        r = store.главный_рейтинг(ТЕМА, ВНЕШНИЕ)
        assert r["голосов"] == 1 and r["сумма"] == 8

    def test_изоляция_витрин_сохранена(self, tmp_path):
        одна = CM.Хранилище(tmp_path / "a.json", витрина="animedia-01")
        другая = CM.Хранилище(tmp_path / "b.json", витрина="animedia-02")
        одна.добавить_голос(ТЕМА, 10, ГОСТЬ, внешние=ВНЕШНИЕ)
        assert другая.главный_рейтинг(ТЕМА, ВНЕШНИЕ)["голосов"] == 0


class TestКонкурентность:
    def test_гонка_первого_голоса_фиксирует_базу_один_раз(self, tmp_path):
        import threading
        х = CM.Хранилище(tmp_path / "c.json", витрина="animedia-01")
        барьер = threading.Barrier(10)

        def голосовать(кто, значение):
            барьер.wait()
            try:
                х.добавить_голос(ТЕМА, значение, кто, внешние=ВНЕШНИЕ)
            except CM.ГолосЗакреплён:
                pass

        нити = [threading.Thread(target=голосовать, args=(f"cookie-{i}", (i % 10) + 1))
                for i in range(10)]
        for н in нити:
            н.start()
        for н in нити:
            н.join()

        данные = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))
        запись = данные["titles"][ТЕМА]
        assert len(запись["votes"]) == 10, "часть голосов потеряна в гонке"
        assert запись["base"]["value"] == 8.0
        r = х.главный_рейтинг(ТЕМА, ВНЕШНИЕ)
        assert r["точное"] == pytest.approx(
            (5 * 8.0 + sum(запись["votes"].values())) / (5 + 10))


class TestОкругление:
    def test_округляется_только_показ(self, store):
        store.добавить_голос(ТЕМА, 10, ГОСТЬ, внешние={"shikimori": 7.0})
        r = store.главный_рейтинг(ТЕМА, {"shikimori": 7.0})
        assert r["точное"] == pytest.approx(45 / 6)      # 7.5
        assert r["значение"] == 7.5
        store2 = store
        store2.добавить_голос(ТЕМА, 9, ДРУГОЙ, внешние={"shikimori": 7.0})
        r = store2.главный_рейтинг(ТЕМА, {"shikimori": 7.0})
        assert r["значение"] == round(r["точное"], 1)
        assert r["точное"] != r["значение"], "точное значение уже округлено"


class TestКэшЧтения:
    """Кэш по mtime не должен показывать устаревшее.

    Витрина многопроцессная только условно, но файл правит и соседний процесс
    (миграция, ручная правка владельца). Кэш, переживший чужую запись, показал
    бы рейтинг, которого в файле уже нет.
    """

    def test_чужая_запись_видна_сразу(self, tmp_path):
        путь = tmp_path / "c.json"
        х = CM.Хранилище(путь, витрина="animedia-01")
        х.добавить_голос(ТЕМА, 8, ГОСТЬ, внешние=ВНЕШНИЕ)
        assert х.главный_рейтинг(ТЕМА, ВНЕШНИЕ)["голосов"] == 1

        # Правка мимо этого объекта — как это сделал бы соседний процесс.
        данные = json.loads(путь.read_text(encoding="utf-8"))
        данные["titles"][ТЕМА]["votes"]["посторонний"] = 2
        путь.write_text(json.dumps(данные), encoding="utf-8")

        assert х.главный_рейтинг(ТЕМА, ВНЕШНИЕ)["голосов"] == 2, (
            "кэш пережил чужую запись"
        )

    def test_кэш_не_отдаёт_общий_словарь_на_правку(self, tmp_path):
        х = CM.Хранилище(tmp_path / "c.json", витрина="animedia-01")
        х.добавить_голос(ТЕМА, 8, ГОСТЬ, внешние=ВНЕШНИЕ)
        первое = х._прочитать()
        первое["titles"][ТЕМА]["votes"]["подделка"] = 10
        assert х.главный_рейтинг(ТЕМА, ВНЕШНИЕ)["голосов"] == 1, (
            "правка копии просочилась в кэш"
        )
