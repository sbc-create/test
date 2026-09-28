"""Потребление контракта обогащения оценок: что витрина примет, а что отвергнет.

Эти проверки описывают требование к Core в исполняемом виде. Пока обогащения
нет, они проверяют сторону потребителя; когда оно появится, тот же набор
станет приёмочным — ответ, который их не проходит, витрине не годится.

Почему требование именно такое, видно из измерений на полном боевом каталоге
(53 251 запись): оценка Кинопоиска есть у 36,8 %, IMDb — у 50,7 %, число
голосов не даёт ни один слой, а идентификатор Кинопоиска есть у 87,7 %. То
есть 27 127 записей — половина каталога — ждут оценки, для которой ключ
сопоставления уже известен.

Главное, чего эти проверки не допускают: оценка без происхождения, оценка
чужого произведения и затирание известного значения молчанием поставщика.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from factory.lords import ratings_contract as contract


def наблюдение(**поля) -> dict:
    основа = {
        "provider": "kinopoisk",
        "value": 7.4,
        "votes": 12043,
        "scale_max": 10,
        "observed_at": "2026-09-06T12:00:00Z",
        "match_method": "id",
        "confidence": 1.0,
        "external_id": "13608404",
    }
    основа.update(поля)
    return основа


class TestОценкаБезПроисхожденияНеПринимается:
    """Число, поставленное неизвестно кем, нельзя ни проверить, ни объяснить."""

    @pytest.mark.parametrize("поле", ["scale_max", "observed_at", "match_method", "confidence"])
    def test_отсутствие_обязательного_поля_это_отказ(self, поле):
        raw = наблюдение()
        del raw[поле]
        with pytest.raises(contract.ContractError):
            contract.parse_observation(raw)

    def test_умолчаний_нет(self):
        """Подставить разумное значение здесь значит выдумать факт."""
        with pytest.raises(contract.ContractError):
            contract.parse_observation(наблюдение(scale_max=None))

    def test_незнакомый_поставщик_отвергается(self):
        with pytest.raises(contract.ContractError):
            contract.parse_observation(наблюдение(provider="некий-агрегатор"))

    def test_нечисловая_оценка_отвергается(self):
        with pytest.raises(contract.ContractError):
            contract.parse_observation(наблюдение(value="семь с половиной"))

    def test_нецелые_голоса_отвергаются(self):
        with pytest.raises(contract.ContractError):
            contract.parse_observation(наблюдение(votes=12.5))

    def test_отсутствие_голосов_допустимо(self):
        """Источник их сегодня не даёт ни на одном слое — это измеренный факт."""
        assert contract.parse_observation(наблюдение(votes=None)).votes is None


class TestОценкаЧужогоПроизведенияНеПоказывается:
    """Сопоставление по названию находит ремейки и однофамильцев."""

    def test_сопоставление_по_идентификатору_доверия_не_требует(self):
        obs = contract.parse_observation(наблюдение(match_method="id", confidence=0.4))
        assert obs.trustworthy, "совпадение по идентификатору сомнений не вызывает"

    def test_слабое_сопоставление_по_названию_отбрасывается(self):
        obs = contract.parse_observation(
            наблюдение(match_method="title_year", confidence=0.80, external_id=None))
        assert not obs.trustworthy

    def test_уверенное_сопоставление_по_названию_принимается(self):
        obs = contract.parse_observation(
            наблюдение(match_method="title_year", confidence=0.97, external_id=None))
        assert obs.trustworthy

    def test_причина_отказа_называется(self):
        payload = [наблюдение(match_method="title_year", confidence=0.5)]
        причины = contract.rejected(payload)
        assert причины and "уверенность" in причины[0][1]

    def test_оценка_вне_шкалы_не_показывается(self):
        assert not contract.parse_observation(наблюдение(value=11, scale_max=10)).trustworthy


class TestШкалыНеСмешиваются:
    def test_обе_оценки_живут_порознь(self):
        payload = [наблюдение(), наблюдение(provider="imdb", value=6.1, external_id="tt1")]
        текущие = contract.current_ratings(payload)
        assert текущие["kinopoisk"].value == 7.4
        assert текущие["imdb"].value == 6.1

    def test_у_каждого_поставщика_своя_шкала(self):
        payload = [наблюдение(scale_max=10),
                   наблюдение(provider="imdb", value=87, scale_max=100, external_id="tt1")]
        текущие = contract.current_ratings(payload)
        assert текущие["imdb"].scale_max == 100
        assert текущие["imdb"].value == 87

    def test_из_нескольких_наблюдений_берётся_свежее(self):
        payload = [
            наблюдение(value=7.0, observed_at="2026-08-01T00:00:00Z"),
            наблюдение(value=7.9, observed_at="2026-09-06T00:00:00Z"),
        ]
        assert contract.current_ratings(payload)["kinopoisk"].value == 7.9


class TestМолчаниеНеОтменяетИзвестного:
    def test_пустой_ответ_не_стирает_известную_оценку(self):
        известно = contract.current_ratings([наблюдение()])
        слито = contract.merge_last_known_good(известно, contract.current_ratings([]))
        assert слито["kinopoisk"].value == 7.4

    def test_свежее_наблюдение_вытесняет_прежнее(self):
        известно = contract.current_ratings([наблюдение(value=7.4)])
        свежее = contract.current_ratings(
            [наблюдение(value=8.1, observed_at="2026-09-07T00:00:00Z")])
        assert contract.merge_last_known_good(известно, свежее)["kinopoisk"].value == 8.1

    def test_устаревшее_наблюдение_остаётся_видимым_но_помечено(self):
        """Вчерашняя оценка честнее отсутствия — если сказано, что она вчерашняя."""
        старое = datetime.now(timezone.utc) - timedelta(days=contract.STALE_AFTER_DAYS + 5)
        obs = contract.parse_observation(наблюдение(observed_at=старое.isoformat()))
        assert obs.trustworthy
        assert obs.stale()


class TestВерсияКонтрактаПроверяется:
    def test_чужая_версия_это_отказ(self):
        with pytest.raises(contract.ContractError):
            contract.current_ratings(
                {"contract": "ratings-enrichment/2.0.0", "observations": [наблюдение()]})

    def test_своя_версия_принимается(self):
        payload = {"contract": contract.CONTRACT_VERSION, "observations": [наблюдение()]}
        assert contract.current_ratings(payload)["kinopoisk"].value == 7.4

    def test_голый_список_принимается(self):
        """Список без обёртки — допустимая краткая форма, версия тогда неявная."""
        assert contract.current_ratings([наблюдение()])


class TestПовреждённыйОтветНеЛомаетВитрину:
    def test_одно_негодное_наблюдение_не_отменяет_остальные(self):
        payload = [{"provider": "kinopoisk"}, наблюдение(provider="imdb", external_id="tt1")]
        текущие = contract.current_ratings(payload)
        assert set(текущие) == {"imdb"}

    def test_ответ_неизвестной_формы_это_отказ(self):
        with pytest.raises(contract.ContractError):
            contract.current_ratings("оценки")
