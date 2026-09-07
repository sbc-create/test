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
import importlib
import json
import os
import signal
import socketserver
import sys
import threading
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, unquote
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

# Каталог релиза берётся из окружения и НЕ разрешается заранее.
#
# Раньше здесь стоял `Path(__file__).resolve()`, и процесс оказывался
# привязан к конкретному каталогу релиза: чтобы показать новый каталог,
# юнит приходилось перезапускать. За сутки это давало 243 перезапуска, и в
# секундное окно между «остановлен» и «запущен» nginx отвечал 502 — один
# такой ответ получил живой посетитель.
#
# Ссылка `current` разрешается операционной системой при каждом обращении к
# файлу, поэтому переключение релиза видно немедленно и перезапуск для
# смены содержимого больше не нужен.
#
# Запасной путь берётся БЕЗ `resolve()`. Разница стоила публичного сайта: юнит
# на сервере переменную ещё не получил, `Path(__file__).resolve()` привязал
# процесс к каталогу релиза, который был текущим на момент старта, хранение
# этот каталог со временем удалило — и сайт начал отдавать 404 на все адреса
# сразу, включая главную. Перезапуска, который прежде всё чинил, больше нет.
#
# `Path(__file__).parent` — это сама ссылка `current`, потому что юнит
# запускает `.../current/serve.py`. Её разрешает операционная система при
# каждом обращении, и процесс остаётся привязан к ссылке, а не к её цели.
BASE = Path(os.environ.get("LORDS_SITE_ROOT") or Path(__file__).parent)

sys.path.insert(0, str(BASE / "lib"))


def site_dir():
    """Каталог страниц текущего релиза. Вычисляется на каждый запрос."""
    return BASE / "site"


SEARCH_LIMIT = 20
SEARCH_MAX_LIMIT = 50
_search_cache = {"stamp": None, "index": None}


def search_index():
    """Указатель поиска текущего релиза или None.

    None означает «источник недоступен», и это не то же самое, что пустая
    выдача: пустая выдача утверждает, что ничего не найдено, а здесь неизвестно,
    искали ли вообще. Витрина, отвечающая «ничего не найдено» из-за
    отсутствующего файла, выглядит исправной и не находит ничего никогда.
    """
    path = BASE / "search-index.json"
    try:
        stat = path.stat()
    except OSError:
        _search_cache["stamp"] = None
        _search_cache["index"] = None
        return None
    stamp = (stat.st_mtime_ns, stat.st_ino, stat.st_size)
    if _search_cache["stamp"] != stamp:
        lib = str(BASE / "lib")
        if lib not in sys.path:
            sys.path.insert(0, lib)
        # Кэш импортёра помнит, что каталога не было.
        #
        # Служба запускается раньше, чем раскладывается релиз: между стартом и
        # появлением `lib` проходят секунды, и Python успевает запомнить путь
        # как отсутствующий. Дальше он туда не заглядывает вовсе — поиск
        # отвечает «указателя нет» при лежащем рядом указателе. Измерено на
        # lords-02: библиотека на месте, файл на месте, ответ 503.
        importlib.invalidate_caches()
        try:
            _search_cache["index"] = json.loads(path.read_text(encoding="utf-8"))
            _search_cache["stamp"] = stamp
        except (OSError, ValueError):
            _search_cache["stamp"] = None
            _search_cache["index"] = None
            return None
    return _search_cache["index"]


def search(query, limit=SEARCH_LIMIT):
    """Результаты поиска или None, если указателя нет."""
    index = search_index()
    if index is None:
        return None
    try:
        from factory.lords import search_index as si
    except ImportError:
        return None
    try:
        return si.search(index, index.get("items") or [], query, limit=limit)
    except ValueError:
        # Указатель собран на другом наборе страниц: выдача была бы о других
        # записях. Отказ честнее.
        return None


def _query_of(environ):
    """Запрос из строки адреса, разобранный как UTF-8.

    WSGI отдаёт QUERY_STRING строкой, полученной побайтовым разбором latin-1:
    так устроен сам договор, и «матрица» приезжает как «Ð¼Ð°ÑÑÐ¸ÑÐ°». Поиск по
    такой строке не находит ничего и выглядит сломанным при исправном
    указателе — измерено на боевой витрине: ответ 200, count 0, в поле query
    видна испорченная кириллица.

    Обратное перекодирование делается на самой строке запроса, а не на
    результате разбора: `parse_qs` раскрывает %-последовательности в те же
    байты, и порядок здесь важен.
    """
    raw = environ.get("QUERY_STRING", "")
    try:
        raw = raw.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Строка уже в нормальном виде или содержит непригодные байты: разбираем
        # как есть. Отказ здесь означал бы, что поиск не работает вовсе.
        pass
    values = parse_qs(raw, keep_blank_values=True).get("q", [])
    return (values[0] if values else "").strip()


def _limit_of(environ):
    raw = parse_qs(environ.get("QUERY_STRING", "")).get("limit", [])
    try:
        value = int(raw[0]) if raw else SEARCH_LIMIT
    except (TypeError, ValueError):
        return SEARCH_LIMIT
    return max(1, min(value, SEARCH_MAX_LIMIT))


def _card(item):
    name = escape(str(item.get("name") or ""))
    url = escape(str(item.get("url") or "/"))
    year = item.get("year")
    подпись = f" <span class='year'>{escape(str(year))}</span>" if year else ""
    return f'<li><a href="{url}">{name}</a>{подпись}</li>'


def search_page(body, query, results):
    """Готовая страница поиска с результатами, вставленными на сервере.

    Вставка идёт по единственному якорю — строке счётчика. Если якоря нет,
    страница отдаётся как есть: сломанная вставка хуже отсутствующей, а
    страница обязана открыться в любом случае.
    """
    anchor_start = body.find('<p class="count" id="search-count">')
    if anchor_start < 0:
        return body
    anchor_end = body.find("</p>", anchor_start)
    if anchor_end < 0:
        return body
    if results is None:
        замена = ('<p class="count" id="search-count">Поиск временно недоступен: '
                  'указатель этого выпуска не собран.</p>')
        return body[:anchor_start] + замена + body[anchor_end + 4:]
    if not query:
        return body
    if results:
        строки = "".join(_card(i) for i in results)
        замена = (f'<p class="count" id="search-count">Найдено: {len(results)} '
                  f'по запросу «{escape(query)}».</p>'
                  f'<ul class="cards search-results">{строки}</ul>')
    else:
        замена = (f'<p class="count" id="search-count">По запросу «{escape(query)}» '
                  f'ничего не найдено.</p>')
    return body[:anchor_start] + замена + body[anchor_end + 4:]


_manifest_cache = {"stamp": None, "data": None}

#: Манифесты релиза по убыванию доверия. `release-manifest.json` описывает
#: релиз целиком — витрину, тему, отпечаток шаблона, ревизию отрисовщика и
#: снимок каталога. `bundle-manifest.json` — прежняя форма, оставленная для
#: релизов, выложенных до неё.
MANIFEST_NAMES = ("release-manifest.json", "bundle-manifest.json")


def manifest():
    """Манифест текущего релиза, перечитываемый при смене файла.

    Держать его в памяти с момента старта нельзя: после переключения релиза
    healthz сообщал бы номер предыдущего.

    Отсутствие файла — это отсутствие манифеста, а не повод отдать прежний.
    Прежняя редакция при пропаже файла возвращала последнее прочитанное, и
    после смены имени манифеста healthz полтора часа сообщал номер релиза,
    которого уже не было в работе. Проверка по такому ответу подтверждает не
    то, что выложено, а то, что когда-то читалось.
    """
    for name in MANIFEST_NAMES:
        path = BASE / name
        try:
            stat = path.stat()
        except OSError:
            continue
        stamp = (name, stat.st_mtime_ns, stat.st_ino, stat.st_size)
        if _manifest_cache["stamp"] != stamp:
            try:
                _manifest_cache["data"] = json.loads(path.read_text(encoding="utf-8"))
                _manifest_cache["stamp"] = stamp
            except (OSError, ValueError):
                continue
        return _manifest_cache["data"] or {}
    _manifest_cache["stamp"] = None
    _manifest_cache["data"] = None
    return {}


def release_identity():
    """Чем витрина отвечает на вопрос «что именно сейчас выложено».

    Отдаётся то, по чему выкладку можно сверить: витрина, тема, отпечаток
    шаблона, ревизия отрисовщика, снимок каталога и цель отката. Пустые
    значения не подставляются: незаполненное поле честнее правдоподобного.
    """
    m = manifest()
    release = m.get("release")
    if not release:
        try:
            release = Path(os.path.realpath(str(BASE))).name
        except OSError:
            release = None
    return {
        "site_id": m.get("tenant_id") or m.get("site_id"),
        "theme": m.get("theme"),
        "profile": m.get("profile"),
        "release": release,
        "template_digest": m.get("template_digest"),
        "renderer_revision": m.get("renderer_revision"),
        "content_snapshot_id": m.get("content_snapshot_id"),
        "content_count": m.get("content_count"),
        "rollback_target": m.get("rollback_target"),
    }

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
    site = site_dir()
    candidate = (site / clean.strip("/") / "index.html") if clean.endswith("/") \
        else (site / clean.lstrip("/"))
    try:
        # Оба пути разрешаются от одного снимка ссылки: иначе переключение
        # релиза посреди запроса выглядело бы как попытка выйти из каталога.
        root = site.resolve()
        candidate = candidate.resolve()
        candidate.relative_to(root)
    except (ValueError, OSError):
        return None, None
    return (candidate if candidate.is_file() else None), None


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    if path in ("/healthz", "/readyz"):
        ready = (site_dir() / "index.html").is_file()
        body = json.dumps({
            "status": "ok" if (path == "/healthz" or ready) else "not_ready",
            **release_identity(),
            "indexing": "disabled",
        }, ensure_ascii=False).encode("utf-8")
        status = "200 OK" if (path == "/healthz" or ready) else "503 Service Unavailable"
        start_response(status, [("Content-Type", "application/json; charset=utf-8"),
                                ("Content-Length", str(len(body)))] + HEADERS)
        return [body]

    if path == "/api/search":
        query = _query_of(environ)
        results = search(query, _limit_of(environ)) if query else []
        if results is None:
            body = json.dumps({"error": "search_index_unavailable",
                               "message": "указатель поиска этого выпуска не собран"},
                              ensure_ascii=False).encode("utf-8")
            status = "503 Service Unavailable"
        else:
            body = json.dumps({"query": query, "count": len(results),
                               "results": results}, ensure_ascii=False).encode("utf-8")
            status = "200 OK"
        start_response(status, [("Content-Type", "application/json; charset=utf-8"),
                                ("Content-Length", str(len(body)))] + HEADERS)
        return [body]

    if path in ("/search/", "/search"):
        query = _query_of(environ)
        page = site_dir() / "search" / "index.html"
        if page.is_file():
            текст = page.read_text(encoding="utf-8", errors="replace")
            результаты = search(query, SEARCH_LIMIT) if query else []
            body = search_page(текст, query, результаты).encode("utf-8")
            start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"),
                                      ("Content-Length", str(len(body)))] + HEADERS)
            return [body]

    target, redirect = resolve(path)
    if redirect:
        start_response("308 Permanent Redirect",
                       [("Location", redirect), ("Content-Length", "0")] + HEADERS)
        return [b""]
    if target is None:
        target = site_dir() / "404.html"
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
    print("стенд %s на http://%s:%d/" % (manifest().get("site_id"), host, port), file=sys.stderr)
    # Ждём с таймаутом, а не бесконечно. Обработчик сигнала на уровне Python
    # выполняется только когда главный поток возвращается в цикл интерпретатора.
    # Бесконечный stop.wait() стоит в futex, а обработчики ставятся с SA_RESTART,
    # поэтому ядро перезапускает ожидание и ход обработчику не достаётся: SIGTERM
    # доставлен и снят, а _stop не выполнялся.
    #
    # Измерено 2026-09-04 под нагрузкой, примерно один запуск из семи: SigCgt
    # содержит 0x4000, SigPnd и ShdPnd пусты, SigBlk пуст, главный поток в
    # futex_wait_queue_me, строка «остановка» не напечатана. Юнит доживал до
    # таймаута соединения в 30 секунд, то есть systemd добивал бы его по
    # TimeoutStopSec вместо чистой остановки.
    while not stop.wait(0.5):
        pass
    print("остановка %s" % manifest().get("site_id"), file=sys.stderr)
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
