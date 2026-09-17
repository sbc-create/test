"""Ворота перед сборкой: решение до дорогой работы.

Самое опасное свойство таких ворот — отвечать «не надо» при собственной
поломке. Это остановило бы обновление каталога навсегда и незаметно, ровно как
неактивный таймер 30 августа. Поэтому отдельная проверка на отказ.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from factory.paths import PATHS

GATE = PATHS.root / "automation" / "host" / "lords-render-gate.py"
SCRIPT = PATHS.root / "automation" / "host" / "lords-content-refresh.sh"

НУЖЕН, НЕЯСНО, НЕ_НУЖЕН = 0, 2, 10


def запустить(*args, repo: Path, state: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args, "--repo", str(repo), "--state", str(state)],
        capture_output=True, text=True, check=False, timeout=120,
    )


@pytest.fixture
def репозиторий(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "factory" / "lords").mkdir(parents=True)
    for имя in ("render.py", "live_catalog.py", "live_site.py", "theme.py", "player.py",
                "plan.py"):
        (repo / "factory" / "lords" / имя).write_text(f"# {имя}\n", encoding="utf-8")
    (repo / "sites" / "lords-01").mkdir(parents=True)
    (repo / "sites" / "lords-01" / "package.yaml").write_text("site_id: lords-01\n",
                                                              encoding="utf-8")
    кэш = repo / "var" / "lords" / "lords" / "catalog-cache"
    кэш.mkdir(parents=True)
    (кэш / "lords-01.json").write_text(
        json.dumps({"items": [{"external_id": "1", "name": "Тайтл"}]}), encoding="utf-8"
    )
    return repo


class TestРешениеДоРаботы:
    def test_первый_прогон_требует_сборки(self, репозиторий, tmp_path):
        итог = запустить("lords-01", repo=репозиторий, state=tmp_path / "fp.json")
        assert итог.returncode == НУЖЕН

    def test_неизменившийся_вход_сборки_не_требует(self, репозиторий, tmp_path):
        состояние = tmp_path / "fp.json"
        запустить("lords-01", "--record", repo=репозиторий, state=состояние)
        итог = запустить("lords-01", repo=репозиторий, state=состояние)
        assert итог.returncode == НЕ_НУЖЕН
        assert "не изменился" in итог.stdout

    def test_изменение_каталога_видно(self, репозиторий, tmp_path):
        состояние = tmp_path / "fp.json"
        запустить("lords-01", "--record", repo=репозиторий, state=состояние)
        кэш = репозиторий / "var" / "lords" / "lords" / "catalog-cache" / "lords-01.json"
        кэш.write_text(json.dumps({"items": [{"external_id": "1", "name": "Другое"}]}),
                       encoding="utf-8")
        итог = запустить("lords-01", repo=репозиторий, state=состояние)
        assert итог.returncode == НУЖЕН
        assert "catalog" in итог.stdout

    def test_правка_кода_рендерера_не_прячется(self, репозиторий, tmp_path):
        """Отпечаток одного каталога оставил бы витрину со старой вёрсткой."""
        состояние = tmp_path / "fp.json"
        запустить("lords-01", "--record", repo=репозиторий, state=состояние)
        путь = репозиторий / "factory" / "lords" / "theme.py"
        путь.write_text(путь.read_text(encoding="utf-8") + "# правка\n", encoding="utf-8")
        итог = запустить("lords-01", repo=репозиторий, state=состояние)
        assert итог.returncode == НУЖЕН
        assert "renderer_version" in итог.stdout
        assert "полная пересборка" in итог.stdout

    def test_правка_профиля_сайта_видна(self, репозиторий, tmp_path):
        состояние = tmp_path / "fp.json"
        запустить("lords-01", "--record", repo=репозиторий, state=состояние)
        путь = репозиторий / "sites" / "lords-01" / "package.yaml"
        путь.write_text("site_id: lords-01\ntheme: другая\n", encoding="utf-8")
        итог = запустить("lords-01", repo=репозиторий, state=состояние)
        assert итог.returncode == НУЖЕН
        assert "site_profile" in итог.stdout


class TestОтказВоротНеОстанавливаетОбновление:
    def test_пропавший_кэш_даёт_сборку_а_не_пропуск(self, репозиторий, tmp_path):
        """Ворота, отвечающие «не надо» при поломке, останавливают всё молча."""
        (репозиторий / "var" / "lords" / "lords" / "catalog-cache" / "lords-01.json").unlink()
        итог = запустить("lords-01", repo=репозиторий, state=tmp_path / "fp.json")
        assert итог.returncode == НЕЯСНО
        assert итог.returncode != НЕ_НУЖЕН

    def test_битый_кэш_даёт_сборку(self, репозиторий, tmp_path):
        кэш = репозиторий / "var" / "lords" / "lords" / "catalog-cache" / "lords-01.json"
        кэш.write_text("не json", encoding="utf-8")
        итог = запустить("lords-01", repo=репозиторий, state=tmp_path / "fp.json")
        assert итог.returncode == НЕЯСНО

    def test_повреждённое_состояние_даёт_сборку(self, репозиторий, tmp_path):
        состояние = tmp_path / "fp.json"
        состояние.write_text("{}", encoding="utf-8")
        assert запустить("lords-01", repo=репозиторий, state=состояние).returncode == НУЖЕН


class TestПодключениеКСценарию:
    def test_ворота_вызываются_до_сборки(self):
        текст = SCRIPT.read_text(encoding="utf-8")
        ворота = текст.index("lords-render-gate.py")
        сборка = текст.index('"$PYTHON" - "$site" "$staging"')
        assert ворота < сборка, "ворота обязаны стоять перед дорогой работой"

    def test_код_десять_пропускает_сборку(self):
        текст = SCRIPT.read_text(encoding="utf-8")
        assert 'gate_code" -eq 10' in текст
        assert "сборка пропущена" in текст

    def test_отпечаток_пишется_после_приёмки_релиза(self):
        """Запись раньше означала бы, что оборванный прогон пометил вход как готовый."""
        текст = SCRIPT.read_text(encoding="utf-8")
        приёмка = текст.index("релиз ${release} принят")
        запись = текст.index("--record", приёмка)
        assert запись > приёмка

    def test_ворота_отключаются_переменной(self):
        """Аварийный выключатель нужен: гейт не должен быть незаменимым."""
        assert "LORDS_RENDER_GATE" in SCRIPT.read_text(encoding="utf-8")
