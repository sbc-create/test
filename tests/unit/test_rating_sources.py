"""REQ-RATING-SOURCES: реестр источников оценок и договор с ними.

Оценок нет не потому, что их негде взять, а потому, что **ни один источник не
разрешён**. Это решение владельца, и подменять его нельзя ничем: ни скрапингом,
ни средним по соседям, ни «примерно».

Отсюда всё устройство слоя.

**Разрешение versioned и явное.** Источник используется только при
`authorization.status: granted`. Ни флаг в конфигурации, ни переменная среды
этого не заменяют — ровно как с идентификаторами воспроизведения.

**Отсутствие числа не превращается в ноль.** Нет источника — состояние
`SOURCE_NOT_AUTHORIZED`, а не оценка 0 и не пустая строка, которую слой выше
покажет как «0».

**Сорвавшийся источник отключается сам.** Подряд отказы открывают предохранитель,
и запросы к нему прекращаются до истечения паузы: настойчивый повтор к чужому
сервису — это нагрузка на него и отказ нам.

**Последнее известное хорошее значение живёт по сроку.** Оно отдаётся с
отметкой, когда снято, и после истечения срока перестаёт выдаваться за
свежее. Молча стареющее значение — это ложь с задержкой.

**Расхождение двух источников не усредняется.** Два разных числа — это факт о
разногласии, а не повод придумать третье.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def реестр(tmp_path):
    from factory.site_engine import rating_sources

    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    return rating_sources


class TestРеестр:
    def test_поставляется_с_реестром(self):
        путь = REPO / "config" / "rating-sources.yaml"
        assert путь.is_file(), "реестр источников — часть поставки, а не деталь среды"

    def test_разрешён_ровно_один_источник_и_это_фид(self, реестр):
        """Разрешение владельца от 2026-09-06 — на фид, и только на него.

        Раньше здесь стояло «не разрешён ни один». Это было верно до решения
        владельца; после него проверка должна утверждать не отсутствие прав, а
        их точную границу — иначе она перестаёт что-либо охранять.
        """
        решение = реестр.resolve(REPO)
        assert решение.authorized == ("provider-feed",)
        assert решение.known, "известные источники обязаны быть перечислены"
        assert not решение.blocker, "разрешённый источник — не блокер"

    def test_у_каждого_источника_объявлено_состояние_разрешения(self, реестр):
        решение = реестр.resolve(REPO)
        for источник in решение.known:
            assert источник["authorization"]["status"] in {"granted", "absent", "revoked"}
            assert источник["authorization"]["reason"], "состояние без объяснения бесполезно"

    def test_включение_без_разрешения_отклоняется(self, tmp_path, реестр):
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        (tmp_path / "config" / "rating-sources.yaml").write_text(
            "version: 1\n"
            "sources:\n"
            "  - id: пример\n"
            "    enabled: true\n"
            "    ttl_seconds: 3600\n"
            "    authorization:\n"
            "      status: absent\n"
            "      reason: не запрашивалось\n",
            encoding="utf-8",
        )
        with pytest.raises(реестр.RatingSourceError):
            реестр.resolve(tmp_path)

    def test_разрешённый_источник_попадает_в_разрешённые(self, tmp_path, реестр):
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        (tmp_path / "config" / "rating-sources.yaml").write_text(
            "version: 1\n"
            "sources:\n"
            "  - id: пример\n"
            "    enabled: true\n"
            "    ttl_seconds: 3600\n"
            "    rate_limit_per_minute: 30\n"
            "    authorization:\n"
            "      status: granted\n"
            "      reason: письмо владельца от 2026-09-05\n"
            "      document: docs/rights/пример.md\n",
            encoding="utf-8",
        )
        решение = реестр.resolve(tmp_path)
        assert решение.authorized == ("пример",)


class TestЗначенияБезИсточника:
    def test_без_источника_состояние_названо_а_не_обнулено(self, реестр):
        итог = реестр.fetch(REPO, source_id="", entity_id="site:1")
        assert итог["state"] == "SOURCE_NOT_AUTHORIZED"
        assert итог["value"] is None
        assert str(итог["value"]) != "0"

    def test_чужой_источник_не_спрашивается(self, реестр):
        итог = реестр.fetch(REPO, source_id="не-разрешён", entity_id="site:1")
        assert итог["state"] == "SOURCE_NOT_AUTHORIZED"
        assert итог["value"] is None


class TestПредохранитель:
    def test_подряд_отказы_размыкают_цепь(self, tmp_path, реестр):
        предохранитель = реестр.Breaker(порог=3, пауза=60, now=lambda: 1000.0)
        for _ in range(3):
            предохранитель.отказ()
        assert предохранитель.разомкнут() is True

    def test_после_паузы_пробует_снова(self, реестр):
        время = {"t": 1000.0}
        предохранитель = реестр.Breaker(порог=2, пауза=60, now=lambda: время["t"])
        предохранитель.отказ()
        предохранитель.отказ()
        assert предохранитель.разомкнут() is True
        время["t"] = 1061.0
        assert предохранитель.разомкнут() is False

    def test_успех_закрывает_цепь(self, реестр):
        предохранитель = реестр.Breaker(порог=2, пауза=60, now=lambda: 1000.0)
        предохранитель.отказ()
        предохранитель.успех()
        предохранитель.отказ()
        assert предохранитель.разомкнут() is False


class TestПоследнееХорошее:
    def test_значение_отдаётся_со_сроком_и_отметкой(self, tmp_path, реестр):
        хранилище = реестр.LastKnownGood(tmp_path, ttl_seconds=100, now=lambda: 1000.0)
        хранилище.put("site:1", источник="s", value=7.4, votes=120)
        итог = хранилище.get("site:1")
        assert итог["value"] == 7.4
        assert итог["stale"] is False
        assert итог["capturedAt"]

    def test_после_срока_значение_помечается_устаревшим(self, tmp_path, реестр):
        время = {"t": 1000.0}
        хранилище = реестр.LastKnownGood(tmp_path, ttl_seconds=100, now=lambda: время["t"])
        хранилище.put("site:1", источник="s", value=7.4, votes=120)
        время["t"] = 1101.0
        итог = хранилище.get("site:1")
        assert итог["stale"] is True, "молча стареющее значение — это ложь с задержкой"
        assert итог["value"] == 7.4, "значение не выбрасывается: оно перестаёт быть свежим"

    def test_чего_не_было_того_нет(self, tmp_path, реестр):
        хранилище = реестр.LastKnownGood(tmp_path, ttl_seconds=100, now=lambda: 1000.0)
        assert хранилище.get("site:нет") is None


class TestРасхождение:
    def test_два_разных_числа_не_усредняются(self, реестр):
        итог = реестр.reconcile(
            [
                {"source": "a", "value": 7.4, "votes": 100},
                {"source": "b", "value": 6.1, "votes": 900},
            ]
        )
        assert итог["state"] == "SOURCES_DISAGREE"
        assert итог["value"] is None
        assert {з["source"] for з in итог["candidates"]} == {"a", "b"}

    def test_совпадение_в_пределах_допуска_принимается(self, реестр):
        итог = реестр.reconcile(
            [
                {"source": "a", "value": 7.4, "votes": 100},
                {"source": "b", "value": 7.42, "votes": 900},
            ]
        )
        assert итог["state"] == "AGREED"
        # Берётся значение источника с большим числом голосов, а не среднее:
        # среднее — это третье число, которого не сообщал никто.
        assert итог["value"] == 7.42
        assert итог["chosen"] == "b"

    def test_единственный_источник_это_не_согласие(self, реестр):
        итог = реестр.reconcile([{"source": "a", "value": 7.4, "votes": 100}])
        assert итог["state"] == "SINGLE_SOURCE"
        assert итог["value"] == 7.4

    def test_пустой_список_не_даёт_нуля(self, реестр):
        итог = реестр.reconcile([])
        assert итог["state"] == "NO_DATA"
        assert итог["value"] is None


class TestМаршрутИЭкран:
    def test_состояние_источников_видно_через_api(self):
        from factory.site_engine.api.control import ControlApi

        api = ControlApi(
            root=REPO, env={"SITE_ENGINE_CONTROL_TOKENS": "t=read"}
        )
        ответ = api.handle(
            "GET", "/api/v1/rating-sources", headers={"Authorization": "Bearer t"}
        )
        assert ответ.status == 200
        assert ответ.body["authorized"] == ["provider-feed"]
        assert ответ.body["known"]
        assert ответ.body["blocker"] == "", "при разрешённом источнике блокера нет"

    def test_сторонние_сайты_остаются_запрещёнными(self, реестр):
        """Проверяется разобранный реестр, а не текст файла.

        Разрешение на фид не расширяется на сайты, чьи метрики в этом фиде
        приходят: значение берётся из фида, а не с сайта, и совпадение имени
        метрики с именем сайта их не уравнивает.
        """
        решение = реестр.resolve(REPO)
        по_имени = {и["id"]: и for и in решение.known}
        for имя in ("imdb", "kinopoisk"):
            assert по_имени[имя]["authorization"]["status"] != "granted"
            assert имя not in решение.authorized
