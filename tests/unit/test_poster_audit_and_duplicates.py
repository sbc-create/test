"""Постеры: счётчик не запрашивается, дубли считаются по содержимому.

Два инструмента, два свойства, которые нельзя терять.

1. `poster-delivery-audit.py` обходит страницы витрин, а в разметке стоит
   пиксель Метрики (`<img src="https://mc.yandex.ru/watch/…">`). Технический
   обход, запросивший его, запишет визит, которого не было, и испортит те самые
   данные, по которым потом считают трафик. Поэтому адрес счётчика не должен
   запрашиваться НИКОГДА — и это проверяется на вызове, а не на глаз.

2. `image-duplicate-census.py` считает точные дубли. Одинаковый размер — ещё не
   дубль, жёсткая ссылка — не вторая копия, а резервная копия не становится
   ненужной из-за совпадения содержимого. Каждое из трёх свойств закреплено
   отдельной проверкой: без них «освобождаемый объём» был бы завышен.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]


def _модуль(имя: str, файл: str):
    путь = КОРЕНЬ / "automation" / "local" / файл
    спец = importlib.util.spec_from_file_location(имя, путь)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


АУДИТ = _модуль("poster_delivery_audit", "poster-delivery-audit.py")
ПЕРЕПИСЬ = _модуль("image_duplicate_census", "image-duplicate-census.py")


# --- счётчики --------------------------------------------------------------

def test_адрес_счётчика_не_запрашивается(monkeypatch):
    """Метрика не должна получить ни одного технического просмотра."""
    вызовы = []

    def подмена(команда, **прочее):
        вызовы.append(команда)
        raise AssertionError("сеть не должна быть затронута для счётчика")

    monkeypatch.setattr(АУДИТ.subprocess, "run", подмена)
    итог = АУДИТ.изображение("https://mc.yandex.ru/watch/113288667", "агент")
    assert итог["ок"] is False
    assert "счётчик" in итог["почему"], итог
    assert вызовы == [], "был сетевой вызов к адресу счётчика"


def test_счётчик_узнаётся_по_хосту_а_не_по_точному_адресу():
    """Форма адреса меняется, хост — нет."""
    for адрес in ("https://mc.yandex.ru/watch/1",
                  "http://MC.YANDEX.RU/watch/2?x=1",
                  "https://www.googletagmanager.com/gtag/js"):
        assert АУДИТ.счётчик(адрес), адрес
    for адрес in ("https://poster.cdnvideohub.com/01a1.webp",
                  "https://animedia.icu/poster/01a1.webp"):
        assert not АУДИТ.счётчик(адрес), адрес


def test_пиксель_счётчика_не_попадает_в_перечень_постеров():
    """Отбор постеров обязан выбросить счётчик ещё до сети."""
    html = ('<img src="https://mc.yandex.ru/watch/113288667" alt="">'
            '<img class="zt__img" src="/poster/01a1.webp" alt="Птицы"'
            ' width="190" height="285" data-poster>')
    найдено = АУДИТ.постеры_страницы(html, 10)
    assert [п["src"] for п in найдено] == ["/poster/01a1.webp"], найдено
    assert найдено[0]["признак"] == "атрибут data-poster"


def test_признак_отбора_называется_а_не_угадывается():
    """По признаку видно, на чём основан отбор: ошибку отбора можно отличить."""
    assert АУДИТ.постер_ли({"src": "/poster/x.webp"}) == "адрес постера"
    assert АУДИТ.постер_ли(
        {"src": "/i/x.webp", "alt": "Постер аниме «Х»"}) == "подпись «постер»"
    assert АУДИТ.постер_ли(
        {"src": "/i/x.webp", "width": "190",
         "height": "285"}) == "вертикальное соотношение в разметке"
    assert АУДИТ.постер_ли({"src": "/brand/logo.svg", "width": "243",
                            "height": "85"}) == ""


# --- дубли -----------------------------------------------------------------

def _файл(путь: pathlib.Path, данные: bytes) -> None:
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_bytes(данные)


def _перепись(tmp_path, аргв: list[str]) -> str:
    г = subprocess.run([sys.executable,
                        str(КОРЕНЬ / "automation/local/image-duplicate-census.py"),
                        *аргв], capture_output=True, text=True, timeout=180)
    return г.stdout


def test_одинаковый_размер_но_разное_содержимое_не_дубль(tmp_path):
    """Контроль: без сумм инструмент насчитал бы дубль там, где его нет."""
    _файл(tmp_path / "a.webp", b"A" * 4096)
    _файл(tmp_path / "b.webp", b"B" * 4096)
    вывод = _перепись(tmp_path, ["--root", str(tmp_path)])
    assert "групп точных дублей: 0" in вывод, вывод


def test_точный_дубль_находится(tmp_path):
    _файл(tmp_path / "a.webp", b"X" * 4096)
    _файл(tmp_path / "копия/a-other-name.webp", b"X" * 4096)
    вывод = _перепись(tmp_path, ["--root", str(tmp_path)])
    assert "групп точных дублей: 1" in вывод, вывод


def test_жёсткая_ссылка_считается_одним_файлом(tmp_path):
    """Один файл, видимый по двум путям, занимает место ОДИН раз."""
    первый = tmp_path / "a.webp"
    _файл(первый, b"Y" * 8192)
    os.link(первый, tmp_path / "b.webp")
    вывод = _перепись(tmp_path, ["--root", str(tmp_path)])
    assert "ОДИН файл, видимый дважды" in вывод
    assert "1 вхождений" in вывод, вывод
    assert "групп точных дублей: 0" in вывод, вывод


def test_резервная_копия_не_считается_освобождаемой(tmp_path):
    """Совпадение содержимого не делает резервную копию ненужной."""
    _файл(tmp_path / "live/a.webp", b"Z" * 4096)
    _файл(tmp_path / "backups/a.webp", b"Z" * 4096)
    вывод = _перепись(tmp_path, ["--root", str(tmp_path)])
    assert "РЕАЛИСТИЧНО освобождаемое: 0.00 ГиБ" in вывод, вывод
    assert "УДАЛИТЬ ДОПУСТИМО: 0.00 ГиБ (0 файлов)" in вывод, вывод


def test_назначение_определяется_по_пути():
    assert ПЕРЕПИСЬ.назначение("/x/publish-backups/a.webp") == "резервная копия"
    assert ПЕРЕПИСЬ.назначение(
        "/x/artifacts/evidence/a.webp") == "доказательство проверки"
    assert ПЕРЕПИСЬ.назначение("/srv/s/releases/ab/a.webp") == "каталог релиза"
    assert ПЕРЕПИСЬ.назначение("/var/cache/nginx/x/a.webp") == "кеш"
    assert ПЕРЕПИСЬ.назначение("/home/claude/wt-abc/a.webp") == "рабочая копия сессии"


# --- зависимость от PIL ----------------------------------------------------

def test_без_pil_опыт_отказывает_понятно():
    """Отказ обязан называть место установки, а не только ошибку импорта.

    Повод измеренный, 23.10: соседняя линия выпустила уменьшение обложек и
    получила ноль эффекта — Pillow стоит в каталоге ПОЛЬЗОВАТЕЛЯ, а системный
    python3 службы его не видит. Та же зависимость у моих инструментов, и под
    `python3 -s` опыт сжатия падал traceback-ом. Проверяется ПОВЕДЕНИЕ:
    инструмент запускается интерпретатором без пользовательского каталога.
    """
    г = subprocess.run(
        [sys.executable, "-s",
         str(КОРЕНЬ / "automation/local/poster-recompress-trial.py"),
         "--from-csv", str(КОРЕНЬ / "artifacts/evidence/posters"
                           / "poster-delivery-20261023.csv"),
         "--limit", "1"],
        capture_output=True, text=True, timeout=180)
    assert "Traceback" not in г.stderr, г.stderr[-400:]
    assert "НЕ ИЗМЕРЕНО" in г.stdout, г.stdout
    assert "каталоге пользователя" in г.stdout, г.stdout
    assert г.returncode == 2, г.returncode


def test_без_pil_опись_называет_причину_один_раз():
    """Одна громкая строка вместо шести одинаковых отказов в строках."""
    г = subprocess.run(
        [sys.executable, "-s",
         str(КОРЕНЬ / "automation/local/poster-delivery-audit.py"),
         "--domain", "example.invalid", "--per-page", "1"],
        capture_output=True, text=True, timeout=180)
    assert "Traceback" not in г.stderr, г.stderr[-400:]
    assert "ВНИМАНИЕ: пиксели измерены НЕ БУДУТ" in г.stdout, г.stdout
    assert "каталоге пользователя" in г.stdout, г.stdout
