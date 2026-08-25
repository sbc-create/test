"""Переносимый пакет стенда Lords.

Пакет собирается так, чтобы его можно было перенести на управляющий сервер и
запустить там без единого обращения в сеть. Отсюда три свойства:

* **Воспроизводимость.** Архив детерминирован: имена отсортированы, отметок
  времени у файлов нет, права фиксированы. Две сборки одного пакета дают один и тот же
  sha256, и это проверяется, а не декларируется.
* **Отсутствие сети во время запуска.** Рантайм — стандартная библиотека
  Python. Пакет не ставит зависимости ни при сборке образа, ни при старте:
  сервер, который при каждом запуске идёт в реестр пакетов, невозможно ни
  повторить, ни поднять в закрытом контуре.
* **Готовый откат.** Вместе с релизом кладётся артефакт отката: идентификатор
  релиза, отпечаток сайта и точная процедура возврата. Откат, придуманный в
  момент аварии, — не откат.

Пакет никуда не выкатывается. Он именно готовится: выкат требует цели, домена и
отдельного решения владельца.
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

from factory.lords import preview as preview_mod
from factory.paths import PATHS

#: Фиксированное время в архиве. Реальное время сделало бы архив невоспроизводимым.
EPOCH = 0

RUNTIME = '''#!/usr/bin/env python3
"""Рантайм стенда Lords. Только стандартная библиотека — сеть при старте не нужна."""
import json
import os
import signal
import socketserver
import sys
import threading
from pathlib import Path
from urllib.parse import unquote
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
MANIFEST = json.loads((ROOT / "bundle-manifest.json").read_text(encoding="utf-8"))

TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}
HEADERS = [
    ("X-Robots-Tag", "noindex, nofollow"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("X-Frame-Options", "SAMEORIGIN"),
]


def normalize(path):
    """Канонический вид адреса. Копия правила из factory/lords/serve.py.

    Копия, а не импорт: пакет обязан работать без репозитория. Совпадение двух
    реализаций проверяется тестом на общей таблице адресов — разошедшийся
    рантайм отдавал бы 200 там, где сайт ждёт 308.
    """
    path = unquote(path or "/")
    while "//" in path:
        path = path.replace("//", "/")
    if not path.startswith("/"):
        path = "/" + path
    lowered = path.lower()
    if lowered != path:
        path = lowered
    if path != "/" and "." not in path.rsplit("/", 1)[-1] and not path.endswith("/"):
        path += "/"
    return path


def resolve(path):
    """Адрес → файл внутри site/. Выход за пределы каталога невозможен."""
    raw = unquote(path.split("?", 1)[0] or "/")
    clean = normalize(raw)
    if clean != raw:
        return None, clean
    candidate = (SITE / clean.strip("/") / "index.html") if clean.endswith("/") \
        else (SITE / clean.lstrip("/"))
    try:
        candidate = candidate.resolve()
        candidate.relative_to(SITE.resolve())
    except (ValueError, OSError):
        return None, None
    return (candidate if candidate.is_file() else None), None


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    if path in ("/healthz", "/readyz"):
        ready = (SITE / "index.html").is_file()
        body = json.dumps({
            "status": "ok" if (path == "/healthz" or ready) else "not_ready",
            "site_id": MANIFEST["site_id"],
            "profile": MANIFEST["profile"],
            "release": MANIFEST["release"],
            "indexing": "disabled",
        }, ensure_ascii=False).encode("utf-8")
        status = "200 OK" if (path == "/healthz" or ready) else "503 Service Unavailable"
        start_response(status, [("Content-Type", "application/json; charset=utf-8"),
                                ("Content-Length", str(len(body)))] + HEADERS)
        return [body]

    target, redirect = resolve(path)
    if redirect:
        start_response("308 Permanent Redirect",
                       [("Location", redirect), ("Content-Length", "0")] + HEADERS)
        return [b""]
    if target is None:
        target = SITE / "404.html"
        status = "404 Not Found"
    else:
        status = "200 OK"
    body = target.read_bytes() if target.is_file() else b"Not Found"
    ctype = TYPES.get(target.suffix, "application/octet-stream")
    start_response(status, [("Content-Type", ctype),
                            ("Content-Length", str(len(body)))] + HEADERS)
    return [body]


class Handler(WSGIRequestHandler):
    """Обработчик, который не зависает на молчащем соединении.

    Браузер заранее открывает несколько сокетов про запас (preconnect) и по
    части из них не присылает ничего. Однопоточный сервер принимал такой сокет
    и ждал строку запроса, которая не придёт, — весь сайт замирал до таймаута
    клиента. Поэтому у соединения есть свой срок жизни.

    Таймаут и разрыв — это поведение клиента, а не отказ сайта, поэтому они
    гасятся здесь и не превращаются в traceback на каждый неиспользованный
    сокет.
    """

    timeout = 30

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except OSError:
            self.close_connection = True


class ThreadingWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
    """Сервер, обслуживающий соединения параллельно.

    `wsgiref.simple_server` однопоточен: одно соединение в единицу времени на
    сайт. Nginx это не компенсирует — он проксирует, а не мультиплексирует, и
    очередь всё равно упирается в единственный поток рантайма.

    Потоки демонические и не удерживаются при закрытии: выключение идёт через
    shutdown() ниже, а висящее соединение не должно задерживать остановку юнита.
    """

    daemon_threads = True
    block_on_close = False
    request_queue_size = 128


if __name__ == "__main__":
    host = os.environ.get("LORDS_HOST", "127.0.0.1")
    port = int(os.environ.get("LORDS_PORT", "8080"))
    server = make_server(host, port, app, server_class=ThreadingWSGIServer, handler_class=Handler)
    stop = threading.Event()

    def _stop(signum, frame):
        # Только флаг. shutdown() ждёт выхода из цикла serve_forever, и вызов
        # его из потока, где этот цикл крутится, — взаимоблокировка.
        stop.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    worker = threading.Thread(target=server.serve_forever, name="serve", daemon=True)
    worker.start()
    print("стенд %s на http://%s:%d/" % (MANIFEST["site_id"], host, port), file=sys.stderr)
    stop.wait()
    print("остановка %s" % MANIFEST["site_id"], file=sys.stderr)
    server.shutdown()
    server.server_close()
    worker.join(timeout=5)
'''

DOCKERFILE = """# Стенд Lords. Зависимостей нет — образ ничего не скачивает ни при сборке
# слоёв приложения, ни при запуске контейнера.
FROM python:3.11-slim
WORKDIR /srv/lords
COPY . /srv/lords
ENV LORDS_HOST=0.0.0.0 LORDS_PORT=8080 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \\
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/readyz').status==200 else 1)"
USER nobody
CMD ["python3", "serve.py"]
"""

README = """# Стенд {site_id} ({profile})

Пакет собран фабрикой из синтетического каталога `fixture/test`. Реальных
произведений, оценок, дат релизов и сведений о правообладателях в нём нет.

## Запуск

    python3 serve.py            # http://127.0.0.1:8080/
    LORDS_PORT=8090 python3 serve.py

Или контейнером:

    docker build -t lords-{site_id} .
    docker run --rm -p 8080:8080 lords-{site_id}

Зависимости не устанавливаются: рантайм — стандартная библиотека Python.

## Пробы

    GET /healthz   процесс жив
    GET /readyz    сайт собран, главная на месте

## Индексация

Закрыта на всех уровнях: `robots.txt` с `Disallow: /`, заголовок
`X-Robots-Tag: noindex, nofollow` на каждом ответе, `noindex` в разметке,
sitemap без единого адреса. Домена у пакета нет, поэтому canonical не
выдумывается.

## Откат

Артефакт отката — `rollback.json`. Он содержит идентификатор релиза, отпечаток
сайта и процедуру возврата к предыдущему релизу.

## Чего здесь нет

Плеера CDNVideoHub: вместо него заглушка со статусом
`BLOCKED_INPUT_CDNVIDEOHUB_CREDENTIALS`. Заглушка не является пройденной
проверкой контракта плеера.
"""


def _tar_add(archive: tarfile.TarFile, name: str, data: bytes, *, mode: int = 0o644) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = EPOCH
    info.mode = mode
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    archive.addfile(info, io.BytesIO(data))


def build_bundle(site_id: str, *, output: Path | None = None) -> dict:
    """Собирает архив стенда. Повторный вызов даёт тот же sha256."""
    result = preview_mod.build_preview(site_id)
    site_digest = result.report["digest"]
    release = f"{site_id}-{site_digest[:12]}"

    manifest = {
        "site_id": site_id,
        "profile": result.profile,
        "release": release,
        "digest": site_digest,
        "data_source": result.report["data_source"],
        "indexing": "disabled",
        "canonical_state": result.report["canonical_state"],
        "player": result.report["player"],
        "blocked_inputs": result.report["blocked_inputs"],
        "deployable": False,
        "not_deployable_reason": "домен и цель выката не переданы; каталог синтетический",
    }
    rollback = {
        "release": release,
        "digest": site_digest,
        "previous_release": None,
        "procedure": [
            "остановить контейнер текущего релиза",
            "распаковать архив предыдущего релиза рядом, не удаляя текущий",
            "запустить предыдущий релиз и дождаться 200 на /readyz",
            "переключить трафик на предыдущий релиз",
            "сохранить архив отката и запись о причине",
        ],
        "note": "предыдущего релиза нет: стенд ещё не выкатывался",
    }

    files: dict[str, bytes] = {
        "serve.py": RUNTIME.encode("utf-8"),
        "Dockerfile": DOCKERFILE.encode("utf-8"),
        "README.md": README.format(site_id=site_id, profile=result.profile).encode("utf-8"),
        "bundle-manifest.json": (
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        "rollback.json": (
            json.dumps(rollback, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
    }
    for path in sorted(result.directory.rglob("*")):
        if path.is_file():
            files["site/" + str(path.relative_to(result.directory))] = path.read_bytes()

    directory = Path(output) if output else PATHS.artifact_dir("lords", "bundle")
    directory.mkdir(parents=True, exist_ok=True)
    archive_path = directory / f"{site_id}.tar"
    with tarfile.open(archive_path, "w", format=tarfile.GNU_FORMAT) as archive:
        for name in sorted(files):
            mode = 0o755 if name == "serve.py" else 0o644
            _tar_add(archive, name, files[name], mode=mode)
    payload = archive_path.read_bytes()

    rollback_path = directory / f"{site_id}.rollback.json"
    rollback_path.write_text(
        json.dumps(rollback, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")

    return {
        "site_id": site_id,
        "profile": result.profile,
        "archive": str(archive_path),
        "rollback": str(rollback_path),
        "release": release,
        "files": len(files),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "digest": site_digest,
        "manifest": manifest,
    }
