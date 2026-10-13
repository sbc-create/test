"""Развод www-зеркала: блок 80 обязан сохранить `www.`, блок 443 — потерять.

Ловушка, ради которой сценарий существует. У `zona-02.conf` ДВА блока с
одинаковой строкой `server_name zonafilm.cc www.zonafilm.cc;`: порт 80 и порт
443. Из блока 80 имя `www.` убирать нельзя — именно он перенаправляет
`http://www` на https. Глобальная замена по файлу сломала бы это молча, замена
по номеру строки — при любой следующей правке файла.

Проверяется и прямое требование, и обратное: без второго проверка прошла бы и
на сценарии, который не меняет ничего.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "host"
        / "www-redirect" / "apply-www-split.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("apply_www_split", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()

ДВА_БЛОКА = """server {
    listen 80;
    listen [::]:80;
    server_name zonafilm.cc www.zonafilm.cc;
    return 301 https://zonafilm.cc$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name zonafilm.cc www.zonafilm.cc;
    location / { proxy_pass http://127.0.0.1:9120; }
}
"""


def _имена(текст: str) -> dict[str, list[str]]:
    """Порт → имена. Для файлов, где порты РАЗНЫЕ."""
    итог: dict[str, list[str]] = {}
    for порт, имена in _по_порядку(текст):
        итог[порт] = имена
    return итог


def _по_порядку(текст: str) -> list[tuple[str, list[str]]]:
    """(порт, имена) по каждому блоку, в порядке файла.

    Словарь по порту здесь не годится: у файла бывает ДВА блока на 443 —
    перенаправление с www и основной хост, — и второй затирал бы первый.
    Проверка, написанная на словаре, объявляла потерю блока там, где терял её
    сам помощник.
    """
    итог: list[tuple[str, list[str]]] = []
    for порт, начало, конец in МОД.блоки(текст):
        м = re.search(r"^\s*server_name\s+([^;]+);", текст[начало:конец], re.M)
        if м:
            итог.append((порт, м.group(1).split()))
    return итог


def test_блок_80_сохраняет_www_а_443_теряет():
    """Главное требование, и оно про ОБА блока сразу."""
    новый, что = МОД.убрать_www(ДВА_БЛОКА, "zonafilm.cc")
    assert "убрано www.zonafilm.cc" in что, что
    имена = _имена(новый)
    assert имена["80"] == ["zonafilm.cc", "www.zonafilm.cc"], имена
    assert имена["443"] == ["zonafilm.cc"], имена


def test_повторный_запуск_ничего_не_меняет():
    """Иначе второй прогон срезал бы основное имя."""
    один, _ = МОД.убрать_www(ДВА_БЛОКА, "zonafilm.cc")
    два, что = МОД.убрать_www(один, "zonafilm.cc")
    assert два == один
    assert "уже без www" in что, что


def test_блок_перенаправления_не_трогается():
    """У него `server_name` РОВНО www — это цель правки, а не остаток."""
    текст = """server {
    listen 443 ssl;
    server_name www.zonafilm.cc;
    return 301 https://zonafilm.cc$request_uri;
}

server {
    listen 443 ssl;
    server_name zonafilm.cc www.zonafilm.cc;
    location / { proxy_pass http://127.0.0.1:9120; }
}
"""
    новый, что = МОД.убрать_www(текст, "zonafilm.cc")
    assert "убрано" in что, что
    # Оба блока на 443: разбор пропускает чистый www и правит ИМЕННО основной.
    # Утверждение по РАЗОБРАННЫМ именам в порядке файла, а не по подстроке:
    # подстрока «www.zonafilm.cc» есть и в основном блоке до правки.
    блоки = _по_порядку(новый)
    assert блоки == [("443", ["www.zonafilm.cc"]), ("443", ["zonafilm.cc"])], блоки



def test_единственное_имя_www_это_отказ():
    """Правка не должна оставлять блок 443 без имён вовсе."""
    текст = """server {
    listen 443 ssl;
    server_name www.proba.example;
    location / { proxy_pass http://127.0.0.1:9999; }
}
"""
    новый, что = МОД.убрать_www(текст, "proba.example")
    # Тут `server_name` РОВНО www — это блок перенаправления, он пропускается.
    assert новый == текст
    assert "не найдено" in что or "уже без www" in что, что


def test_отсутствие_блока_443_называется_а_не_молчит():
    текст = """server {
    listen 80;
    server_name proba.example www.proba.example;
    return 301 https://proba.example$request_uri;
}
"""
    новый, что = МОД.убрать_www(текст, "proba.example")
    assert новый == текст
    assert "блока 443" in что, что


def test_перечень_целей_равен_набору_вставок():
    """Домен без готовой вставки сюда попасть не должен."""
    каталог = ПУТЬ.parent
    for файл, домен, вставка in МОД.ЦЕЛИ:
        assert файл.endswith(".conf"), файл
        assert (каталог / вставка).is_file(), вставка
        текст = (каталог / вставка).read_text(encoding="utf-8")
        assert f"www.{домен}" in текст, (вставка, домен)


def test_без_apply_ничего_не_меняется(tmp_path):
    """Показ по умолчанию: сценарий, который правит без флага, опасен."""
    import subprocess
    import sys
    (tmp_path / "zona-02.conf").write_text(ДВА_БЛОКА, encoding="utf-8")
    г = subprocess.run(
        [sys.executable, str(ПУТЬ), "--dir", str(tmp_path)],
        capture_output=True, text=True, timeout=120)
    assert г.returncode == 0, г.stdout + г.stderr
    assert "ничего не изменено" in г.stdout, г.stdout
    assert (tmp_path / "zona-02.conf").read_text(encoding="utf-8") == ДВА_БЛОКА


def test_каталога_нет_это_не_измерено(tmp_path):
    import subprocess
    import sys
    г = subprocess.run(
        [sys.executable, str(ПУТЬ), "--dir", str(tmp_path / "нет")],
        capture_output=True, text=True, timeout=120)
    assert г.returncode == 2, г.stdout
    assert "НЕ ИЗМЕРЕНО" in г.stdout, г.stdout
