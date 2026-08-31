"""Реестр адресов: личность записи важнее её названия.

Дефект, ради которого написан модуль, стоил 207 записей из 53 116. Проверки
ниже стерегут не форму кода, а те свойства, отсутствие которых к потере и
привело.
"""
import json
from pathlib import Path

import pytest

from factory.site_engine.routes import (
    SEPARATOR,
    Candidate,
    Route,
    RouteError,
    RouteRegistry,
    discriminator,
    seed_from_live,
)


def кандидаты(*пары: tuple[str, str]) -> list[Candidate]:
    return [Candidate(content_id=c, base_slug=s) for c, s in пары]


class TestИсходныйДефект:
    """«Акулы» вторым экземпляром отбирали адрес у «Акул 2»."""

    def test_суффикс_больше_не_вторгается_в_чужую_группу(self):
        registry = RouteRegistry("lords-01")
        итог = registry.assign(
            кандидаты(("p:a", "akuly"), ("p:b", "akuly"), ("p:c", "akuly-2"))
        )
        assert итог["p:c"] == "akuly-2", "законный владелец сохраняет свой адрес"
        assert итог["p:a"] != итог["p:b"]
        assert len(set(итог.values())) == 3

    def test_разделитель_невозможен_в_естественном_адресе(self):
        """`slugify` схлопывает серии дефисов — значит, пространства не пересекаются."""
        from factory.lords.live_catalog import slugify

        assert SEPARATOR not in slugify("Акулы -- 2")
        assert SEPARATOR not in slugify("что-то — тире")

    def test_каждая_запись_получает_адрес(self):
        registry = RouteRegistry("lords-01")
        итог = registry.assign(кандидаты(*[(f"p:{i}", "odno-imya") for i in range(50)]))
        assert len(итог) == 50
        assert len(set(итог.values())) == 50, "потерянных адресов быть не должно"


class TestРаботающиеСсылкиНеЛомаются:
    def test_уже_выданный_адрес_остаётся(self):
        registry = RouteRegistry("lords-01")
        первый = registry.assign(кандидаты(("p:a", "film"), ("p:b", "film")))
        второй = registry.assign(кандидаты(("p:a", "film"), ("p:b", "film")))
        assert первый == второй

    def test_чужой_адрес_не_отбирается_даже_по_справедливости(self):
        """Владелец `X-2` сохраняет его, даже если «по имени» адрес чужой.

        Это прямое требование: работающая ссылка важнее стройности схемы.
        """
        registry = seed_from_live("lords-01", {"p:squatter": "avatar-korolya-2"})
        итог = registry.assign(
            кандидаты(("p:squatter", "avatar-korolya"), ("p:rightful", "avatar-korolya-2"))
        )
        assert итог["p:squatter"] == "avatar-korolya-2"
        assert итог["p:rightful"].startswith("avatar-korolya-2" + SEPARATOR)

    def test_переименование_тайтла_адрес_не_двигает(self):
        """Слаг — представление, личность несёт content_id.

        Поставщик переименовал тайтл — ссылка, которую кто-то сохранил, обязана
        продолжать работать. Совпадение адреса с текущим названием этого не
        стоит.
        """
        registry = RouteRegistry("lords-01")
        registry.assign(кандидаты(("p:a", "film")))
        registry.assign(кандидаты(("p:a", "kino")))
        assert registry.path_for("p:a") == "film"
        assert registry.route_for("p:a").route_version == 1

    def test_намеренный_перенос_оставляет_перенаправление(self):
        """Миграция адресов бывает нужна — но делается явно, а не переименованием."""
        registry = RouteRegistry("lords-01")
        registry.assign(кандидаты(("p:a", "film")))
        registry.move("p:a", "kino")
        route = registry.route_for("p:a")
        assert route.canonical_path == "kino"
        assert "film" in route.legacy_paths
        assert route.route_version == 2
        assert registry.redirects()["film"] == "kino"

    def test_перенос_на_занятый_адрес_отклоняется(self):
        registry = RouteRegistry("lords-01")
        registry.assign(кандидаты(("p:a", "film"), ("p:b", "kino")))
        with pytest.raises(RouteError, match="принадлежит"):
            registry.move("p:a", "kino")

    def test_перенос_несуществующего_отклоняется(self):
        with pytest.raises(RouteError, match="нечего переносить"):
            RouteRegistry("s").move("p:нет", "kuda")


class TestПорядокОбходаНеВлияет:
    def test_обратный_порядок_даёт_те_же_адреса(self):
        пары = [(f"p:{i}", "odno") for i in range(20)]
        прямо = RouteRegistry("s").assign(кандидаты(*пары))
        обратно = RouteRegistry("s").assign(кандидаты(*reversed(пары)))
        assert прямо == обратно

    def test_перемешанный_порядок_даёт_те_же_адреса(self):
        import random

        пары = [(f"p:{i}", f"группа-{i % 4}") for i in range(40)]
        эталон = RouteRegistry("s").assign(кандидаты(*пары))
        for семя in (1, 2, 3):
            перемешано = list(пары)
            random.Random(семя).shuffle(перемешано)
            assert RouteRegistry("s").assign(кандидаты(*перемешано)) == эталон

    def test_различающая_часть_зависит_только_от_личности(self):
        assert discriminator("p:a") == discriminator("p:a")
        assert discriminator("p:a") != discriminator("p:b")


class TestПовторныйИмпорт:
    def test_не_создаёт_нового_адреса(self):
        registry = RouteRegistry("s")
        первый = registry.assign(кандидаты(("p:a", "film"), ("p:b", "film")))
        for _ in range(5):
            assert registry.assign(кандидаты(("p:a", "film"), ("p:b", "film"))) == первый
        assert all(r.route_version == 1 for r in registry)

    def test_новая_запись_не_трогает_прежние(self):
        registry = RouteRegistry("s")
        было = registry.assign(кандидаты(("p:a", "film"), ("p:b", "film")))
        стало = registry.assign(кандидаты(("p:a", "film"), ("p:b", "film"), ("p:c", "film")))
        assert стало["p:a"] == было["p:a"]
        assert стало["p:b"] == было["p:b"]
        assert стало["p:c"] not in (было["p:a"], было["p:b"])


class TestБудущаяКоллизия:
    def test_новая_искусственная_коллизия_разрешается(self):
        """Регрессия: тот же случай, но введённый заново."""
        registry = RouteRegistry("s")
        registry.assign(кандидаты(("p:one", "serial"), ("p:two", "serial")))
        # Появляется тайтл, чьё имя даёт адрес, уже занятый суффиксом.
        итог = registry.assign(
            кандидаты(("p:one", "serial"), ("p:two", "serial"), ("p:three", "serial-2"))
        )
        assert len(set(итог.values())) == 3
        assert итог["p:three"] not in (итог["p:one"], итог["p:two"])

    def test_двойное_назначение_адреса_отклоняется(self):
        registry = RouteRegistry("s")
        registry.assign(кандидаты(("p:a", "film")))
        with pytest.raises(RouteError, match="уже принадлежит"):
            registry._register(
                Route(content_id="p:b", site_id="s", canonical_path="film",
                      collision_group="film")
            )


class TestХранение:
    def test_реестр_переживает_запись_и_чтение(self, tmp_path: Path):
        registry = RouteRegistry("lords-01")
        было = registry.assign(кандидаты(("p:a", "film"), ("p:b", "film")))
        файл = registry.save(tmp_path / "routes.json")
        снова = RouteRegistry.load(файл)
        assert снова.site_id == "lords-01"
        assert {r.content_id: r.canonical_path for r in снова} == было

    def test_запись_атомарна(self, tmp_path: Path):
        """Оборванная запись реестра оставила бы витрину без адресов."""
        registry = RouteRegistry("s")
        registry.assign(кандидаты(("p:a", "film")))
        путь = registry.save(tmp_path / "routes.json")
        assert not list(tmp_path.glob("*.tmp")), "временный файл обязан исчезнуть"
        assert json.loads(путь.read_text(encoding="utf-8"))["routes"]

    def test_чужая_версия_схемы_отклоняется(self, tmp_path: Path):
        файл = tmp_path / "routes.json"
        файл.write_text(json.dumps({"schema_version": "0.9", "site_id": "s", "routes": []}),
                        encoding="utf-8")
        with pytest.raises(RouteError, match="ожидается"):
            RouteRegistry.load(файл)

    def test_отсутствующий_файл_даёт_пустой_реестр(self, tmp_path: Path):
        assert len(RouteRegistry.load(tmp_path / "нет.json", "s")) == 0


class TestЗапросы:
    def test_адрес_неизвестной_записи_это_отказ(self):
        """Молчаливый None привёл бы к ссылке в никуда."""
        with pytest.raises(RouteError, match="не назначен"):
            RouteRegistry("s").path_for("p:нет")

    def test_владелец_адреса_известен(self):
        registry = RouteRegistry("s")
        registry.assign(кандидаты(("p:a", "film")))
        assert registry.owner_of("film") == "p:a"
        assert registry.owner_of("нет-такого") is None
