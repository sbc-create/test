"""Рантайм стенда Lords: WSGI-приложение поверх собранного сайта.

Приложение отдаёт то, что собрал рендерер, и добавляет то, что бывает только у
работающего сервера: нормализацию адреса ответом 308, честный 404 вместо пустой
двухсотки, заголовок `X-Robots-Tag` на каждом ответе и пробы готовности.

Зависимостей нет: всё берётся из стандартной библиотеки. Это требование не
эстетическое — рантайм, который при каждом запуске тянет пакеты из сети, нельзя
ни воспроизвести, ни запустить в закрытом контуре.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import unquote

from factory.lords.render import RenderedSite

#: Заголовок закрытия от индексации. Ставится на каждый ответ стенда, включая
#: 404, 308 и статику: закрывать только HTML недостаточно.
ROBOTS_HEADER = ("X-Robots-Tag", "noindex, nofollow")

SECURITY_HEADERS = (
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("X-Frame-Options", "SAMEORIGIN"),
)

HEALTH_PATH = "/healthz"
READY_PATH = "/readyz"


@dataclass(frozen=True)
class Response:
    status: int
    headers: tuple
    body: bytes


STATUS_TEXT = {
    200: "200 OK",
    308: "308 Permanent Redirect",
    404: "404 Not Found",
    405: "405 Method Not Allowed",
    503: "503 Service Unavailable",
}


def normalize(path: str) -> str:
    """Канонический вид адреса.

    Один документ — один адрес. Двойные слэши, верхний регистр и отсутствующий
    завершающий слэш дают тот же документ по другому URL, а это ровно тот случай,
    ради которого существует 308: адрес исправляется один раз и навсегда, без
    потери метода запроса.
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


class Application:
    """WSGI-приложение одного сайта стенда."""

    def __init__(self, site: RenderedSite):
        self.site = site
        self.pages = site.pages

    # -- ответы ------------------------------------------------------------
    def _headers(self, page_type: str, length: int, extra=()) -> tuple:
        base = [
            ("Content-Type", page_type),
            ("Content-Length", str(length)),
            ROBOTS_HEADER,
            *SECURITY_HEADERS,
        ]
        base.extend(extra)
        return tuple(base)

    def _text(self, status: int, body: str, content_type="text/plain; charset=utf-8",
              extra=()) -> Response:
        payload = body.encode("utf-8")
        return Response(status, self._headers(content_type, len(payload), extra), payload)

    def handle(self, method: str, raw_path: str) -> Response:
        if method not in ("GET", "HEAD"):
            return self._text(405, "Стенд отвечает только на GET и HEAD.\n")

        if raw_path in (HEALTH_PATH, READY_PATH):
            return self._probe(raw_path)

        path = normalize(raw_path)
        if path != (unquote(raw_path) or "/"):
            return self._text(308, "", extra=(("Location", path),))

        page = self.pages.get(path)
        if page is None:
            miss = self.site.not_found
            body = miss.body if miss else "Страница не найдена"
            payload = body.encode("utf-8")
            return Response(404, self._headers("text/html; charset=utf-8", len(payload)), payload)

        payload = page.body.encode("utf-8")
        return Response(page.status,
                        self._headers(page.content_type, len(payload)), payload)

    def _probe(self, path: str) -> Response:
        """Health и readiness.

        Health говорит, что процесс жив. Readiness — что сайт собран и в нём есть
        главная; пустой набор страниц означает «не готов», а не «готов, но пусто».
        """
        ready = bool(self.pages) and "/" in self.pages
        payload = {
            "status": "ok" if (path == HEALTH_PATH or ready) else "not_ready",
            "site_id": self.site.site_id,
            "profile": self.site.profile,
            "pages": len(self.pages),
            "indexing": "disabled",
            "data_source": self.site.report.get("data_source", ""),
        }
        status = 200 if (path == HEALTH_PATH or ready) else 503
        return self._text(status, json.dumps(payload, ensure_ascii=False) + "\n",
                          content_type="application/json; charset=utf-8")

    # -- WSGI --------------------------------------------------------------
    def __call__(self, environ, start_response):
        response = self.handle(environ.get("REQUEST_METHOD", "GET"),
                               environ.get("PATH_INFO", "/"))
        start_response(STATUS_TEXT.get(response.status, f"{response.status} Status"),
                       list(response.headers))
        if environ.get("REQUEST_METHOD") == "HEAD":
            return [b""]
        return [response.body]


def export(site: RenderedSite, directory) -> dict:
    """Выгружает собранный сайт в каталог. Используется сборкой пакета стенда."""
    from pathlib import Path

    root = Path(directory)
    written = []
    for path, page in sorted(site.pages.items()):
        target = root / path.lstrip("/")
        if path.endswith("/"):
            target = root / path.strip("/") / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page.body, encoding="utf-8")
        written.append(str(target.relative_to(root)))
    if site.not_found is not None:
        (root / "404.html").write_text(site.not_found.body, encoding="utf-8")
        written.append("404.html")
    return {"root": str(root), "files": sorted(written)}
