"""SUITE_7 — переезды адресов: один шаг, живая цель, без петель.

Адрес меняет владельца, когда прежнее правило отдавало его не тому, кто
назван в его названии. Содержимое при этом не исчезает — оно переезжает, и
читателя надо привести к нему. Проверяется именно это, а не наличие файла.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from factory.lords import serve as serve_mod
from factory.lords import urlmap as um

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
КОРЕНЬ_СБОРОК = КОРЕНЬ / "var" / "build-a"
ВИТРИНЫ = ("zona-cinema", "animedia-portal", "lords-02")


@pytest.fixture(scope="module", params=ВИТРИНЫ)
def витрина(request):
    путь = КОРЕНЬ_СБОРОК / request.param
    if not (путь / "redirects.json").is_file():
        pytest.skip(f"сборки с переездами нет: {путь}")
    карта = json.loads((путь / "route-map.json").read_text("utf-8"))["routes"]
    переезды = json.loads((путь / "redirects.json").read_text("utf-8"))
    return {"root": путь, "routes": {f"/title/{с}/" for с in карта},
            "moved": переезды["moved"], "tombstones": переезды["tombstones"]}


class TestФормаПереездов:
    def test_источник_переезда_не_является_собранной_страницей(self, витрина):
        """Иначе это не переезд, а подмена живой страницы."""
        лишние = [а for а in витрина["moved"] if а in витрина["routes"]]
        assert лишние == [], f"переезд с живого адреса: {лишние[:5]}"

    def test_цель_переезда_собрана(self, витрина):
        мимо = [ц for ц in витрина["moved"].values() if ц not in витрина["routes"]]
        assert мимо == [], f"переезд ведёт в никуда: {мимо[:5]}"

    def test_цепочек_нет(self, витрина):
        цепочки = [(а, ц) for а, ц in витрина["moved"].items()
                   if ц in витрина["moved"]]
        assert цепочки == [], f"переход больше одного шага: {цепочки[:3]}"

    def test_петель_нет(self, витрина):
        петли = [а for а, ц in витрина["moved"].items() if а == ц]
        assert петли == []

    def test_адреса_канонического_вида(self, витрина):
        for а, ц in витрина["moved"].items():
            assert um.нормализовать(а) == а
            assert um.нормализовать(ц) == ц

    def test_надгробия_названы_с_причиной(self, витрина):
        for н in витрина["tombstones"]:
            assert н.get("reason"), f"надгробие без причины: {н}"
            assert н["path"] not in витрина["routes"]


class TestРантаймОтдаётПереезд:
    """Проверяется поведение приложения, а не содержимое файла."""

    class ЗаглушкаСтраницы:
        status = 200
        content_type = "text/html; charset=utf-8"
        body = "<html><h1>Цель</h1></html>"

    class ЗаглушкаСайта:
        def __init__(self, pages):
            self.pages = pages
            self.not_found = None

    def приложение(self, переезды):
        сайт = self.ЗаглушкаСайта({"/title/cel/": self.ЗаглушкаСтраницы()})
        return serve_mod.Application(сайт, redirects=переезды)

    def test_переезд_отдаёт_308_на_цель(self):
        п = self.приложение({"/title/staryy/": "/title/cel/"})
        ответ = п.handle("GET", "/title/staryy/")
        assert ответ.status == 308
        assert dict(ответ.headers)["Location"] == "/title/cel/"

    def test_переезд_ровно_один_шаг(self):
        п = self.приложение({"/title/staryy/": "/title/cel/"})
        первый = п.handle("GET", "/title/staryy/")
        цель = dict(первый.headers)["Location"]
        второй = п.handle("GET", цель)
        assert второй.status == 200, "цель переезда сама оказалась переездом"

    def test_переезд_на_несобранную_страницу_не_выдаётся(self):
        """Переход в никуда — это 404 через лишний шаг, и хуже честного 404."""
        п = self.приложение({"/title/staryy/": "/title/net-takoy/"})
        assert п.handle("GET", "/title/staryy/").status == 404

    def test_цепочка_не_выдаётся(self):
        п = self.приложение({"/title/a/": "/title/b/", "/title/b/": "/title/cel/"})
        assert п.handle("GET", "/title/a/").status == 404

    def test_неизвестный_адрес_остаётся_честным_404(self):
        п = self.приложение({"/title/staryy/": "/title/cel/"})
        assert п.handle("GET", "/title/nikogda-ne-bylo/").status == 404

    def test_ложного_200_нет(self):
        п = self.приложение({"/title/staryy/": "/title/cel/"})
        assert п.handle("GET", "/title/staryy/").status != 200


class TestЗагрузкаИзКаталога:
    def test_файла_нет_значит_переездов_нет(self, tmp_path):
        assert serve_mod.переезды_из_каталога(tmp_path) == {}

    def test_битый_файл_не_роняет_рантайм(self, tmp_path):
        (tmp_path / serve_mod.ПЕРЕЕЗДЫ).write_text("{не json", encoding="utf-8")
        assert serve_mod.переезды_из_каталога(tmp_path) == {}

    def test_читается_собранная_витрина(self, витрина):
        загружено = serve_mod.переезды_из_каталога(витрина["root"])
        assert загружено == витрина["moved"]
