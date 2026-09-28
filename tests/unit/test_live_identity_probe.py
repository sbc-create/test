"""Опознание витрины: три состояния, которые нельзя было различить.

Домен может не разрешаться в адрес. Может разрешаться, но не обслуживать
TLS. Может отвечать 200 и отдавать чужую страницу. Раньше всё это выглядело
одинаково — «сайт недоступен», — и владелец не узнал бы, чинить ему DNS,
сервер или выкладку.

Опознание нужно ещё и затем, чтобы приёмка не запустилась по адресу, который
отдаёт не нашу витрину: она измерила бы чужую работу и записала её в наш отчёт.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import live_identity_probe as probe  # noqa: E402


class TestРазметкаРендерераОпознаётся:
    def test_три_признака_объявлены(self):
        assert probe.MARKERS == ('data-block="', 'data-shelf="', 'data-algorithm="')

    def test_собранная_витрина_опознаётся_своей_же_разметкой(self):
        """Признаки берутся из настоящей сборки, а не выдуманы под проверку."""
        собранная = ROOT / "var" / "product-preview" / "zona-cinema" / "index.html"
        if not собранная.is_file():
            import pytest
            pytest.skip("сборки предпросмотра нет: признаки не на чем сверить")
        текст = собранная.read_text(encoding="utf-8")
        найдено = [m for m in probe.MARKERS if m in текст]
        assert len(найдено) >= 2, f"наша же сборка не опознаётся: найдено {найдено}"


class TestПредставлениеЧестное:
    def test_агент_не_выдаёт_себя_за_браузер(self):
        """Подделка клиента — обход различения, которое сайт вправе делать."""
        assert "Mozilla" not in probe.AGENT
        assert "read-only" in probe.AGENT

    def test_отказ_доступа_перечислен(self):
        assert probe.ОТКАЗ_ДОСТУПА == {401, 403, 429}


class TestРазрешениеИмени:
    def test_несуществующее_имя_не_разрешается(self):
        assert probe._resolve("не-существует.invalid") is None

    def test_существующее_имя_разрешается(self):
        """Проверка среды: без неё «не разрешается» ничего не доказывает."""
        assert probe._resolve("example.com") is not None
