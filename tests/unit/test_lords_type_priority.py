"""Порядок типов на главной — решение профиля, а не одного общего перечня.

`content_types.CONTENT_TYPES` задаёт порядок по умолчанию: фильмы, сериалы,
мультфильмы, аниме, дорамы. До этой правки `render_site` брал его напрямую —
единственный порядок один на все витрины. Для Lords это устраивало (витрина
ведёт фильмами и сериалами), но `sites/animedia-preview` заведён обратным:
его собственный `navigation.primary` и текст `purpose` профиля
`animedia-portal` называют аниме первым, а раздел «type_rows» (когда он
включён) всё равно рисовал бы фильмы выше — порядок одной витрины решал бы
за другую.

Правило: приоритет объявляется в `layout.type_priority` профиля блюпринта.
Без объявления действует прежний порядок по умолчанию — ничей вид не меняется
молча.
"""
from __future__ import annotations

from factory.lords import content_types as ct
from factory.lords import fixtures as fx
from factory.lords import preview as preview_mod
from factory.lords import render as render_mod


def _states(active: dict[str, bool]) -> dict[str, ct.TypeState]:
    return {
        name: ct.TypeState(
            name=name, state=ct.ENABLED if active.get(name) else ct.DISABLED_BY_CONFIG,
            reason="test",
        )
        for name in ct.CONTENT_TYPES
    }


class TestActiveTypesОбщийПорядок:
    def test_без_приоритета_порядок_по_умолчанию(self):
        states = _states({"movies": True, "series": True, "anime": True})
        assert ct.active_types(states) == ["movies", "series", "anime"]

    def test_свой_приоритет_переставляет_порядок(self):
        states = _states({"movies": True, "series": True, "anime": True})
        order = ct.active_types(states, order=("anime", "series", "movies"))
        assert order == ["anime", "series", "movies"]

    def test_неактивный_тип_не_появляется_даже_если_назван_в_приоритете(self):
        states = _states({"movies": True, "anime": True})
        order = ct.active_types(states, order=("anime", "series", "movies"))
        assert order == ["anime", "movies"], "dorama/series не включены — им неоткуда взяться"

    def test_тип_вне_приоритета_не_теряется_а_идёт_следом(self):
        # Профиль объявляет только то, что для него важно; остальное не пропадает.
        states = _states({"movies": True, "series": True, "animation": True})
        order = ct.active_types(states, order=("series",))
        assert order == ["series", "movies", "animation"], (
            "типы, не упомянутые в приоритете, обязаны идти следом в порядке "
            "по умолчанию, а не исчезать"
        )

    def test_пустой_приоритет_равен_отсутствию_приоритета(self):
        states = _states({"movies": True, "anime": True})
        assert ct.active_types(states, order=()) == ct.active_types(states, order=None)


class TestПрофильОбъявляетСвойПорядок:
    """Проверка на уровне собранного сайта: порядок берётся из manifest'а
    профиля, а не пересчитывается заново для каждой витрины."""

    def _kinds(self, site_id: str, *, declared_types: dict[str, bool]) -> list[str]:
        package, _ = preview_mod._package(site_id)
        package = dict(package)
        package["content_types"] = declared_types
        site = render_mod.render_site(package, catalog=fx.build_catalog(), environ={})
        return site.report["active_types"]

    def test_lords_ведёт_фильмами_и_сериалами_даже_при_включённом_аниме(self):
        # lords-02 использует профиль lords-new: type_priority объявлен явно
        # (фильмы, сериалы, мультфильмы, аниме, дорамы), поэтому включение
        # аниме в manifest не должно вывести его выше фильмов.
        kinds = self._kinds("lords-02", declared_types={
            "movies": True, "series": True, "animation": True,
            "anime": True, "dorama": True, "collections": False,
        })
        assert kinds.index("movies") < kinds.index("anime")
        assert kinds.index("series") < kinds.index("anime")
        assert kinds.index("movies") < kinds.index("dorama")
        assert kinds.index("series") < kinds.index("dorama")

    def test_animedia_ведёт_аниме_даже_при_включённых_фильмах(self):
        kinds = self._kinds("animedia-preview", declared_types={
            "movies": True, "series": True, "animation": True,
            "anime": True, "dorama": False, "collections": True,
        })
        assert kinds[0] == "anime", (
            f"Animedia заведён ради аниме (purpose профиля animedia-portal): "
            f"порядок {kinds} ставит впереди что-то другое"
        )

    def test_приоритет_одного_профиля_не_переставляет_другой(self):
        # Смена порядка в animedia-portal не должна была задеть lords-new —
        # profiles.yaml независимы, но регресс, объединяющий их через общий
        # ct.CONTENT_TYPES, был бы виден только тут.
        lords_kinds = self._kinds("lords-02", declared_types={
            "movies": True, "series": True, "animation": True,
            "anime": True, "dorama": False, "collections": False,
        })
        assert lords_kinds[0] == "movies"


class TestТипПриоритетаВПрофилях:
    # Профили направления Lords, которым принадлежит sites/lords-02 (Lords
    # site 33 по домену lordserial33.biz — config/FLEET-REGISTRY.json) через
    # tenant.seo_profile: lords-new. lords-general/lords-curated — соседние
    # профили того же направления и того же правила. zona-cinema использует
    # ту же вёрстку, но принадлежит другому направлению и в эту задачу не
    # входит — трогать его манифест здесь не за чем.
    LORDS_PROFILES = ("lords-new", "lords-general", "lords-curated")

    def test_lords_профили_с_type_rows_объявляют_приоритет(self):
        profiles = render_mod.plan_mod.load_profiles()
        for name in self.LORDS_PROFILES:
            layout = profiles[name].get("layout") or {}
            assert "type_rows" in (layout.get("home_blocks") or []), (
                f"профиль {name} ожидался с блоком type_rows — иначе приоритет типов"
                " на нём не проверить"
            )
            priority = layout.get("type_priority") or []
            assert priority, f"профиль {name} рисует type_rows без объявленного приоритета"
            movies_pos = priority.index("movies") if "movies" in priority else -1
            anime_pos = priority.index("anime") if "anime" in priority else len(priority)
            dorama_pos = priority.index("dorama") if "dorama" in priority else len(priority)
            assert movies_pos < anime_pos, f"{name}: фильмы не впереди аниме в type_priority"
            assert movies_pos < dorama_pos, f"{name}: фильмы не впереди дорам в type_priority"

    def test_animedia_portal_объявляет_аниме_первым(self):
        profiles = render_mod.plan_mod.load_profiles()
        priority = (profiles["animedia-portal"].get("layout") or {}).get("type_priority") or []
        assert priority and priority[0] == "anime"
