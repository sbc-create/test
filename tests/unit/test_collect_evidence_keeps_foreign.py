"""Сборщик доказательств не стирает доказательства чужих работ.

Дефект, который закрывает эта проверка, измерен 2026-10-14. Сборщик удалял
`artifacts/evidence` целиком (`shutil.rmtree`), оставляя только `README.md`, и
вместе со своими вчерашними копиями уносил ЧУЖИЕ наборы, лежащие в git:
`arch-player-content-010/`, `lords-template-1.1.0/`, `portable-site-cell/`,
`playback/`, `new-sites/` — 57 файлов по `git status` после полного прогона.
Отдельно, уже во ВТОРОЙ редакции, тем же прогоном потерялись восемь файлов
`multisite-*`: это своя область сборщика, но собрать их на этом хосте нечем —
шаг `payload-blueprint` здесь пропускается. То есть инструмент, который ведёт набор доказательств, сам его
и стирал, а следующий коммит зафиксировал бы пропажу как намеренную.

Доказательство, исчезающее от запуска тестов, доказательством не является —
поэтому правило проверяется, а не описывается в комментарии.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
СБОРЩИК = КОРЕНЬ / "tests" / "tools" / "collect_evidence.py"


def _стенд(tmp_path: Path) -> Path:
    """Поддельный корень фабрики: задание, своя копия и чужие доказательства."""
    артефакты = tmp_path / "artifacts"
    (артефакты / "jobs" / "pilot-local").mkdir(parents=True)
    (артефакты / "jobs" / "pilot-local" / "job.json").write_text(json.dumps(
        {"job_id": "j1", "status": "DONE", "finished_at": "2026-10-14T00:00:00Z"},
        ensure_ascii=False), encoding="utf-8")

    доказательства = артефакты / "evidence"
    (доказательства / "lords-template-1.1.0").mkdir(parents=True)
    (доказательства / "lords-template-1.1.0" / "ACCEPTANCE.md").write_text(
        "чужой набор", encoding="utf-8")
    (доказательства / "playback").mkdir()
    (доказательства / "playback" / "fleet-probe-summary.json").write_text(
        "{}", encoding="utf-8")
    (доказательства / "README.md").write_text("опись набора", encoding="utf-8")
    # Своя копия прошлого прогона: её сборщик обязан заменить.
    (доказательства / "run-all.json").write_text('{"прошлый": true}', encoding="utf-8")
    (артефакты / "qa").mkdir()
    (артефакты / "qa" / "run-all.json").write_text('{"новый": true}', encoding="utf-8")
    return tmp_path


def _запустить(корень: Path) -> subprocess.CompletedProcess:
    среда = {"FACTORY_ROOT": str(корень), "PATH": "/usr/bin:/bin",
             "PYTHONPATH": str(КОРЕНЬ)}
    return subprocess.run([sys.executable, str(СБОРЩИК)], capture_output=True,
                          text=True, timeout=120, cwd=str(КОРЕНЬ), env=среда)


def test_чужие_доказательства_остаются_на_месте(tmp_path: Path):
    корень = _стенд(tmp_path)
    г = _запустить(корень)
    assert г.returncode == 0, г.stderr
    д = корень / "artifacts" / "evidence"
    assert (д / "lords-template-1.1.0" / "ACCEPTANCE.md").is_file(), (
        "чужой набор доказательств удалён сборщиком")
    assert (д / "playback" / "fleet-probe-summary.json").is_file()
    assert (д / "README.md").read_text(encoding="utf-8") == "опись набора"


def test_своя_копия_обновляется_а_не_копится(tmp_path: Path):
    """Прошлая своя копия заменяется: иначе отчёт отстаёт ровно на один прогон."""
    корень = _стенд(tmp_path)
    г = _запустить(корень)
    assert г.returncode == 0, г.stderr
    свежий = (корень / "artifacts" / "evidence" / "run-all.json").read_text(encoding="utf-8")
    assert json.loads(свежий) == {"новый": True}


def test_своя_копия_остаётся_если_заменить_её_нечем(tmp_path: Path):
    """Шаг в прогоне не выполнялся — файл остаётся, а не удаляется.

    Измерено 2026-10-14: на этом хосте шаг `payload-blueprint` пропускается
    (нет зависимостей приложения), и редакция, чистившая весь свой список,
    удалила восемь закоммиченных файлов `multisite-*` — доказательства,
    которые здесь воспроизвести нечем. Какие шаги шли в последнем прогоне,
    видно из `run-all.json`: у каждого статус и exit code, поэтому смешения
    прогонов эта сохранность не прячет.
    """
    корень = _стенд(tmp_path)
    был = корень / "artifacts" / "evidence" / "seo-render.json"
    был.write_text('{"прошлый": true}', encoding="utf-8")
    многосайт = корень / "artifacts" / "evidence" / "multisite-restore-proof.json"
    многосайт.write_text('{"с другого хоста": true}', encoding="utf-8")
    г = _запустить(корень)
    assert г.returncode == 0, г.stderr
    assert был.is_file(), "файл удалён, хотя источника для замены нет"
    assert многосайт.is_file(), (
        "доказательство второго blueprint удалено на хосте, где его нечем собрать")
    assert "сохранено без замены" in г.stdout
