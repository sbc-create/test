"""Барьер ревизий: вытесненная заявка не переключит production никогда.

Дважды подряд заявка присоединялась к чужому прогону и часами отрисовывала не
то, что просили. Защитой был порядок событий — то есть надежда. Барьер убирает
надежду: у витрины есть монотонное поколение и объявленная желаемая ревизия, а
заявка предъявляет своё поколение в четырёх местах, включая последнее — прямо
перед атомарным переключением. Между отрисовкой и переключением проходят часы,
и именно там раньше происходила подмена.
"""

from __future__ import annotations

import json

import pytest

from automation.deploy import lords_fence as fence

РЕВ_A = "a" * 40
РЕВ_B = "b" * 40
ART_A = "1" * 64
ART_B = "2" * 64


@pytest.fixture()
def корень(tmp_path):
    return tmp_path / "fence"


class TestОбъявлениеПоколений:
    def test_первое_объявление_даёт_поколение_один(self, корень):
        б = fence.объявить("lords-02", РЕВ_A, ART_A, корень=корень)
        assert б.generation == 1 and б.desired_revision == РЕВ_A

    def test_поколение_растёт_монотонно(self, корень):
        fence.объявить("lords-02", РЕВ_A, ART_A, корень=корень)
        второй = fence.объявить("lords-02", РЕВ_B, ART_B, корень=корень)
        assert второй.generation == 2

    def test_повтор_той_же_ревизии_тоже_поднимает_поколение(self, корень):
        """Иначе «выложить заново» означало бы гонку старой и новой попытки."""
        fence.объявить("lords-02", РЕВ_A, ART_A, корень=корень)
        снова = fence.объявить("lords-02", РЕВ_A, ART_A, корень=корень)
        assert снова.generation == 2

    def test_короткая_ревизия_отвергается(self, корень):
        with pytest.raises(fence.FenceError):
            fence.объявить("lords-02", "abc", ART_A, корень=корень)

    def test_отпечаток_не_sha256_отвергается(self, корень):
        with pytest.raises(fence.FenceError):
            fence.объявить("lords-02", РЕВ_A, "короткий", корень=корень)

    def test_имя_витрины_с_путём_отвергается(self, корень):
        with pytest.raises(fence.FenceError):
            fence.объявить("../etc/passwd", РЕВ_A, ART_A, корень=корень)


class TestВытеснение:
    def test_старая_ревизия_не_проходит(self, корень):
        """Пункт: старая ревизия не запускается."""
        fence.объявить("lords-02", РЕВ_A, ART_A, корень=корень)
        новое = fence.объявить("lords-02", РЕВ_B, ART_B, корень=корень)
        решение = fence.проверить("lords-02", generation=1, revision=РЕВ_A,
                                  artifact_sha256=ART_A, этап="enqueue", корень=корень)
        assert решение["allowed"] is False
        assert решение["verdict"] == fence.ВЫТЕСНЕНА
        assert str(новое.generation) in решение["reason"]

    def test_старый_job_не_переключит_после_новой_generation(self, корень):
        """Пункт: старый job не может переключиться после новой generation.

        Самая дорогая из проверок: между отрисовкой и переключением проходят
        часы, и заявка, законная в начале, к концу может оказаться вытесненной.
        """
        fence.объявить("lords-02", РЕВ_A, ART_A, корень=корень)
        перед_рендером = fence.проверить("lords-02", generation=1, revision=РЕВ_A,
                                         artifact_sha256=ART_A, этап="pre-render",
                                         корень=корень)
        assert перед_рендером["allowed"] is True
        fence.объявить("lords-02", РЕВ_B, ART_B, корень=корень)  # пока шла отрисовка
        перед_switch = fence.проверить("lords-02", generation=1, revision=РЕВ_A,
                                       artifact_sha256=ART_A, этап="pre-switch",
                                       корень=корень)
        assert перед_switch["allowed"] is False
        assert перед_switch["verdict"] == fence.ВЫТЕСНЕНА

    def test_подмена_артефакта_при_той_же_ревизии_отвергается(self, корень):
        fence.объявить("lords-02", РЕВ_A, ART_A, корень=корень)
        решение = fence.проверить("lords-02", generation=1, revision=РЕВ_A,
                                  artifact_sha256=ART_B, этап="pre-switch", корень=корень)
        assert решение["allowed"] is False

    def test_поколение_из_будущего_отвергается(self, корень):
        fence.объявить("lords-02", РЕВ_A, ART_A, корень=корень)
        решение = fence.проверить("lords-02", generation=9, revision=РЕВ_A,
                                  artifact_sha256=ART_A, этап="capture", корень=корень)
        assert решение["allowed"] is False

    def test_без_барьера_ничего_не_проходит(self, корень):
        решение = fence.проверить("lords-02", generation=1, revision=РЕВ_A,
                                  artifact_sha256=ART_A, этап="enqueue", корень=корень)
        assert решение["allowed"] is False


class TestОткатЭтоНовоеПоколение:
    def test_возврат_старой_ревизии_идёт_новым_поколением(self, корень):
        """Старый артефакт разрешён только явным откатом — как новая generation."""
        fence.объявить("lords-02", РЕВ_A, ART_A, корень=корень)
        fence.объявить("lords-02", РЕВ_B, ART_B, корень=корень)
        откат = fence.объявить("lords-02", РЕВ_A, ART_A, reason="rollback", корень=корень)
        assert откат.generation == 3
        # Заявка первого поколения по-прежнему вытеснена и не воскресает.
        assert fence.проверить("lords-02", generation=1, revision=РЕВ_A,
                               artifact_sha256=ART_A, этап="capture",
                               корень=корень)["allowed"] is False
        assert fence.проверить("lords-02", generation=3, revision=РЕВ_A,
                               artifact_sha256=ART_A, этап="capture",
                               корень=корень)["allowed"] is True


class TestИзоляцияВитрин:
    def test_зависшая_витрина_не_блокирует_остальные(self, корень):
        """Пункт: зависший сайт не блокирует остальные."""
        fence.объявить("lords-02", РЕВ_A, ART_A, корень=корень)
        fence.объявить("yummy-biz", РЕВ_B, ART_B, корень=корень)
        fence.объявить("lords-02", РЕВ_B, ART_B, корень=корень)  # lords-02 вытеснена
        assert fence.проверить("lords-02", generation=1, revision=РЕВ_A,
                               artifact_sha256=ART_A, этап="capture",
                               корень=корень)["allowed"] is False
        assert fence.проверить("yummy-biz", generation=1, revision=РЕВ_B,
                               artifact_sha256=ART_B, этап="capture",
                               корень=корень)["allowed"] is True


class TestЦелостностьСостояния:
    def test_запись_атомарна_и_не_оставляет_временных(self, корень):
        fence.объявить("lords-02", РЕВ_A, ART_A, корень=корень)
        fence.объявить("lords-02", РЕВ_B, ART_B, корень=корень)
        assert not list(корень.glob("*.tmp"))
        json.loads((корень / "lords-02.json").read_text(encoding="utf-8"))

    def test_испорченный_барьер_это_отказ_а_не_разрешение(self, корень):
        """Молча разрешить всё в момент, когда защита сломана, — потерять её."""
        корень.mkdir(parents=True, exist_ok=True)
        (корень / "lords-02.json").write_text("{сломано", encoding="utf-8")
        with pytest.raises(fence.FenceError):
            fence.прочитать("lords-02", корень=корень)

    def test_четыре_этапа_называются_в_решении(self, корень):
        fence.объявить("lords-02", РЕВ_A, ART_A, корень=корень)
        for этап in ("enqueue", "capture", "pre-render", "pre-switch"):
            решение = fence.проверить("lords-02", generation=1, revision=РЕВ_A,
                                      artifact_sha256=ART_A, этап=этап, корень=корень)
            assert решение["stage"] == этап and решение["allowed"] is True
