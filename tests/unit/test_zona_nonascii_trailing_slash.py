"""Адрес с кириллицей без завершающего слэша роняет соединение.

Дефект найден при приёмке zonafilm.cc. Воспроизводится на любой витрине,
исполняющей оформление 1.1+ — то есть на zona, animedia и lords, как только
их манифест объявит версию из `ОФОРМЛЕНИЕ_ВЕРСИИ`.

Что происходит
--------------

В обработчике (`lords-frontend.py`):

    путь = unquote(разбор.path)                      # → str с кириллицей
    ...
    if ОФОРМЛЕНИЕ_НОВОЕ:
        if len(путь) > 1 and not путь.endswith("/"):
            цель = путь + "/" + (("?" + разбор.query) if разбор.query else "")
            self.send_response(308)
            self.send_header("Location", цель)       # ← latin-1, UnicodeEncodeError

`http.server` кодирует заголовки в latin-1. Значение `Location`, собранное из
раскодированного пути, содержит символы вне latin-1, `send_header` возбуждает
`UnicodeEncodeError`, обработчик умирает до `end_headers()`, и клиент получает
разорванное соединение вместо ответа.

Почему это важнее, чем кажется
------------------------------

Это не «кривой адрес». Любая ссылка на кириллический путь без завершающего
слэша — из письма, мессенджера, старой выдачи, чужого сайта — даёт не 404 и не
редирект, а обрыв. Обрыв неотличим от падения сервиса: мониторинг видит ошибку
транспорта, а не 404.

Точная правка (одна строка)
---------------------------

    -            цель = путь + "/" + (("?" + разбор.query) if разбор.query else "")
    +            цель = quote(путь, safe="/") + "/" + (("?" + разбор.query) if разбор.query else "")

и `quote` в импорт рядом с `unquote`. Эквивалентный вариант — собирать цель из
`разбор.path` (он ещё не раскодирован), но тогда двойное кодирование надо
исключать отдельно, и первый вариант короче.

Статус: `TEMPLATE_ZONA_BLOCKER-04`. Ветка разработки шаблона не трогается;
в контуре zonafilm.cc обрыв закрыт на уровне nginx — редирект на слэш
выполняется до проксирования (`automation/host/nginx/zona-02.conf`).
"""

from __future__ import annotations

import http.client
import os
import re
import urllib.parse
from pathlib import Path

import pytest

ORIGIN_ENV = "ZONA02_ORIGIN"
HOST_ENV = "ZONA02_HOST"
ФРОНТ = Path("/srv/lords/.frontend")


def _origin() -> tuple[str, int, str]:
    origin = os.environ.get(ORIGIN_ENV, "http://127.0.0.1:9123")
    host = os.environ.get(HOST_ENV, "zonafilm.cc")
    разобрано = urllib.parse.urlsplit(origin)
    return разобрано.hostname or "127.0.0.1", разобрано.port or 80, host


def _запрос(путь: str) -> tuple[str, int | None]:
    """Возвращает ('status', код) либо ('disconnect', None).

    `http.client` намеренно вместо `urllib`: нужен именно факт обрыва, а не
    исключение поверх него.
    """
    адрес, порт, host = _origin()
    соединение = http.client.HTTPConnection(адрес, порт, timeout=15)
    try:
        соединение.request("GET", путь, headers={"Host": host})
        ответ = соединение.getresponse()
        ответ.read()
        return "status", ответ.status
    except (http.client.RemoteDisconnected, http.client.BadStatusLine, ConnectionResetError):
        return "disconnect", None
    finally:
        соединение.close()


def _витрина_жива() -> bool:
    вид, код = _запрос("/healthz")
    return вид == "status" and код == 200


pytestmark = pytest.mark.skipif(
    not _витрина_жива(),
    reason=f"витрина недоступна: задайте {ORIGIN_ENV}/{HOST_ENV}",
)


КИРИЛЛИЦА = urllib.parse.quote("этого-адреса-нет")


def test_ascii_путь_без_слэша_отвечает_а_не_обрывается():
    """Опорная точка: на ASCII тот же переход работает."""
    вид, код = _запрос("/no-such-page-xyz")
    assert вид == "status", "ASCII-путь тоже обрывается: дефект шире описанного"
    assert код in (200, 301, 308, 404)


def test_кириллица_со_слэшом_отвечает():
    """Вторая опорная точка: сам по себе кириллический путь обрабатывается."""
    вид, код = _запрос("/" + КИРИЛЛИЦА + "/")
    assert вид == "status"
    assert код == 404


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TEMPLATE_ZONA_BLOCKER-04: дефект закреплённого артефакта шаблона Zona "
        "(7ccf094a…), который этой задаче править запрещено — ветка шаблона "
        "принадлежит другому терминалу. xfail здесь не прячет провал: strict "
        "означает, что как только правка появится, тест начнёт ПАДАТЬ как XPASS "
        "и потребует снять и эту пометку, и обход в nginx. В контуре zonafilm.cc "
        "обрыв закрыт до origin — см. automation/host/nginx/zona-02.conf."
    ),
)
def test_кириллица_без_слэша_не_обрывает_соединение():
    """Собственно дефект. XPASS = TEMPLATE_ZONA_BLOCKER-04 исправлен, обход пора убрать."""
    вид, код = _запрос("/" + КИРИЛЛИЦА)
    assert вид == "status", (
        "витрина разорвала соединение вместо ответа: Location для 308 собирается "
        "из раскодированного пути и не кодируется обратно, а http.server пишет "
        "заголовки в latin-1 (TEMPLATE_ZONA_BLOCKER-04)"
    )
    assert код in (301, 308, 404)


def test_исходник_всё_ещё_содержит_неисправленную_строку():
    """Пока правки нет — она видна в артефакте. Когда появится, тест напомнит убрать себя."""
    рантайм = ФРОНТ / "sites" / "zona-02" / "current" / "lords-frontend.py"
    if not рантайм.exists():
        pytest.skip("витрина zona-02 не развёрнута")
    исходник = рантайм.resolve().read_text(encoding="utf-8")
    уязвимая = re.search(
        r'цель\s*=\s*путь\s*\+\s*"/"\s*\+\s*\(\("\?"\s*\+\s*разбор\.query\)', исходник)
    исправленная = re.search(r'цель\s*=\s*quote\(путь', исходник)
    assert уязвимая or исправленная, "форма строки изменилась — тест устарел и требует пересмотра"
    if исправленная:
        pytest.skip("правка применена в артефакте: тест выполнил свою задачу")
