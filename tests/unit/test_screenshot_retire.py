"""Снятие снимков: без сохранённого вида файлы не удаляются.

Требование владельца 23.10: «если важная информация существует только на
изображении, сначала сохрани и проверь её содержание; внешний вид страницы
одним текстом не заменяй». Инструмент `screenshot-retire.py` это исполняет:
пишет опись, сохраняет уменьшенный образец на каждый КАТАЛОГ прогона,
перечитывает образец и только потом удаляет.

Проверяется поведение на подготовленных каталогах, а не текст инструмента:
структурная проверка «в коде есть слово образец» прошла бы и на инструменте,
который удаляет первым.
"""
from __future__ import annotations

import csv
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "local" / "screenshot-retire.py"


def _png(путь: pathlib.Path, ширина: int = 40, высота: int = 60) -> None:
    from PIL import Image
    путь.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (ширина, высота), (30, 60, 90)).save(путь)


def _опись(tmp_path: pathlib.Path, файлы: list[pathlib.Path]) -> pathlib.Path:
    п = tmp_path / "census.csv"
    with п.open("w", newline="", encoding="utf-8") as ф:
        з = csv.DictWriter(ф, fieldnames=["путь", "байт", "группа", "почему"])
        з.writeheader()
        for ф_ in файлы:
            з.writerow({"путь": str(ф_), "байт": ф_.stat().st_size,
                        "группа": "к снятию", "почему": "проверка"})
    return п


def _прогон(*аргв: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ИНСТРУМЕНТ), *аргв],
                          capture_output=True, text=True, timeout=180)


def test_без_apply_не_удаляет_и_не_пишет_образцы(tmp_path):
    файл = tmp_path / "прогон" / "home.png"
    _png(файл)
    опись = _опись(tmp_path, [файл])
    образцы = tmp_path / "thumbs"
    г = _прогон("--census", str(опись), "--group", "к снятию",
                "--thumbs", str(образцы), "--manifest",
                str(tmp_path / "m.csv"))
    assert "НИЧЕГО НЕ УДАЛЕНО" in г.stdout, г.stdout
    assert файл.exists(), "файл удалён без --apply"
    assert not list(образцы.iterdir()), "образцы записаны без --apply"


def test_с_apply_сначала_образец_потом_удаление(tmp_path):
    каталог = tmp_path / "прогон"
    файлы = [каталог / f"home-{n}.png" for n in range(3)]
    for ф in файлы:
        _png(ф, 400, 600)
    опись = _опись(tmp_path, файлы)
    образцы = tmp_path / "thumbs"
    манифест = tmp_path / "m.csv"
    г = _прогон("--census", str(опись), "--group", "к снятию",
                "--thumbs", str(образцы), "--manifest", str(манифест),
                "--apply")
    assert "УДАЛЕНО: 3" in г.stdout, г.stdout
    assert not any(ф.exists() for ф in файлы), "исходники остались"
    записанные = list(образцы.iterdir())
    assert len(записанные) == 1, ("образец должен быть ОДИН на каталог,"
                                  f" а их {len(записанные)}")
    from PIL import Image
    с = Image.open(записанные[0])
    с.load()
    assert с.size[0] <= 320, с.size
    строки = list(csv.DictReader(манифест.open(encoding="utf-8")))
    assert len(строки) == 3
    assert {с_["исход"] for с_ in строки} == {"удалён"}
    assert all(с_["sha256"] and с_["пиксели"] for с_ in строки), строки


def test_без_образца_файлы_не_удаляются(tmp_path):
    """Если вид сохранить не удалось, удалять нельзя — это условие владельца."""
    каталог = tmp_path / "прогон"
    каталог.mkdir(parents=True)
    битый = каталог / "broken.png"
    битый.write_bytes("не изображение".encode("utf-8"))
    опись = _опись(tmp_path, [битый])
    манифест = tmp_path / "m.csv"
    г = _прогон("--census", str(опись), "--group", "к снятию",
                "--thumbs", str(tmp_path / "thumbs"),
                "--manifest", str(манифест), "--apply")
    assert битый.exists(), "файл удалён, хотя образец не сохранился"
    строки = list(csv.DictReader(манифест.open(encoding="utf-8")))
    assert строки and строки[0]["исход"].startswith("НЕ УДАЛЁН"), строки
    assert "нет образца" in строки[0]["исход"], строки


def test_группа_не_из_описи_ничего_не_трогает(tmp_path):
    файл = tmp_path / "прогон" / "home.png"
    _png(файл)
    опись = _опись(tmp_path, [файл])
    г = _прогон("--census", str(опись), "--group", "визуальный эталон",
                "--thumbs", str(tmp_path / "thumbs"),
                "--manifest", str(tmp_path / "m.csv"), "--apply")
    assert "НЕЧЕГО СНИМАТЬ" in г.stdout, г.stdout
    assert файл.exists()
    assert г.returncode == 1
