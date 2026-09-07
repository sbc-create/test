"""Окружение стенда одно на всех, кто его поднимает.

Три инструмента задавали его каждый своей копией, и копии уже разошлись: у
`browser_multisite` было заведомо поддельное значение токена и порт, у
`cross_site_uniqueness` и `frontend_http` — нет. Дальше расходиться им ничто не
мешало.

Цена расхождения не теоретическая: проверки пошли бы по разным настройкам,
объявляя проверенным одно и то же поведение. А проверка «токен Content API не
попадает в страницу» существует ровно одна —
`tests/e2e-multisite/player.spec.js` — и она требует, чтобы значение в
окружении было непустым. Убрать его из общего умолчания и не заметить значило
бы получить падение там, где никто не менял ни страницу, ни плеер.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import stand_env  # noqa: E402

ИНСТРУМЕНТЫ = ("browser_multisite.py", "cross_site_uniqueness.py", "frontend_http.py")


class TestКопийБольшеНет:
    @pytest.mark.parametrize("имя", ИНСТРУМЕНТЫ)
    def test_инструмент_не_держит_своей_копии(self, имя):
        текст = (ROOT / "tests" / "tools" / имя).read_text(encoding="utf-8")
        assert "PLAYER_PUBLISHER_ID_A" not in текст, (
            f"{имя}: собственная копия окружения стенда вернулась")

    @pytest.mark.parametrize("имя", ИНСТРУМЕНТЫ)
    def test_инструмент_берёт_общее(self, имя):
        текст = (ROOT / "tests" / "tools" / имя).read_text(encoding="utf-8")
        assert "stand_env.stand_environment(" in текст, имя


class TestСоставОкружения:
    def test_три_витрины_объявлены(self):
        assert set(stand_env.PUBLISHERS) == {
            "PLAYER_PUBLISHER_ID_A", "PLAYER_PUBLISHER_ID_B", "PLAYER_PUBLISHER_ID_C"}

    def test_значения_различны(self):
        """Одинаковые идентификаторы сделали бы проверку изоляции витрин пустой."""
        assert len(set(stand_env.PUBLISHERS.values())) == 3

    def test_плеер_в_поддельном_режиме(self):
        env = stand_env.stand_environment()
        assert env["PLAYER_MODE"] == "mock"
        assert env["FACTORY_ENVIRONMENT"] == "staging"

    def test_порт_добавляется_только_когда_назван(self):
        assert "FACTORY_MULTISITE_PORT" not in stand_env.stand_environment()
        assert stand_env.stand_environment(port=8123)["FACTORY_MULTISITE_PORT"] == "8123"


class TestПоддельныйТокен:
    def test_по_умолчанию_не_добавляется(self):
        """Значение в окружении не делает строже проверку, которая его не ищет."""
        env = stand_env.stand_environment()
        assert env.get("CDNVIDEOHUB_API_TOKEN") != stand_env.LEAK_CANARY_TOKEN

    def test_добавляется_по_запросу(self):
        env = stand_env.stand_environment(with_leak_canary=True)
        assert env["CDNVIDEOHUB_API_TOKEN"] == stand_env.LEAK_CANARY_TOKEN

    def test_значение_говорит_о_себе(self):
        """Поддельное значение обязано читаться как поддельное."""
        assert "must-not-leak" in stand_env.LEAK_CANARY_TOKEN
        assert "stand" in stand_env.LEAK_CANARY_TOKEN

    def test_проверка_утечки_существует_и_требует_значения(self):
        """Иначе включение канарейки — обряд без последствий."""
        spec = (ROOT / "tests" / "e2e-multisite" / "player.spec.js").read_text(encoding="utf-8")
        assert "CDNVIDEOHUB_API_TOKEN" in spec
        assert re.search(r"sentinel\s*&&\s*sentinel\.length\s*>\s*0", spec), (
            "проверка обязана падать на пустом значении, иначе она пройдёт и "
            "тогда, когда токена в окружении нет вовсе")

    def test_канарейку_включает_тот_кто_её_ищет(self):
        """`browser_multisite` запускает набор с проверкой утечки — он и включает."""
        multisite = (ROOT / "tests" / "tools" / "browser_multisite.py").read_text(encoding="utf-8")
        assert "with_leak_canary=True" in multisite
        for имя in ("cross_site_uniqueness.py", "frontend_http.py"):
            текст = (ROOT / "tests" / "tools" / имя).read_text(encoding="utf-8")
            assert "with_leak_canary" not in текст, имя
