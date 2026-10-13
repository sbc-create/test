"""Cross-site утечка — блокирующий пункт готовности, значит проверка повторяемая.

Определение готовности фабрики называет утечку отдельной строкой среди причин,
по которым нельзя ставить `DONE`. Поэтому признак живёт инструментом, а не
разовым замером, и у него проверяются оба исхода: чужой хост найден и чужого
хоста нет.

`www.<домен>` своим считается намеренно: это тот же сайт, и объявлять его
утечкой значило бы ломать работу правки www-зеркал.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "cross-site-leak-probe.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("cross_site_leak_probe", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def test_свой_хост_и_www_не_утечка():
    assert МОД.свой("zonafilm.space", "zonafilm.space")
    assert МОД.свой("www.zonafilm.space", "zonafilm.space")
    # Пустой хост — относительный адрес, он не может указывать на чужой сайт.
    assert МОД.свой("", "zonafilm.space")


def test_чужой_хост_это_утечка():
    assert not МОД.свой("zonafilm.cc", "zonafilm.space")
    assert not МОД.свой("lordfilm47.space", "zonafilm.space")
    # Похожий, но другой домен: подстрока не делает хост своим.
    assert not МОД.свой("zonafilm.space.evil.example", "zonafilm.space")
    assert not МОД.свой("notzonafilm.space", "zonafilm.space")


def test_места_поиска_названы_перечнем():
    """Признак, который ищет в одном месте, отвечает про место, а не про страницу."""
    имена = [имя for имя, _ in МОД.МЕСТА]
    assert "canonical" in имена and "og:url" in имена
    assert len(МОД.МЕСТА) == 2


def test_обе_формы_адреса_карточки_известны():
    assert МОД.ФОРМЫ_КАРТОЧКИ == ("/title/", "/anime/")


def test_предел_признака_назван_в_выводе():
    """Признак не видит подмену СОДЕРЖИМОГО при верном хосте, и говорит это."""
    текст = ПУТЬ.read_text(encoding="utf-8")
    assert "Подмену СОДЕРЖИМОГО при верном хосте он не" in текст
    assert "CSU-4" in текст or "B007" in текст


def test_зарезервированные_имена_не_обходятся():
    """RFC 6761: `.test` и `.localhost` публично не разрешаются."""
    assert all(not д.endswith((".test", ".localhost")) for д in МОД.домены())


def test_неполный_замер_называется_а_не_проходит():
    """Витрина, у которой карточку взять не с чего, не выдаётся за проверенную."""
    текст = ПУТЬ.read_text(encoding="utf-8")
    assert "неполные замеры" in текст
    assert "карточку взять не с чего" in текст
