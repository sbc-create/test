"""Замер памяти витрин меряет витрину, а не всё, что нашлось по пути.

Поводы, оба стоили неверных выводов:

* в счёт попадали обновлятель данных (`animedia-data-update.py`, минута жизни и
  156 МиБ) и сама оболочка, выполнявшая замер: RSS витрины выходил завышен на
  сотни МиБ, а её возраст обнулялся — выходило «витрина только что поднялась»;
* базовая линия считалась по точному равенству размера снимка. Снимки одного
  семейства расходятся на единицы МиБ, поэтому каждая витрина попадала в группу
  из себя одной и дрейф всегда выходил нулевым.

Здесь сторожится само правило замера: кто считается витриной, как складываются
процессы, как выбирается база и чем отличается «дрейфа нет» от «сравнивать не с
чем».
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "local" / "showcase-memory-report.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("showcase_memory_report", СЦЕНАРИЙ)
    м = importlib.util.module_from_spec(спец)
    sys.modules["showcase_memory_report"] = м
    спец.loader.exec_module(м)
    return м


def _процесс(корень: Path, pid: int, команда: str, rss_мб: int, hwm_мб: int,
             старт_тактов: int) -> None:
    место = корень / str(pid)
    место.mkdir(parents=True)
    (место / "cmdline").write_bytes(команда.replace(" ", "\0").encode() + b"\0")
    (место / "status").write_text(
        f"Name:\tpython3\nPPid:\t1\nVmRSS:\t{rss_мб * 1024} kB\n"
        f"VmHWM:\t{hwm_мб * 1024} kB\nThreads:\t3\n")
    поля = " ".join(["0"] * 19 + [str(старт_тактов)])
    (место / "stat").write_text(f"{pid} (python3) S {поля}\n")


@pytest.fixture()
def стенд(tmp_path, monkeypatch):
    м = _модуль()
    проц, srv = tmp_path / "proc", tmp_path / "srv"
    проц.mkdir()
    srv.mkdir()
    (проц / "uptime").write_text("360000.00 10.0\n")
    (проц / "meminfo").write_text(
        "MemTotal:       30797000 kB\nMemAvailable:    3072000 kB\n")
    (проц / "vmstat").write_text("pgfault 1\noom_kill 27\nnr_free_pages 5\n")
    monkeypatch.setattr(м, "ПРОЦЕССЫ", проц)
    monkeypatch.setattr(м, "КОРНИ", srv)
    return м, проц, srv


def _снимок(srv: Path, витрина: str, байт: int) -> None:
    данные = srv / витрина / "data"
    данные.mkdir(parents=True, exist_ok=True)
    (данные / f"{витрина}-01-catalog.json").write_bytes(b"x" * байт)


def test_обновлятель_в_замер_не_попадает(стенд):
    """Главный повод: он живёт минуту, держит 156 МиБ и обнуляет возраст."""
    м, проц, srv = стенд
    _снимок(srv, "animedia-icu", 17 * 1024 * 1024)
    _процесс(проц, 101, "/usr/bin/python3 /srv/animedia-icu/releases/aa/src/"
             "animedia-frontend.py --port 9121", 913, 944, 100 * 6660)
    _процесс(проц, 102, "/usr/bin/python3 /srv/animedia-icu/current/automation/"
             "animedia-data-update.py --site animedia-01", 156, 156, 100 * 359_940)
    (витрина,) = м.собрать()
    assert витрина["rss_mib"] == 913, "обновлятель не часть витрины"
    assert витрина["processes"] == 1
    assert витрина["age_s"] > 3000, "возраст витрины, а не её обновлятеля"


def test_посторонняя_оболочка_не_витрина(стенд):
    """Замер не должен находить сам себя: путь витрины есть и в его команде."""
    м, проц, srv = стенд
    _процесс(проц, 201, "/bin/bash -c grep /srv/animedia-icu/current/x", 3, 3, 0)
    assert м.собрать() == []


def test_процессы_одной_витрины_складываются(стенд):
    """Переключение blue-green — два процесса, и память занята обоими."""
    м, проц, srv = стенд
    _снимок(srv, "zonafilm-space", 100 * 1024 * 1024)
    _процесс(проц, 301, "/usr/bin/python3 /srv/zonafilm-space/releases/aa/src/"
             "lords-frontend.py --port 9120", 500, 520, 100 * 350_000)
    _процесс(проц, 302, "/usr/bin/python3 /srv/zonafilm-space/releases/bb/src/"
             "lords-frontend.py --port 9220", 300, 310, 100 * 359_000)
    (витрина,) = м.собрать()
    assert витрина["rss_mib"] == 800, "RSS — сумма по процессам витрины"
    assert витрина["hwm_mib"] == 520, "HWM — наибольшая отметка одного из них"
    assert витрина["processes"] == 2


def test_база_по_сравнимым_снимкам_а_не_по_равным(стенд):
    """100,4 и 100,5 МиБ — одно семейство; иначе дрейф всегда ноль."""
    м = стенд[0]
    витрины = м.дрейф([
        {"showcase": "старая", "rss_mib": 1430, "snapshot_mib": 100.5},
        {"showcase": "свежая", "rss_mib": 577, "snapshot_mib": 100.4},
    ])
    по_имени = {м_["showcase"]: м_ for м_ in витрины}
    assert по_имени["старая"]["drift_mib"] == 853
    assert по_имени["свежая"]["drift_mib"] == 0
    assert all(м_["comparable"] for м_ in витрины)


def test_несравнимый_размер_в_одну_группу_не_сводится(стенд):
    """3 МиБ снимка и служебный процесс без данных — не база друг для друга."""
    м = стенд[0]
    витрины = м.дрейф([
        {"showcase": "мелкая", "rss_mib": 182, "snapshot_mib": 3.3},
        {"showcase": "служебный", "rss_mib": 4, "snapshot_mib": 0.0},
        {"showcase": "крупная", "rss_mib": 904, "snapshot_mib": 132.7},
    ])
    по_имени = {м_["showcase"]: м_ for м_ in витрины}
    assert по_имени["мелкая"]["baseline_mib"] == 182, "4 МиБ ей не база"
    assert по_имени["крупная"]["comparable"] is False, "пары нет — сравнивать не с чем"
    assert по_имени["служебный"]["comparable"] is False


def test_одиночка_это_не_отсутствие_дрейфа(стенд, capsys):
    м, проц, srv = стенд
    _снимок(srv, "lordfilm47-space", 132 * 1024 * 1024)
    _процесс(проц, 401, "/usr/bin/python3 /srv/lordfilm47-space/releases/aa/src/"
             "lords01-frontend.py --port 9110", 904, 1596, 100 * 350_000)
    assert м.главное([]) == 0
    вывод = capsys.readouterr().out
    assert "—" in вывод, "у одиночки в столбце дрейфа прочерк, а не нуль"
    assert "наибольший дрейф" not in вывод


def test_состояние_хоста_и_порог_редактора(стенд):
    м = стенд[0]
    х = м.хост()
    assert х["mem_available_mib"] == 3000 and х["mem_total_mib"] == 30075
    assert х["oom_kill_total"] == 27
    assert х["editor_threshold_mib"] == 2048, "порог редактора снижать нельзя"
    assert х["editor_can_start"] is True


def test_нехватка_памяти_для_редактора_видна(стенд):
    м, проц, _ = стенд
    (проц / "meminfo").write_text(
        "MemTotal:       30797000 kB\nMemAvailable:    1986560 kB\n")
    assert м.хост()["editor_can_start"] is False


def test_порядок_обслуживания_ссылается_на_этот_замер():
    текст = (КОРЕНЬ / "docs" / "MEMORY_MAINTENANCE_ORDER.md").read_text(
        encoding="utf-8")
    assert "showcase-memory-report.py" in текст
    assert "одна витрина за раз" in текст.lower()
    assert "blue-green" in текст, "для освобождения памяти он противопоказан"
