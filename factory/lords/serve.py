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
import shutil
from pathlib import Path
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

    def __init__(self, site: RenderedSite, redirects: dict | None = None):
        self.site = site
        self.pages = site.pages
        # Переезды адресов: старый адрес → новый, ровно один переход.
        #
        # Возникают, когда адрес меняет владельца: прежде по нему отдавалась
        # одна сущность, теперь адрес принадлежит другой, а прежняя переехала.
        # Отдавать 404 читателю, у которого этот адрес в закладках, незачем —
        # содержимое никуда не делось, оно переехало.
        self.redirects = dict(redirects or {})

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
            переезд = self.redirects.get(path)
            # Цель переезда обязана существовать. Переход на несобранную
            # страницу — это 404 через лишний шаг, а цепочка переходов
            # начинается ровно с того, что целью назначают ещё один переезд.
            if переезд and переезд in self.pages and переезд not in self.redirects:
                return self._text(308, "", extra=(("Location", переезд),))
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


#: Имя файла переездов в выгруженном дереве.
ПЕРЕЕЗДЫ = "redirects.json"


def переезды_из_каталога(directory) -> dict:
    """Карта переездов рядом с выгруженной витриной.

    Отсутствие файла — не ошибка: витрина без переездов их и не объявляет.
    А вот молчаливое игнорирование существующего файла было бы ошибкой:
    тринадцать адресов, у которых сменился владелец, стали бы 404 у читателя,
    и узнали бы об этом не мы.
    """
    файл = Path(directory) / ПЕРЕЕЗДЫ
    try:
        данные = json.loads(файл.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    переезды = данные.get("moved") or {}
    return {str(а): str(ц) for а, ц in переезды.items()}


def clear_directory(directory) -> None:
    """Опустошает каталог выгрузки, оставляя сам каталог.

    Выгрузка добавляет файлы и никогда не удаляет: страница, которую сайт
    перестал отдавать, остаётся лежать и отвечает как ни в чём не бывало. Так и
    вышло с разделом `/years/0/` — указатель на него ссылаться перестал, а
    страница со старым заголовком открывалась по прямой ссылке ещё три часа.

    Идиома была скопирована дословно в две точки вызова из четырёх, и в
    забытых двух ошибка и жила. Поэтому она здесь одна и названа.

    Обход снятым вручную не делается намеренно: он шёл по `rglob` и `is_dir`,
    а обе функции идут по символическим ссылкам — очистка каталога со ссылкой
    наружу вычистила бы и то, что снаружи. `rmtree` ссылку удаляет как запись
    и за неё не заходит.
    """
    root = Path(directory)
    if root.is_dir():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)


def page_target(root, path: str) -> Path:
    """Файл, в который ложится страница. Одно правило на выгрузку и на поток.

    Вынесено, потому что правил стало два места: обычная выгрузка и потоковая
    запись во время отрисовки. Две копии одного правила разошлись бы молча, и
    каталог, собранный потоком, отличался бы от собранного выгрузкой.
    """
    root = Path(root)
    if path.endswith("/"):
        return root / path.strip("/") / "index.html"
    return root / path.lstrip("/")


def write_page(root, page) -> str:
    """Записать одну страницу и вернуть её путь относительно корня."""
    target = page_target(root, page.path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(page.payload)
    return str(target.relative_to(Path(root)))


def export(site: RenderedSite, directory) -> dict:
    """Выгружает собранный сайт в каталог. Используется сборкой пакета стенда."""
    root = Path(directory)
    written = []
    for path, page in sorted(site.pages.items()):
        written.append(write_page(root, page))
    if site.not_found is not None:
        # Байтами, как и все прочие страницы. Текстовый режим здесь делал две
        # тихие вещи: переводил переносы строк по правилам платформы — то есть
        # артефакт при тех же входах вышел бы другим на другой системе — и
        # писал `body` вместо `payload`, а `body` при заданном `raw` является
        # человекочитаемым описанием, а не содержимым.
        (root / "404.html").write_bytes(site.not_found.payload)
        written.append("404.html")
    return {"root": str(root), "files": sorted(written)}
