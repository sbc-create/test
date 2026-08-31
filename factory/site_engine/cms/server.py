"""CMS canary: интерфейс управления поверх Control Plane.

Изолирован намеренно. Слушает только loopback, не имеет публичного домена и не
знает ни одного адреса поставщика: всё, что он показывает, приходит из
Control Plane, а тот — из движков.

Пароли здесь не хранятся и не задаются в коде. Лицо опознаётся ключом сеанса,
который выдаётся при запуске и печатается в консоль запустившего. Ключ не
попадает ни в разметку, ни в журнал.
"""
from __future__ import annotations

import html
import json
import secrets
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from factory.site_engine.access import Principal, ROLE_PERMISSIONS
from factory.site_engine.api.control_plane import ControlPlaneApi
from factory.site_engine.api.openapi_v1 import spec as openapi_spec

СТИЛЬ = """
:root{--bg:#12141a;--fg:#e6e8ee;--dim:#8b90a0;--line:#262a35;--accent:#7aa2f7;--warn:#e0af68}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{padding:12px 20px;border-bottom:1px solid var(--line);display:flex;gap:18px;align-items:center;flex-wrap:wrap}
header b{color:var(--accent)}
nav a{color:var(--dim);text-decoration:none;margin-right:14px}
nav a.on{color:var(--fg);border-bottom:2px solid var(--accent)}
main{padding:20px;max-width:1200px}
h1{font-size:18px;margin:0 0 14px}
table{border-collapse:collapse;width:100%;margin-bottom:20px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.card{border:1px solid var(--line);border-radius:8px;padding:14px;margin-bottom:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.num{font-size:26px;font-weight:600}
.dim{color:var(--dim)}
.warn{color:var(--warn)}
form.act{display:inline}
button{background:#1c2030;color:var(--fg);border:1px solid var(--line);border-radius:6px;
padding:6px 12px;cursor:pointer;font:inherit}
button.danger{border-color:var(--warn);color:var(--warn)}
code{background:#1a1d27;padding:1px 5px;border-radius:4px}
.note{border-left:3px solid var(--accent);padding-left:12px;color:var(--dim);margin:14px 0}
"""

РАЗДЕЛЫ = [
    ("/", "Обзор"),
    ("/sites", "Сайты"),
    ("/content", "Контент"),
    ("/editorial", "Редакция"),
    ("/shelves", "Полки"),
    ("/schedule", "Расписание"),
    ("/jobs", "Задания"),
    ("/releases", "Релизы"),
    ("/users", "Доступ"),
    ("/audit", "Аудит"),
]


def э(значение: Any) -> str:
    return html.escape(str(значение), quote=True)


@dataclass
class Сеанс:
    principal_id: str
    ключ: str


class CmsCanary:
    """Состояние canary: кто вошёл и через что он ходит."""

    def __init__(self, api: ControlPlaneApi) -> None:
        self.api = api
        self.сеансы: dict[str, Сеанс] = {}
        self._lock = threading.RLock()

    def выдать_ключ(self, principal_id: str) -> str:
        with self._lock:
            ключ = secrets.token_urlsafe(24)
            self.сеансы[ключ] = Сеанс(principal_id, ключ)
            return ключ

    def лицо(self, ключ: str | None) -> Principal | None:
        if not ключ:
            return None
        сеанс = self.сеансы.get(ключ)
        if сеанс is None:
            return None
        return self.api.principals.get(сеанс.principal_id)


def страница(заголовок: str, путь: str, лицо: Principal | None, тело: str) -> str:
    навигация = "".join(
        f'<a href="{э(p)}" class="{"on" if p == путь else ""}">{э(t)}</a>'
        for p, t in РАЗДЕЛЫ
    )
    кто = (
        f'<span class="dim">{э(лицо.principal_id)} · {", ".join(r.value for r in лицо.roles)}</span>'
        if лицо else '<span class="warn">не опознан</span>'
    )
    return (
        "<!doctype html><html lang=ru><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{э(заголовок)} — Site Factory CMS</title><style>{СТИЛЬ}</style></head><body>"
        f"<header><b>Site Factory</b><nav>{навигация}</nav>{кто}"
        '<span class="dim">canary · не production</span></header>'
        f"<main><h1>{э(заголовок)}</h1>{тело}</main></body></html>"
    )


def таблица(колонки: list[str], строки: list[list[str]]) -> str:
    if not строки:
        return '<p class="dim">Записей нет.</p>'
    шапка = "".join(f"<th>{э(c)}</th>" for c in колонки)
    тело = "".join(
        "<tr>" + "".join(f"<td>{ячейка}</td>" for ячейка in строка) + "</tr>"
        for строка in строки
    )
    return f"<table><thead><tr>{шапка}</tr></thead><tbody>{тело}</tbody></table>"


class Обработчик(BaseHTTPRequestHandler):
    canary: CmsCanary = None  # назначается при запуске
    server_version = "SiteFactoryCMS/canary"

    def log_message(self, fmt, *args):  # журнал без ключей сеанса
        pass

    # ------------------------------------------------------------------ помощь
    def _ключ(self) -> str | None:
        куки = self.headers.get("Cookie") or ""
        for часть in куки.split(";"):
            имя, _, значение = часть.strip().partition("=")
            if имя == "sf_session":
                return значение
        return None

    def _ответ(self, код: int, тело: str, тип: str = "text/html; charset=utf-8",
               куки: str | None = None) -> None:
        данные = тело.encode("utf-8")
        self.send_response(код)
        self.send_header("Content-Type", тип)
        self.send_header("Content-Length", str(len(данные)))
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("Cache-Control", "no-store")
        if куки:
            self.send_header("Set-Cookie", куки)
        self.end_headers()
        self.wfile.write(данные)

    def _api(self, метод: str, путь: str, лицо: Principal | None, **kw) -> dict:
        ответ = self.canary.api.handle(
            метод, путь, principal_id=лицо.principal_id if лицо else None, **kw
        )
        return {"status": ответ.status, "body": ответ.body}

    # ------------------------------------------------------------------ GET
    def do_GET(self) -> None:
        разбор = urlparse(self.path)
        путь = разбор.path
        параметры = {k: v[0] for k, v in parse_qs(разбор.query).items()}

        if путь == "/openapi.json":
            self._ответ(200, json.dumps(openapi_spec(), ensure_ascii=False),
                        "application/json; charset=utf-8")
            return
        if путь == "/healthz":
            self._ответ(200, json.dumps({"status": "ok"}), "application/json")
            return

        if путь == "/login":
            ключ = параметры.get("key", "")
            if ключ in self.canary.сеансы:
                self._ответ(302, "", куки=f"sf_session={ключ}; HttpOnly; Path=/; SameSite=Strict")
                self.send_header if False else None
                return
            self._ответ(401, страница("Вход", путь, None,
                                      '<p class="dim">Ключ сеанса неверен.</p>'))
            return

        лицо = self.canary.лицо(self._ключ())
        if лицо is None:
            self._ответ(401, страница("Вход", путь, None,
                '<div class="note">Ключ сеанса выдаётся при запуске canary и печатается '
                'в консоль запустившего. В разметку и журнал он не попадает.</div>'
                '<p class="dim">Откройте <code>/login?key=…</code>.</p>'))
            return

        обработчики = {
            "/": self._обзор, "/sites": self._сайты, "/content": self._контент,
            "/editorial": self._редакция, "/shelves": self._полки,
            "/schedule": self._расписание, "/jobs": self._задания,
            "/releases": self._релизы, "/users": self._доступ, "/audit": self._аудит,
        }
        рисовать = обработчики.get(путь)
        if рисовать is None:
            self._ответ(404, страница("Не найдено", путь, лицо, '<p class="dim">Нет такого раздела.</p>'))
            return
        заголовок, тело = рисовать(лицо, параметры)
        self._ответ(200, страница(заголовок, путь, лицо, тело))

    # ------------------------------------------------------------------ POST
    def do_POST(self) -> None:
        лицо = self.canary.лицо(self._ключ())
        if лицо is None:
            self._ответ(401, страница("Вход", self.path, None, "<p>Не опознан.</p>"))
            return
        длина = int(self.headers.get("Content-Length") or 0)
        сырое = self.rfile.read(длина).decode("utf-8") if длина else ""
        поля = {k: v[0] for k, v in parse_qs(сырое).items()}
        тело = {
            "kind": поля.get("kind"),
            "site_id": поля.get("site_id") or None,
            "payload": json.loads(поля.get("payload") or "{}"),
            "idempotency_key": поля.get("idempotency_key") or None,
            "reason": поля.get("reason") or "",
            "confirmed": поля.get("confirmed") == "1",
        }
        итог = self._api("POST", "/api/v1/commands", лицо, body=тело)
        цвет = "" if итог["status"] < 400 else ' class="warn"'
        ошибка = (итог["body"].get("error") or {}).get("message", "")
        команда = (итог["body"].get("command") or {})
        разметка = (
            f'<div class="card"><p{цвет}>Код {итог["status"]}</p>'
            + (f"<p>Команда <code>{э(команда.get('command_id',''))}</code> "
               f"вид <code>{э(команда.get('kind',''))}</code> "
               f"состояние <code>{э(команда.get('state',''))}</code>"
               f"{' · повтор' if итог['body'].get('repeated') else ''}</p>"
               if команда else f"<p>{э(ошибка)}</p>")
            + '</div><p><a href="/jobs">К заданиям</a></p>'
        )
        self._ответ(200, страница("Команда", "/jobs", лицо, разметка))

    # ------------------------------------------------------------------ разделы
    def _данные(self, ресурс: str, лицо: Principal, параметры: dict) -> list[dict]:
        итог = self._api("GET", f"/api/v1/{ресурс}", лицо, params=параметры)
        if итог["status"] != 200:
            return []
        return итог["body"].get("items", [])

    def _обзор(self, лицо, параметры):
        сайты = self._данные("sites", лицо, {"per_page": "100"})
        задания = self._данные("jobs", лицо, {"per_page": "100"})
        аудит = self._данные("audit-events", лицо, {"per_page": "100"})
        карточки = "".join(
            f'<div class="card"><div class="num">{э(значение)}</div>'
            f'<div class="dim">{э(подпись)}</div></div>'
            for значение, подпись in (
                (len(сайты), "сайтов"),
                (len(задания), "заданий"),
                (len(аудит), "записей аудита"),
                (len(self.canary.api.commands), "команд подано"),
            )
        )
        return "Обзор", (
            f'<div class="grid">{карточки}</div>'
            '<div class="note">Canary. Публикация в production отсюда невозможна: '
            'команда принимается, но исполнителя в этом контуре нет.</div>'
        )

    def _сайты(self, лицо, параметры):
        строки = [
            [э(s.get("site_id")), э(s.get("site_type", "")),
             э(", ".join(s.get("domains", []))), э(s.get("modules", ""))]
            for s in self._данные("sites", лицо, {"per_page": "100"})
        ]
        return "Сайты", таблица(["Сайт", "Тип", "Домены", "Модулей"], строки)

    def _контент(self, лицо, параметры):
        записи = self._данные("content", лицо, {"per_page": "50", **параметры})
        строки = [[э(z.get("id", "")), э(z.get("name", "")), э(z.get("provenance", "")),
                   э(z.get("updated_at", ""))] for z in записи]
        поиск = ('<form method="get" class="act"><input name="q" placeholder="поиск" '
                 'style="background:#1a1d27;border:1px solid #262a35;color:#e6e8ee;'
                 'padding:6px 10px;border-radius:6px"> <button>Найти</button></form>')
        return "Контент", поиск + таблица(["ID", "Название", "Происхождение", "Обновлено"], строки)

    def _редакция(self, лицо, параметры):
        может = "editorial:write" in {p.value for p in лицо.permissions}
        форма = (
            '<form method="post" class="card">'
            '<input type="hidden" name="kind" value="editorial.create">'
            '<p><input name="site_id" placeholder="site_id" style="background:#1a1d27;'
            'border:1px solid #262a35;color:#e6e8ee;padding:6px 10px;border-radius:6px"></p>'
            '<p><textarea name="payload" rows="3" style="width:100%;background:#1a1d27;'
            'border:1px solid #262a35;color:#e6e8ee;padding:8px;border-radius:6px">'
            '{"title": "", "description": ""}</textarea></p>'
            '<button>Сохранить черновик</button></form>'
        ) if может else '<p class="dim">Нет права <code>editorial:write</code>.</p>'
        return "Редакция", форма + '<div class="note">Черновик не публикуется сам: ' \
            'публикация — отдельная команда с отдельным правом.</div>'

    def _полки(self, лицо, параметры):
        строки = [[э(s.get("id", "")), э(s.get("site_id", "")), э(s.get("title", "")),
                   э(s.get("items", ""))] for s in self._данные("shelves", лицо, {"per_page": "50"})]
        return "Полки", таблица(["Полка", "Сайт", "Заголовок", "Записей"], строки)

    def _расписание(self, лицо, параметры):
        строки = [[э(z.get("air_date", "")), э(z.get("title", "")), э(z.get("source", "")),
                   э(z.get("confidence", ""))] for z in self._данные("schedules", лицо, {"per_page": "50"})]
        return "Расписание", (
            '<div class="note">Показывается только подтверждённое источником. '
            'Предположение не превращается в факт: у записи без даты выхода дата не '
            'подставляется из времени наблюдения.</div>'
            + таблица(["Дата эфира", "Произведение", "Источник", "Достоверность"], строки)
        )

    def _задания(self, лицо, параметры):
        команды = self.canary.api.commands.as_list()
        строки = [[э(c["command_id"][:12]), э(c["kind"]), э(c["state"]), э(c["actor"]),
                   э(c["site_id"] or "—"), э(c["updated_at"][11:19])] for c in команды[-30:]]
        может = "ingestion:run" in {p.value for p in лицо.permissions}
        форма = (
            '<form method="post" class="card">'
            '<input type="hidden" name="kind" value="ingestion.run">'
            '<p><input name="site_id" placeholder="site_id" style="background:#1a1d27;'
            'border:1px solid #262a35;color:#e6e8ee;padding:6px 10px;border-radius:6px">'
            ' <input name="idempotency_key" placeholder="ключ повтора" style="background:#1a1d27;'
            'border:1px solid #262a35;color:#e6e8ee;padding:6px 10px;border-radius:6px"></p>'
            '<button>Запустить загрузку</button></form>'
        ) if может else '<p class="dim">Нет права <code>ingestion:run</code>.</p>'
        return "Задания", форма + таблица(
            ["Команда", "Вид", "Состояние", "Автор", "Сайт", "Обновлена"], строки)

    def _релизы(self, лицо, параметры):
        строки = [[э(d.get("id", "")), э(d.get("site_id", "")), э(d.get("revision", "")),
                   э(d.get("state", ""))] for d in self._данные("deployments", лицо, {"per_page": "50"})]
        опасно = "publish:production" in {p.value for p in лицо.permissions}
        кнопка = (
            '<form method="post" class="card">'
            '<input type="hidden" name="kind" value="release.publish">'
            '<input type="hidden" name="confirmed" value="1">'
            '<p><input name="site_id" placeholder="site_id" style="background:#1a1d27;'
            'border:1px solid #262a35;color:#e6e8ee;padding:6px 10px;border-radius:6px">'
            ' <input name="reason" placeholder="причина" style="background:#1a1d27;'
            'border:1px solid #262a35;color:#e6e8ee;padding:6px 10px;border-radius:6px"></p>'
            '<button class="danger">Опубликовать (требует подтверждения)</button></form>'
        ) if опасно else '<p class="dim">Публикация в production доступна только владельцу.</p>'
        return "Релизы", кнопка + таблица(["Выкладка", "Сайт", "Ревизия", "Состояние"], строки)

    def _доступ(self, лицо, параметры):
        строки = [
            [э(p.principal_id), э(", ".join(r.value for r in p.roles)),
             э(", ".join(sorted(p.sites)) or "все"),
             э(len(p.permissions))]
            for p in self.canary.api.principals.values()
        ]
        роли = таблица(
            ["Роль", "Права"],
            [[э(r.value), э(", ".join(sorted(x.value for x in perms)))]
             for r, perms in ROLE_PERMISSIONS.items()],
        )
        return "Доступ", таблица(["Лицо", "Роли", "Сайты", "Прав"], строки) + "<h1>Роли</h1>" + роли

    def _аудит(self, лицо, параметры):
        события = list(self.canary.api.audit)
        строки = [[э(e.at.isoformat()[11:19]), э(e.actor), э(e.action), э(e.subject[:14]),
                   э(e.correlation_id or ""), э(e.digest())] for e in события[-40:]]
        return "Аудит", (
            '<div class="note">Журнал только дописывается. У каждой записи есть отпечаток: '
            'подмена содержимого перестаёт быть незаметной.</div>'
            + таблица(["Время", "Автор", "Действие", "Объект", "Связь", "Отпечаток"], строки)
        )


def serve(api: ControlPlaneApi, *, host: str = "127.0.0.1", port: int = 8710) -> tuple[Any, CmsCanary]:
    canary = CmsCanary(api)
    Обработчик.canary = canary
    сервер = ThreadingHTTPServer((host, port), Обработчик)
    return сервер, canary
