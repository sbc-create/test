"""REQ-LORDS-RUNTIME: рантайм пакета обслуживает соединения параллельно.

Проверяется тот самый `serve.py`, который лежит в архиве и который systemd
запустит на хосте, — он распаковывается и поднимается настоящим процессом.
Проверять здесь рендерер из репозитория было бы подменой: в пакет едет копия,
и разойтись они могут молча.

Почему это отдельный набор, а не строка в приёмке: `wsgiref.simple_server`
однопоточен, и отказ от этого проявляется не ошибкой, а зависанием. Браузер
заранее открывает сокеты про запас и по части из них не присылает ничего;
однопоточный сервер принимал такой сокет и ждал строку запроса, которой не
будет, — весь сайт замирал. В приёмке это выглядело плавающим таймаутом
`page.goto` на каждый раз новом тесте, то есть дефектом страницы, хотя дефект
был в рантайме. Nginx это не лечит: он проксирует, а не мультиплексирует.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pytest

from factory.lords import bundle as bundle_mod

SITE_ID = "lords-01"
STARTUP_TIMEOUT = 30.0

# Страницы, статика, пробы и тайтл с блоком комментариев — то, что браузер
# тянет одновременно при открытии одной страницы.
PATHS = [
    "/",
    "/catalog/",
    "/catalog/page/2/",
    "/movies/",
    "/title/bumazhnyy-ciferblat-2021/",
    "/assets/app.js",
    "/assets/site.css",
    "/robots.txt",
    "/healthz",
    "/readyz",
]


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _get(port: int, path: str, timeout: float = 10.0) -> tuple[int, bytes]:
    url = f"http://127.0.0.1:{port}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 — свой петлевой стенд
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


@pytest.fixture(scope="module")
def runtime(tmp_path_factory):
    """Распакованный пакет, поднятый настоящим процессом. Гасится по SIGTERM."""
    workdir = tmp_path_factory.mktemp("lords-runtime")
    built = bundle_mod.build_bundle(SITE_ID, output=workdir)
    unpacked = workdir / "unpacked"
    with tarfile.open(built["archive"]) as archive:
        archive.extractall(unpacked)  # noqa: S202 — архив собран этим же тестом

    port = _free_port()
    process = subprocess.Popen(
        [sys.executable, "serve.py"],
        cwd=unpacked,
        env={"LORDS_HOST": "127.0.0.1", "LORDS_PORT": str(port), "PATH": "/usr/bin:/bin"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(f"рантайм умер на старте: {process.stderr.read().decode()}")
        try:
            if _get(port, "/healthz", timeout=1.0)[0] == 200:
                break
        except OSError:
            time.sleep(0.1)
    else:
        process.kill()
        pytest.fail("рантайм не ответил на /healthz за отведённое время")

    yield port, process

    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


class TestConcurrency:
    def test_every_route_answers_when_requested_alone(self, runtime):
        """Опорная точка: без нагрузки все проверяемые адреса отдают 200."""
        port, _ = runtime
        for path in PATHS:
            status, body = _get(port, path)
            assert status == 200, f"{path}: получен {status}"
            assert body, f"{path}: пустое тело"

    def test_the_title_page_carries_the_comments_block(self, runtime):
        """Комментарии — часть страницы тайтла, и они тоже едут в параллели."""
        port, _ = runtime
        status, body = _get(port, "/title/bumazhnyy-ciferblat-2021/")
        assert status == 200
        assert b"comments" in body, "на странице тайтла нет блока комментариев"

    def test_parallel_requests_all_succeed(self, runtime):
        """Страницы, статика и пробы, запрошенные одновременно."""
        port, _ = runtime
        batch = PATHS * 6  # 60 запросов, больше чем соединений у браузера
        with ThreadPoolExecutor(max_workers=len(batch)) as pool:
            results = list(pool.map(lambda path: _get(port, path), batch))
        codes = [status for status, _ in results]
        assert set(codes) == {200}, f"в параллели появились коды {sorted(set(codes))}"

    def test_a_silent_connection_does_not_block_the_site(self, runtime):
        """Главная проверка регрессии.

        Открываем соединения и молчим — ровно то, что делает браузер, открывая
        сокеты про запас. Однопоточный рантайм на этом вставал целиком, и
        следующий запрос не получал ответа вообще. Порог в пять секунд взят с
        большим запасом: обычный ответ укладывается в миллисекунды, а зависание
        длилось до таймаута клиента.
        """
        port, _ = runtime
        silent = []
        try:
            for number in range(8):
                try:
                    silent.append(socket.create_connection(("127.0.0.1", port), timeout=5))
                except OSError as error:
                    # Однопоточный рантайм спотыкается уже здесь: занятый поток
                    # не разбирает очередь, она упирается в request_queue_size,
                    # и следующее соединение не принимается вовсе.
                    pytest.fail(
                        f"соединение №{number + 1} не принято ({error}): "
                        "рантайм не разбирает очередь параллельно"
                    )

            started = time.monotonic()
            status, _body = _get(port, "/", timeout=5.0)
            elapsed = time.monotonic() - started

            assert status == 200, f"сайт ответил {status}, пока висели молчащие соединения"
            assert elapsed < 5.0, f"ответ занял {elapsed:.1f}s — соединения блокируют сайт"
        finally:
            for quiet in silent:
                quiet.close()

    def test_the_site_survives_a_burst_and_keeps_answering(self, runtime):
        """Утечки соединений нет: после нагрузки рантайм отвечает как прежде."""
        port, process = runtime
        for _ in range(3):
            with ThreadPoolExecutor(max_workers=30) as pool:
                statuses = list(pool.map(lambda path: _get(port, path)[0], PATHS * 3))
            assert set(statuses) == {200}
        assert process.poll() is None, "рантайм умер под нагрузкой"

        status, body = _get(port, "/readyz")
        assert status == 200
        assert json.loads(body)["indexing"] == "disabled"


class TestShutdown:
    def test_sigterm_stops_the_process_cleanly_and_frees_the_port(self, tmp_path):
        """systemd останавливает юнит через SIGTERM.

        Прежний рантайм не обрабатывал сигнал и полагался на то, что процесс
        просто убьют. Теперь он закрывает слушающий сокет сам, поэтому проверяем
        и код возврата, и освобождённый порт.
        """
        built = bundle_mod.build_bundle(SITE_ID, output=tmp_path)
        unpacked = tmp_path / "unpacked"
        with tarfile.open(built["archive"]) as archive:
            archive.extractall(unpacked)  # noqa: S202 — архив собран этим же тестом

        port = _free_port()
        process = subprocess.Popen(
            [sys.executable, "serve.py"],
            cwd=unpacked,
            env={"LORDS_HOST": "127.0.0.1", "LORDS_PORT": str(port), "PATH": "/usr/bin:/bin"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            try:
                if _get(port, "/healthz", timeout=1.0)[0] == 200:
                    break
            except OSError:
                time.sleep(0.1)
        else:
            process.kill()
            pytest.fail("рантайм не поднялся")

        process.terminate()  # SIGTERM
        try:
            code = process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            pytest.fail("SIGTERM не остановил рантайм за 15 секунд")

        assert code == 0, f"рантайм вышел с кодом {code}, ожидался 0"

        # Слушающий сокет закрыт: соединение больше не принимается.
        # Проверяется именно это, а не bind: обслуженные соединения оставляют
        # записи TIME_WAIT на том же локальном адресе, и bind без SO_REUSEADDR
        # отказал бы даже при полностью закрытом слушателе.
        with socket.socket() as probe:
            probe.settimeout(2)
            assert probe.connect_ex(("127.0.0.1", port)) != 0, "порт всё ещё принимает соединения"

    def test_a_pending_silent_connection_does_not_delay_shutdown(self, tmp_path):
        """Висящее соединение не задерживает остановку юнита."""
        built = bundle_mod.build_bundle(SITE_ID, output=tmp_path)
        unpacked = tmp_path / "unpacked"
        with tarfile.open(built["archive"]) as archive:
            archive.extractall(unpacked)  # noqa: S202 — архив собран этим же тестом

        port = _free_port()
        process = subprocess.Popen(
            [sys.executable, "serve.py"],
            cwd=unpacked,
            env={"LORDS_HOST": "127.0.0.1", "LORDS_PORT": str(port), "PATH": "/usr/bin:/bin"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            try:
                if _get(port, "/healthz", timeout=1.0)[0] == 200:
                    break
            except OSError:
                time.sleep(0.1)
        else:
            process.kill()
            pytest.fail("рантайм не поднялся")

        quiet = socket.create_connection(("127.0.0.1", port), timeout=5)
        try:
            started = time.monotonic()
            process.terminate()
            try:
                code = process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                pytest.fail("молчащее соединение задержало остановку")
            elapsed = time.monotonic() - started
            assert code == 0
            assert elapsed < 15.0, f"остановка заняла {elapsed:.1f}s"
        finally:
            quiet.close()


class TestRuntimeSource:
    def test_the_shipped_runtime_is_threaded(self):
        """Однопоточный сервер в пакет не возвращается."""
        runtime = bundle_mod.RUNTIME
        assert "ThreadingWSGIServer" in runtime
        assert "socketserver.ThreadingMixIn" in runtime
        assert "server_class=ThreadingWSGIServer" in runtime

    def test_the_shipped_runtime_handles_termination(self):
        runtime = bundle_mod.RUNTIME
        assert "signal.SIGTERM" in runtime
        assert "server.shutdown()" in runtime
        assert "server.server_close()" in runtime

    def test_the_shipped_runtime_bounds_a_connection(self):
        """Без таймаута молчащее соединение держало бы поток вечно."""
        assert "timeout = 30" in bundle_mod.RUNTIME

    def test_the_shipped_runtime_compiles(self):
        """Пакет запускает системный python3, а не интерпретатор тестов."""
        compile(bundle_mod.RUNTIME, "serve.py", "exec")
