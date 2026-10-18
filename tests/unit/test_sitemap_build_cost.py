"""REQ-SEO-SITEMAP-COST: цена сборки карты мерится настоящим сборщиком.

MOD-79 назвал следующим замером цену сборки 565 тысяч адресов серий. Замер
сделан местно и ни одной витрины не касается, но он имеет смысл только при двух
условиях, и они проверяются здесь:

* мерится НАСТОЯЩАЯ `построить_sitemap` семейного рантайма, а не её подобие —
  иначе число описывает выдуманный код;
* печатаются все три объёма (сегодняшний, промежуточный, полный) — одно число
  без сегодняшнего не говорит, во сколько раз выросла цена.

Измерено 2026-10-18: 66 159 адресов — 3 файла, 1.9 с, пик 29 МиБ; 631 167 —
15 файлов, 16.4 с, пик 189 МиБ.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "sitemap-build-cost.py"


def test_мерится_настоящий_сборщик():
    тело = ПУТЬ.read_text(encoding="utf-8")
    assert '"seo_layer"' in тело
    assert "automation" in тело and "seo_layer.py" in тело
    assert "seo.построить_sitemap(" in тело, (
        "цена обязана мериться тем же вызовом, что делает поток «sitemap»")


def test_печатаются_все_три_объёма():
    тело = ПУТЬ.read_text(encoding="utf-8")
    for подпись in ("сегодня: только произведения", "плюс четверть серий",
                    "все доступные серии"):
        assert подпись in тело
    assert "66_159" in тело and "565_008" in тело, (
        "объёмы обязаны быть измеренными числами, а не круглыми")


def test_печатается_пик_памяти_а_не_только_время():
    """Решение упирается в память: на узле семнадцать витрин."""
    тело = ПУТЬ.read_text(encoding="utf-8")
    assert "tracemalloc" in тело
    assert "пик памяти" in тело


def test_сборщик_делит_адреса_по_пределу():
    """Свойство самого сборщика, от которого зависит число файлов в замере."""
    спец = importlib.util.spec_from_file_location(
        "seo_layer_для_замера", КОРЕНЬ / "automation" / "host" / "seo_layer.py")
    seo = importlib.util.module_from_spec(спец)
    sys.modules["seo_layer_для_замера"] = seo
    спец.loader.exec_module(seo)
    страницы = [{"url": f"/title/t{н}/"} for н in range(seo.ПРЕДЕЛ_URL + 10)]
    файлы = seo.построить_sitemap("x.example", страницы)
    assert [и for и, _ in файлы][-1] == "sitemap.xml"
    assert len(файлы) == 3, "две части и индекс"


def test_замер_запускается_и_отвечает_тремя_строками():
    """Короткий прогон целиком: инструмент, который не запускается, не замер."""
    # Делитель 50: проверке нужна форма вывода и факт запуска, а не числа.
    # Числа в MOD-79 сняты при делителе 1 и в записи названы.
    г = subprocess.run([sys.executable, str(ПУТЬ), "50"], capture_output=True,
                       text=True, timeout=600)
    assert г.returncode == 0, г.stderr[-400:]
    строки = [с for с in г.stdout.splitlines() if "адресов" in с]
    assert len(строки) == 3, г.stdout
    assert "файлов" in строки[0] and "пик памяти" in строки[0]
