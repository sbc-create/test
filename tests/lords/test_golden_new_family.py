"""Золотая фикстура: новое семейство подключается данными, а не кодом.

Вопрос, на который отвечает этот тест, один: нужно ли трогать общий
отрисовщик, чтобы добавить витрину с другой раскладкой. Если нужно — никакой
основы для следующих семейств нет, есть только Lords и его копии.

Проверка идёт через настоящую загрузку профилей из каталога blueprint:
фикстура кладёт НОВЫЙ профиль рядом с существующими во временном корне и
собирает по нему сайт тем же `render_site`. Ни одной правки кода при этом
не делается, и ни одного условия по имени витрины в отрисовщике нет.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil

import pytest
import yaml

from factory.lords import fixtures as fx
from factory.lords import plan as plan_mod
from factory.lords import render as render_mod
from factory.lords import theme as theme_mod

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПРОФИЛИ = КОРЕНЬ / "blueprints" / "lords" / "profiles"

#: Токены выдуманного семейства. Намеренно НЕ совпадают ни с Lords, ни с
#: Zona: совпадение скрыло бы, читается ли профиль вообще.
ТОКЕНЫ_НОВОГО = {
    "bg": "#0a0f1a", "surface": "#111a2b", "surface_alt": "#16233a",
    "text": "#e8eef7", "muted": "#8ea0bb", "accent": "#ffb020",
    "accent_text": "#10151f", "border": "#243248", "radius": "14px",
    "container": "960px", "gutter": "24px", "gutter_wide": "32px",
    "gutter_mode": "margin", "header_min_height": "88px",
    "header_position": "static", "header_search": "inline",
    "button_size": "1.25rem", "button_weight": "700",
    "button_line_height": "48px",
    "heading_font": "'Open Sans', 'Segoe UI', Roboto, Arial, sans-serif",
    "h1_size": "1.5rem", "h2_size": "1.2rem",
}


@pytest.fixture(scope="module")
def временный_корень(tmp_path_factory) -> pathlib.Path:
    """Копия каталога профилей плюс один новый профиль."""
    корень = tmp_path_factory.mktemp("новое-семейство")
    куда = корень / "blueprints" / "lords" / "profiles"
    куда.mkdir(parents=True)
    # Новое семейство — СВОЙ blueprint, а не сосед по владению разделами.
    #
    # Первая версия фикстуры копировала все профили Lords рядом, и сборка
    # отказала: раздел caталога оказался объявлен во владении дважды. Отказ
    # верный — владелец раздела обязан быть один, — и он же показывает, что
    # подключение семейства это не «добавить файл к чужим», а отдельный
    # blueprint с собственным владением.
    shutil.copy(КОРЕНЬ / "blueprints" / "lords" / "blueprint.yaml",
                куда.parent / "blueprint.yaml")
    образец = yaml.safe_load((ПРОФИЛИ / "lords-general.yaml").read_text("utf-8"))
    новый = dict(образец)
    новый["profile"] = "nova-demo"
    новый["label"] = "Nova Demo"
    новый["purpose"] = "Golden fixture: новое семейство подключается манифестом."
    новый["theme"] = {"name": "lords_dark", "tokens": dict(ТОКЕНЫ_НОВОГО)}
    # Семейство владеет ВСЕМИ разделами своего blueprint: у каждого раздела
    # обязан быть ровно один владелец, и в одиночном профиле это он.
    import yaml as _yaml
    оснастка = _yaml.safe_load(
        (КОРЕНЬ / "blueprints" / "lords" / "blueprint.yaml").read_text("utf-8"))
    разделы = [с.get("id") if isinstance(с, dict) else с
               for с in (оснастка.get("sections") or [])]
    новый["owns"] = [с for с in разделы if с and с != "home"]
    новый["owns_title_page"] = True
    (куда / "nova-demo.yaml").write_text(
        yaml.safe_dump(новый, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return корень


@pytest.fixture(scope="module")
def профиль_нового(временный_корень) -> dict:
    профили = plan_mod.load_profiles(временный_корень)
    assert "nova-demo" in профили, "новый профиль не подхватился загрузчиком"
    return профили["nova-demo"]


class TestНовоеСемействоЧитается:
    def test_профиль_подхвачен_без_правки_кода(self, профиль_нового):
        assert профиль_нового["label"] == "Nova Demo"

    def test_валиден_по_схеме_манифеста(self, профиль_нового):
        import jsonschema
        схема = json.loads(
            (КОРЕНЬ / "schemas" / "template-manifest.schema.json").read_text("utf-8"))
        jsonschema.validate(профиль_нового, схема)

    def test_токены_попадают_в_таблицу_стилей(self, профиль_нового):
        css = theme_mod.stylesheet(профиль_нового)
        assert "--container: 960px;" in css
        assert "--gutter: 24px;" in css
        assert "--header-min-h: 88px;" in css
        assert "--btn-size: 1.25rem;" in css
        assert "position: static;" in css

    def test_раскладка_отличается_от_lords(self, профиль_нового):
        lords = theme_mod.stylesheet(
            yaml.safe_load((ПРОФИЛИ / "lords-general.yaml").read_text("utf-8")))
        новое = theme_mod.stylesheet(профиль_нового)
        assert lords != новое
        assert "--container: 1100px;" in lords
        assert "--container: 960px;" in новое

    def test_режим_отступа_читается(self, профиль_нового):
        css = theme_mod.stylesheet(профиль_нового)
        assert "width: calc(100% - 2 * var(--gutter))" in css


class TestОбщийКодНеЗнаетИмёнВитрин:
    ОБЩИЕ = ("factory/lords/render.py", "factory/lords/theme.py",
             "factory/lords/plan.py")
    ИМЕНА = ("lords-general", "lords-new", "lords-curated", "zona-cinema",
             "animedia-portal", "nova-demo")

    @staticmethod
    def _только_код(путь: pathlib.Path) -> list[tuple[int, str]]:
        """Исходник без строк и комментариев.

        Имя витрины в объяснении — это объяснение. Ветвлением оно становится
        только в коде, и отличить одно от другого построчным поиском нельзя:
        строка документации занимает много строк и ни одна из них не
        начинается с решётки.
        """
        import io
        import tokenize
        код = []
        with open(путь, "rb") as ф:
            for лексема in tokenize.tokenize(ф.readline):
                if лексема.type in (tokenize.COMMENT, tokenize.STRING,
                                    tokenize.NL, tokenize.NEWLINE,
                                    tokenize.INDENT, tokenize.DEDENT,
                                    tokenize.ENCODING, tokenize.ENDMARKER):
                    continue
                код.append((лексема.start[0], лексема.string))
        return код

    def test_нет_условий_по_имени_витрины(self):
        найдено = []
        for путь in self.ОБЩИЕ:
            for строка, лексема in self._только_код(КОРЕНЬ / путь):
                for имя in self.ИМЕНА:
                    if имя in лексема:
                        найдено.append(f"{путь}:{строка}: {лексема[:60]}")
        assert найдено == [], (
            "общий код ветвится по имени витрины — значит новое семейство "
            f"потребует правки кода: {найдено[:3]}")


class TestНовоеСемействоРисуется:
    def test_страницы_собираются_тем_же_рендерером(self, временный_корень,
                                                   профиль_нового):
        каталог = fx.build_catalog()
        пакет = {
            "site_id": "nova-demo-01",
            "tenant": {"brand": "Nova Demo", "theme": "lords_dark",
                       "seo_profile": "nova-demo", "locale": "ru-RU"},
            "domain": "nova-demo.invalid",
        }
        сайт = render_mod.render_site(пакет, catalog=каталог, environ={},
                                      publisher_id="1", root=временный_корень)
        assert сайт.pages, "новое семейство не дало ни одной страницы"
        assert "/" in сайт.pages
        css = сайт.assets.get("/assets/site.css") if hasattr(сайт, "assets") else None
        if css is not None:
            тело = css.body if hasattr(css, "body") else css
            assert "--container: 960px;" in (тело if isinstance(тело, str)
                                             else тело.decode("utf-8"))
