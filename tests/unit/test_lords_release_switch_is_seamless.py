"""Смена релиза не должна отнимать у сайта ни секунды.

Живой посетитель получил 502 в 08:37:41 — ровно в ту секунду, когда systemd
остановил юнит, чтобы запустить его на новом релизе. Порт в это мгновение не
слушал никто, и nginx отвечать было нечем. Таких перезапусков набиралось 243
в сутки, по одному на сайт на каждый цикл обновления.

Причина была в рантайме: он разрешал путь к релизу один раз при старте и потому
оказывался привязан к каталогу, который ссылка `current` уже не указывала.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from factory.lords.bundle import RUNTIME

PORT = 9297


def _release(root: Path, name: str, marker: str) -> Path:
    release = root / "releases" / name
    (release / "site").mkdir(parents=True)
    (release / "site" / "index.html").write_text(f"<html>{marker}</html>", encoding="utf-8")
    (release / "bundle-manifest.json").write_text(
        json.dumps({"site_id": "t", "profile": "p", "release": name}), encoding="utf-8")
    return release


@pytest.fixture
def stand(tmp_path):
    """Стенд из двух релизов со ссылкой `current`, как на сервере."""
    _release(tmp_path, "r1", "ПЕРВЫЙ")
    _release(tmp_path, "r2", "ВТОРОЙ")
    current = tmp_path / "current"
    current.symlink_to(tmp_path / "releases" / "r1")
    (tmp_path / "serve.py").write_text(RUNTIME, encoding="utf-8")
    env = {**os.environ, "LORDS_SITE_ROOT": str(current),
           "LORDS_HOST": "127.0.0.1", "LORDS_PORT": str(PORT)}
    proc = subprocess.Popen([sys.executable, str(tmp_path / "serve.py")], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        time.sleep(0.2)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/healthz", timeout=2).read()
            break
        except OSError:
            continue
    else:
        proc.terminate()
        pytest.skip("рантайм не поднялся в отведённое время")
    try:
        yield tmp_path, current, proc
    finally:
        proc.terminate()
        proc.wait(timeout=15)


def _get(path="/"):
    return urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=5).read().decode()


def _switch(current: Path, target: Path) -> None:
    """Атомарное переключение ссылки — ровно так же, как в выкладке."""
    staging = current.parent / "current.new"
    if staging.is_symlink() or staging.exists():
        staging.unlink()
    staging.symlink_to(target)
    os.replace(staging, current)


class TestSwitchingReleasesNeedsNoRestart:
    def test_new_release_is_served_without_touching_the_process(self, stand):
        root, current, proc = stand
        assert "ПЕРВЫЙ" in _get()
        _switch(current, root / "releases" / "r2")
        assert "ВТОРОЙ" in _get()
        # Тот же самый процесс: перезапуска не было.
        assert proc.poll() is None

    def test_health_reports_the_release_actually_being_served(self, stand):
        root, current, _ = stand
        assert json.loads(_get("/healthz"))["release"] == "r1"
        _switch(current, root / "releases" / "r2")
        assert json.loads(_get("/healthz"))["release"] == "r2"

    def test_the_site_answers_through_the_whole_switch(self, stand):
        """Ни один запрос не должен провалиться, пока ссылка меняется."""
        root, current, _ = stand
        codes = []
        for index in range(24):
            if index == 8:
                _switch(current, root / "releases" / "r2")
            if index == 16:
                _switch(current, root / "releases" / "r1")
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=5).read()
                codes.append(200)
            except urllib.error.HTTPError as error:
                codes.append(error.code)
            except OSError:
                codes.append(0)
        assert all(code == 200 for code in codes), codes

    def test_a_missing_page_is_still_a_plain_404(self, stand):
        with pytest.raises(urllib.error.HTTPError) as caught:
            _get("/no-such-page/")
        assert caught.value.code == 404


class TestRuntimeReadsTheLinkNotASnapshot:
    def test_the_runtime_no_longer_pins_the_release_at_import(self):
        # `Path(__file__).resolve()` в роли корня — ровно то, что привязывало
        # процесс к одному каталогу и делало перезапуск обязательным.
        assert 'BASE = Path(os.environ.get("LORDS_SITE_ROOT")' in RUNTIME
        assert "def site_dir():" in RUNTIME

    def test_the_manifest_is_reread_rather_than_remembered(self):
        assert "def manifest():" in RUNTIME
        assert "MANIFEST[" not in RUNTIME


class TestTheRuntimeSurvivesReleaseRetention:
    """Хранение удаляет старые релизы. Процесс не должен зависеть от них.

    Это не гипотеза: `Path(__file__).resolve()` в роли запасного пути привязал
    рабочий процесс к каталогу релиза, который был текущим на момент старта.
    Юнит на сервере переменную окружения ещё не получил, хранение со временем
    удалило тот каталог — и сайт начал отдавать 404 на все адреса сразу,
    включая главную. Перезапуска, который прежде всё чинил, больше нет.
    """

    def test_the_fallback_path_does_not_resolve_the_link_away(self):
        assert "Path(__file__).parent" in RUNTIME
        assert "Path(__file__).resolve().parent" not in RUNTIME

    def test_serving_survives_deletion_of_the_release_it_started_on(self, tmp_path):
        import json
        import os
        import shutil
        import subprocess
        import sys
        import time
        import urllib.request

        port = 9296
        for name, marker in (("r1", "ПЕРВЫЙ"), ("r2", "ВТОРОЙ")):
            _release(tmp_path, name, marker)
        current = tmp_path / "current"
        current.symlink_to(tmp_path / "releases" / "r1")
        (current / "serve.py").write_text(RUNTIME, encoding="utf-8")

        # Запускается ровно так, как это делает юнит: через путь со ссылкой и
        # БЕЗ переменной окружения — то есть по запасному пути.
        env = {k: v for k, v in os.environ.items() if k != "LORDS_SITE_ROOT"}
        env.update({"LORDS_HOST": "127.0.0.1", "LORDS_PORT": str(port)})
        proc = subprocess.Popen([sys.executable, str(current / "serve.py")], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(60):
                time.sleep(0.2)
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2).read()
                    break
                except OSError:
                    continue
            else:
                pytest.skip("рантайм не поднялся в отведённое время")

            _switch(current, tmp_path / "releases" / "r2")
            # Хранение убирает релиз, на котором процесс стартовал.
            shutil.rmtree(tmp_path / "releases" / "r1")

            body = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5).read().decode()
            assert "ВТОРОЙ" in body
            health = json.loads(urllib.request.urlopen(
                f"http://127.0.0.1:{port}/healthz", timeout=5).read().decode())
            assert health["release"] == "r2"
        finally:
            proc.terminate()
            proc.wait(timeout=15)
