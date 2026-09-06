"""Разметка админки.

Серверный рендеринг без клиентского каркаса: панель показывает состояние и
отправляет формы, для этого достаточно HTML. Каркас пришлось бы обновлять по
своему расписанию, а не по расписанию задач панели.

Всё, что пришло извне — идентификаторы витрин, значения настроек, тексты
ошибок API, записи журнала, — проходит через html.escape. Значения приходят из
профилей и ответов API, то есть из мест, куда пишет не только эта панель.
"""

from __future__ import annotations

import html
import json
from contextvars import ContextVar
from typing import Any

from factory.site_engine.admin import CSRF_FIELD

STYLE = """
:root{--bg:#f7f7f8;--fg:#16161a;--mut:#5f6470;--line:#dcdde3;--card:#fff;
--ok:#1a7f45;--warn:#8a6100;--bad:#a32020;--acc:#25457a}
@media(prefers-color-scheme:dark){:root{--bg:#15161a;--fg:#e8e8ec;--mut:#9aa0ad;
--line:#2c2e36;--card:#1d1e24;--ok:#4cc98a;--warn:#e0b050;--bad:#f08585;--acc:#7aa2e0}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{border-bottom:1px solid var(--line);padding:14px clamp(10px,4vw,20px);display:flex;
align-items:center;gap:16px;flex-wrap:wrap}
header h1{font-size:16px;margin:0;font-weight:650}
header .sp{flex:1}
main{max-width:1000px;margin:0 auto;padding:22px clamp(10px,4vw,20px) 60px}
a{color:var(--acc)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:16px clamp(10px,3vw,18px);margin:0 0 14px}
.card h2{margin:0 0 10px;font-size:15px}
/* min(260px,100%) вместо 260px: при двукратном увеличении на узком экране
   жёсткий минимум делает содержимое шире окна и появляется горизонтальная
   прокрутка — читать панель приходится в два движения. */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(260px,100%),1fr));gap:12px}
dl{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;margin:8px 0 0;font-size:14px}
dt{color:var(--mut)}
dd{margin:0;overflow-wrap:anywhere}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px}
.ok .dot{background:var(--ok)} .warn .dot{background:var(--warn)} .bad .dot{background:var(--bad)}
.hint{color:var(--mut);font-size:13px;margin:4px 0 0}
form{margin:10px 0 0}
label{display:block;font-size:13px;color:var(--mut);margin:8px 0 3px}
input,select,textarea{width:100%;padding:7px 9px;border:1px solid var(--line);
border-radius:7px;background:var(--bg);color:var(--fg);font:inherit;font-size:14px}
button{padding:7px 14px;border:1px solid var(--line);border-radius:7px;
background:var(--acc);color:#fff;font:inherit;font-size:14px;cursor:pointer}
button.ghost{background:transparent;color:var(--fg)}
.row{display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap;margin-top:10px}
.row>*{flex:1;min-width:130px} .row>button{flex:0 0 auto}
.flash{border-radius:9px;padding:11px 14px;margin:0 0 14px;font-size:14px;border:1px solid}
.flash.ok{border-color:var(--ok);color:var(--ok)}
.flash.bad{border-color:var(--bad);color:var(--bad)}
.flash pre{margin:7px 0 0;white-space:pre-wrap;font-size:12.5px;color:var(--fg)}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{text-align:left;padding:6px 9px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:500}
code{font:12.5px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}
.mut{color:var(--mut)}
.tag{display:inline-block;border:1px solid var(--line);border-radius:20px;
padding:1px 9px;font-size:12px;color:var(--mut);margin:0 4px 4px 0}
"""

#: Стили разделов очереди. Держатся отдельной строкой, чтобы правка очереди не
#: трогала общий вид панели.
STYLE += """
.tabs{display:flex;flex-wrap:wrap;gap:.5rem;margin:.75rem 0}
.tab{padding:.35rem .7rem;border:1px solid #d0d7de;border-radius:999px;
  text-decoration:none;color:inherit;font-size:.9rem}
.tab.on{background:#0969da;color:#fff;border-color:#0969da}
.tab b{font-weight:600}
/* Утверждения обязаны переноситься. nowrap держал строку шире экрана, и на
   390px и при 200% увеличении появлялась горизонтальная прокрутка — поймано
   браузерной проверкой в обоих движках. */
.claim{display:inline-block;margin-right:.75rem}
/* Широкую таблицу прокручивает её собственная обёртка, а не страница:
   горизонтальная прокрутка body уводит из зоны видимости всю разметку. */
.scroll-x{overflow-x:auto;-webkit-overflow-scrolling:touch}
.scroll-x table{min-width:32rem}
/* Длинный идентификатор и адрес не должны растягивать страницу. */
code,dd{overflow-wrap:anywhere}
.claims{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(280px,100%),1fr));
  gap:1rem}
.claim-box{border:1px solid #d0d7de;border-radius:8px;padding:.9rem}
.claim-box h3{margin:.1rem 0 .6rem;font-size:1.1rem}
.pager{display:flex;gap:1rem;align-items:center;justify-content:space-between;
  flex-wrap:wrap;margin-top:.75rem}
.pill{display:inline-block;padding:.15rem .55rem;border-radius:999px;
  font-size:.8rem;border:1px solid #d0d7de}
.pill.ok{background:#dafbe1;border-color:#4ac26b}
.pill.warn{background:#fff8c5;border-color:#d4a72c}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:.45rem .5rem;border-bottom:1px solid #eaeef2;
  vertical-align:top}
@media (prefers-color-scheme:dark){
  .claim-box,.tab,.pill{border-color:#30363d}
  .pill.ok{background:#12261e;border-color:#2ea043}
  .pill.warn{background:#272115;border-color:#9e6a03}
  th,td{border-bottom-color:#21262d}
}
"""


# Состояние совместимости → класс подсветки. Неуправляемая витрина обязана
# отличаться от исправной с одного взгляда, а не при чтении текста.
_STATE_KIND = {"ok": "ok", "unversioned": "warn", "degraded": "warn", "incompatible": "bad"}
_STATE_WORDS = {
    "ok": "контракт согласован",
    "unversioned": "контракт не объявлен",
    "degraded": "работает ограниченно",
    "incompatible": "управление запрещено",
}


#: Базовый путь контура админки. У общего контура это «/admin», у контура
#: сайта — «/s/<siteId>/admin». Значение живёт в контекстной переменной, а не в
#: глобальной: сервер обслуживает запросы в нескольких потоках, и глобальная
#: переменная перепутала бы контуры соседних запросов.
БАЗА: ContextVar[str] = ContextVar("admin_base", default="/admin")

#: Название витрины в контуре сайта. Пусто — общий контур. Показывается в
#: заголовке и на странице входа: вход без имени сайта — это общий вход, а не
#: вход этого сайта, и человек не может убедиться, что пришёл куда хотел.
БРЕНД: ContextVar[str] = ContextVar("admin_brand", default="")


def _путь() -> str:
    """Начало всех адресов панели. Пропущенный вызов виден проверкой разметки."""
    return БАЗА.get()


def _бренд() -> str:
    """Название контура для заголовка. Пусто у общего контура."""
    return БРЕНД.get()


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def page(title: str, body: str, *, session_label: str = "", csrf: str = "") -> str:
    массив = (
        f'<a href="{_путь()}/fleet">Массив</a>' if _путь() == "/admin" else ""
    )
    nav = ""
    if session_label:
        nav = (
            f'<span class="mut">{_e(session_label)}</span>'
            f'<form method="post" action="{_путь()}/logout" style="margin:0">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            f'<button class="ghost" type="submit">Выйти</button></form>'
        )
    return (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        f"<title>{_e(title)} — {_e(_бренд() or 'админка фабрики')}</title><style>{STYLE}</style></head><body>"
        f'<header><h1><a href="{_путь()}" style="color:inherit;text-decoration:none">'
        f"{_e(_бренд() or 'Админка фабрики')}</a></h1>"
        f'<a href="{_путь()}/overview">Сводка</a>'
        f'<a href="{_путь()}/content">Каталог</a>'
        f'<a href="{_путь()}/review">Разбор</a>'
        f'<a href="{_путь()}/jobs">Задания</a>'
        f'<a href="{_путь()}/sites">Витрины</a>'
        f'<a href="{_путь()}/users">Люди</a>'
        f'<a href="{_путь()}/settings">Настройки</a>'
        f'<a href="{_путь()}/releases">Выпуски</a>'
        f'<a href="{_путь()}/incidents">Происшествия</a>'
        f'<a href="{_путь()}/new-site">Новая витрина</a>'
        f'<a href="{_путь()}/readiness">Готовность</a>'
        # Ссылка на массив показывается только вне контура витрины: в контуре её
        # видеть некому, а видимая ссылка у местного администратора —
        # приглашение проверить, что будет.
        f'{массив}'
        f'<a href="{_путь()}/audit">Журнал</a><span class="sp"></span>'
        f"{nav}</header><main>{body}</main></body></html>"
    )


def login(*, error: str = "", bootstrap: bool = False) -> str:
    """Вход по учётной записи.

    Поле токена показывается только пока каталог операторов пуст: это окно
    начальной настройки, и оно закрывается само, как только появился первый
    активный оператор. Постоянный вход в обход каталога обесценил бы и
    блокировку, и отзыв сессий, и журнал — в нём был бы виден токен, а не
    человек.
    """
    warn = f'<div class="flash bad">{_e(error)}</div>' if error else ""
    начальная = (
        (
            '<div class="card"><h2>Начальная настройка</h2>'
            '<p class="hint">Учётных записей ещё нет. Пока их нет, можно войти '
            "токеном Control API и завести первого администратора. После этого "
            "вход по токену закроется сам.</p>"
            f'<form method="post" action="{_путь()}/login">'
            '<label for="tok">Токен</label>'
            '<input id="tok" name="token" type="password" autocomplete="off" required>'
            '<div class="row"><button type="submit">Войти токеном</button></div>'
            "</form></div>"
        )
        if bootstrap
        else ""
    )
    return page(
        "Вход",
        warn + '<div class="card"><h2>Вход</h2>'
        f'<form method="post" action="{_путь()}/login">'
        '<label for="em">Адрес</label>'
        '<input id="em" name="email" type="email" autocomplete="username" required>'
        '<label for="pw">Пароль</label>'
        '<input id="pw" name="password" type="password" '
        'autocomplete="current-password" required>'
        '<div class="row"><button type="submit">Войти</button></div></form></div>' + начальная,
    )


def accept_invite(*, error: str = "", secret: str = "") -> str:
    """Принятие приглашения: пароль задаёт приглашённый, а не приглашающий."""
    warn = f'<div class="flash bad">{_e(error)}</div>' if error else ""
    return page(
        "Приглашение",
        warn + '<div class="card"><h2>Принять приглашение</h2>'
        '<p class="hint">Пароль задаёте вы. Он не известен тому, кто вас '
        "пригласил, и нигде не хранится в открытом виде.</p>"
        f'<form method="post" action="{_путь()}/invite/accept">'
        f'<input type="hidden" name="secret" value="{_e(secret)}">'
        '<label for="pw">Новый пароль (не короче 12 символов)</label>'
        '<input id="pw" name="password" type="password" minlength="12" '
        'autocomplete="new-password" required>'
        '<div class="row"><button type="submit">Принять</button></div>'
        "</form></div>",
    )


def invite_created(приглашение: dict, секрет: str, *, session_label: str, csrf: str) -> str:
    """Секрет приглашения показывается прямо в ответе, а не через перенаправление.

    Причина не в удобстве: значение, пронесённое через перенаправление, живёт
    в сессии до следующего запроса. Одноразовый секрет не должен нигде
    задерживаться — ни на диске, ни в памяти между запросами.
    """
    return page(
        "Приглашение создано",
        '<div class="card ok"><h2>Приглашение создано</h2>'
        f'<p>Адрес: <b>{_e(приглашение.get("email", ""))}</b>, роли: '
        f'{_e(", ".join(приглашение.get("roles") or []))}.</p>'
        '<p class="hint">Ссылка показывается один раз. Она нигде не хранится '
        "в открытом виде: на диске лежит только её отпечаток.</p>"
        f'<p><code id="invite-link">{_путь()}/invite?secret={_e(секрет)}</code></p>'
        f'<p class="mut">Действует до {_e(приглашение.get("expiresAt", ""))}.</p>'
        f'<p><a href="{_путь()}/users">← К списку людей</a></p></div>',
        session_label=session_label,
        csrf=csrf,
    )


def users(
    данные: dict,
    приглашения: list,
    сессии: list,
    *,
    flash: dict | None,
    session_label: str,
    csrf: str,
    может: bool,
    свой_id: str,
    витрины: list | None = None,
    своя_витрина: str = "",
    супер: bool = False,
) -> str:
    """Люди, их роли, приглашения и активные сессии на одном экране."""
    строки = []
    for o in данные.get("items") or []:
        свой = o["operatorId"] == свой_id
        действия = ""
        if может and not свой:
            выбор = "".join(
                f'<option value="{_e(r)}"{" selected" if r in o["roles"] else ""}>'
                f"{_e(r)}</option>"
                for r in ("viewer", "reviewer", "editor", "operator", "admin")
            )
            действия = (
                f'<form method="post" action="{_путь()}/users/{_e(o["operatorId"])}/roles">'
                f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
                f'<select name="role" aria-label="Роль">{выбор}</select>'
                '<button type="submit">Роль</button></form>'
                + (
                    f'<form method="post" action="{_путь()}/users/{_e(o["operatorId"])}/unblock">'
                    f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
                    '<button class="ghost" type="submit">Разблокировать</button></form>'
                    if o["state"] == "BLOCKED"
                    else f'<form method="post" action="{_путь()}/users/{_e(o["operatorId"])}/block">'
                    f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
                    '<input name="reason" placeholder="причина" required>'
                    '<button class="ghost" type="submit">Заблокировать</button></form>'
                )
                + f'<form method="post" action="{_путь()}/users/{_e(o["operatorId"])}/revoke-sessions">'
                f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
                '<button class="ghost" type="submit">Отозвать сессии</button></form>'
            )
        elif свой:
            действия = '<span class="mut">это вы</span>'
        строки.append(
            f'<tr><td>{_e(o["email"])}</td>'
            f'<td>{" ".join(f"<code>{_e(r)}</code>" for r in o["roles"]) or "—"}</td>'
            f'<td><span class="pill {"ok" if o["state"] == "ACTIVE" else "warn"}">'
            f'{_e(o["state"])}</span></td>'
            f'<td class="mut">{_e(o["mfaState"])}</td>'
            f"<td>{действия}</td></tr>"
        )

    приглашения_html = "".join(
        f'<tr><td>{_e(i["email"])}</td><td>{" ".join(_e(r) for r in i["roles"])}</td>'
        f'<td><span class="pill">{_e(i["state"])}</span></td>'
        f'<td class="mut">{_e(i["expiresAt"])}</td>'
        + (
            f'<td><form method="post" action="{_путь()}/users/invites/{_e(i["inviteId"])}/revoke">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            '<button class="ghost" type="submit">Отозвать</button></form></td>'
            if может and i["state"] == "PENDING"
            else "<td></td>"
        )
        + "</tr>"
        for i in приглашения
    )

    сессии_html = "".join(
        f'<tr><td>{_e(s.get("email") or s["operatorId"][:12])}'
        + (
            f'<br><span class="mut">{_e(" ".join(s.get("roles") or []))}</span>'
            if s.get("roles")
            else ""
        )
        + f'</td><td class="mut">{_e(s["createdAt"])}</td>'
        f'<td class="mut">{_e(s["lastSeen"])}</td><td class="mut">{_e(s["userAgent"])}</td>'
        + (
            f'<td><form method="post" action="{_путь()}/users/sessions/revoke">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            f'<input type="hidden" name="sessionId" value="{_e(s["sessionId"])}">'
            '<button class="ghost" type="submit">Отозвать</button></form></td>'
            if может
            else "<td></td>"
        )
        + "</tr>"
        for s in сессии
    )

    форма = (
        ""
        if not может
        else '<div class="card"><h2>Пригласить</h2>'
        '<p class="hint">Секрет приглашения показывается один раз и '
        "нигде не хранится в открытом виде.</p>"
        f'<form method="post" action="{_путь()}/users/invites">'
        f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
        '<label>Адрес<input name="email" type="email" required></label>'
        + (
            # Витрину выбирает только тот, кто вправе приглашать не к себе.
            # Местному администратору поле не показывается вовсе: значение
            # берётся из его сессии, а поле формы, задающее тенанта, — это и
            # есть смена тенанта снаружи.
            '<label>Витрина<select name="siteId">'
            + "".join(
                f'<option value="{_e(с)}">{_e(с)}</option>' for с in (витрины or [])
            )
            + '</select></label>'
            '<label><input type="checkbox" name="superAdmin" value="1"> '
            "супер-администратор (без витрины)</label>"
            if супер
            else f'<p class="hint">Приглашение выдаётся на витрину '
            f"<code>{_e(своя_витрина)}</code>: приглашать на чужую нельзя.</p>"
        )
        + '<label>Роль<select name="role">'
        + "".join(
            f'<option value="{r}">{r}</option>'
            for r in ("viewer", "reviewer", "editor", "operator", "admin")
        )
        + "</select></label>"
        '<button type="submit">Создать приглашение</button></form></div>'
    )

    return page(
        "Люди",
        _flash(flash) + '<div class="card"><h2>Операторы</h2><div class="scroll-x"><table>'
        "<thead><tr><th>Адрес</th><th>Роли</th><th>Состояние</th>"
        "<th>Второй фактор</th><th>Действия</th></tr></thead><tbody>"
        + ("".join(строки) or '<tr><td colspan="5" class="mut">Пусто.</td></tr>')
        + "</tbody></table></div></div>"
        + форма
        + '<div class="card"><h2>Приглашения</h2><div class="scroll-x"><table>'
        "<thead><tr><th>Адрес</th><th>Роли</th><th>Состояние</th><th>До</th>"
        "<th></th></tr></thead><tbody>"
        + (приглашения_html or '<tr><td colspan="5" class="mut">Нет.</td></tr>')
        + "</tbody></table></div></div>"
        + '<div class="card"><h2>Активные сессии</h2><div class="scroll-x"><table>'
        "<thead><tr><th>Чья сессия</th><th>Начата</th><th>Последний запрос</th>"
        "<th>Клиент</th><th></th></tr></thead><tbody>"
        + (сессии_html or '<tr><td colspan="5" class="mut">Нет.</td></tr>')
        + "</tbody></table></div></div>",
        session_label=session_label,
        csrf=csrf,
    )


def _flash(flash: dict | None) -> str:
    if not flash:
        return ""
    kind = "ok" if flash.get("ok") else "bad"
    detail = flash.get("detail")
    block = ""
    if detail:
        block = f"<pre>{_e(json.dumps(detail, ensure_ascii=False, indent=2))}</pre>"
    return f'<div class="flash {kind}">{_e(flash.get("message", ""))}{block}</div>'


def dashboard(
    sites: list[dict],
    *,
    flash: dict | None,
    session_label: str,
    csrf: str,
    read_problem: str = "",
    compat_by_site: dict[str, dict] | None = None,
) -> str:
    if read_problem:
        body = _flash(flash) + f'<div class="flash bad">{_e(read_problem)}</div>'
        return page("Витрины", body, session_label=session_label, csrf=csrf)
    cards = []
    for site in sites:
        sid = site.get("site_id", "")
        domains = ", ".join(site.get("domains") or [])
        state = (compat_by_site or {}).get(sid, {})
        kind = _STATE_KIND.get(state.get("state", ""), "")
        words = _STATE_WORDS.get(state.get("state", ""), "состояние неизвестно")
        cards.append(
            f'<div class="card {kind or "ok"}"><h2><span class="dot"></span>'
            f'<a href="{_путь()}/sites/{_e(sid)}">{_e(sid)}</a></h2>'
            f'<dl><dt>Тип</dt><dd>{_e(site.get("site_type"))}</dd>'
            f'<dt>Домены</dt><dd>{_e(domains)}</dd>'
            f'<dt>Рендеринг</dt><dd>{_e(site.get("render_mode"))}</dd>'
            f'<dt>Контракт</dt><dd>{_e(words)}</dd></dl></div>'
        )
    listing = "".join(cards) or '<div class="card"><p class="hint">Витрин нет.</p></div>'
    return page(
        "Витрины",
        _flash(flash) + f'<p class="hint">Витрин: {len(sites)}</p>'
        f'<div class="grid">{listing}</div>',
        session_label=session_label,
        csrf=csrf,
    )


def _dl(pairs: list[tuple[str, Any]]) -> str:
    return "<dl>" + "".join(f"<dt>{_e(k)}</dt><dd>{_e(v)}</dd>" for k, v in pairs) + "</dl>"


def site_detail(
    site_id: str,
    *,
    info: dict,
    config: dict,
    coverage: dict,
    scopes: list[str],
    flash: dict | None,
    session_label: str,
    csrf: str,
    compatibility: dict | None = None,
) -> str:
    hidden = f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
    tags = "".join(f'<span class="tag">{_e(s)}</span>' for s in scopes)

    overview = (
        f'<div class="card"><h2>{_e(site_id)}</h2>'
        + _dl(
            [
                ("Тип", info.get("site_type")),
                ("Домены", ", ".join(info.get("domains") or [])),
                ("Локаль", info.get("locale")),
                ("Рендеринг", info.get("render_mode")),
                ("Модулей", len(info.get("modules") or [])),
            ]
        )
        + f'<p class="hint">Права токена: {tags or "нет"}</p></div>'
    )

    состояние = ""
    if compatibility:
        kind = _STATE_KIND.get(compatibility.get("state", ""), "warn")
        состояние = (
            f'<div class="card {kind}"><h2><span class="dot"></span>Контракт CMS</h2>'
            + _dl(
                [
                    ("Состояние", _STATE_WORDS.get(compatibility.get("state", ""), "неизвестно")),
                    ("Объявлено витриной", compatibility.get("declared") or "не объявлено"),
                    ("Реализует движок", compatibility.get("engine")),
                    ("Управление", "разрешено" if compatibility.get("manageable") else "запрещено"),
                ]
            )
            + f'<p class="hint">{_e(compatibility.get("reason", ""))}</p></div>'
        )

    cov = (
        ('<div class="card"><h2>Полнота каталога</h2>' + _dl(list(coverage.items())[:8]) + "</div>")
        if coverage
        else ""
    )

    # Действия показываются по правам токена. Сокрытие — удобство: запрет
    # всё равно применяется на уровне API, а не здесь.
    actions = []
    if "jobs:write" in scopes:
        actions.append(
            f'<div class="card"><h2>Задание</h2>'
            f'<form method="post" action="{_путь()}/sites/{_e(site_id)}/jobs">{hidden}'
            '<div class="row">'
            '<div><label for="act">Действие</label>'
            '<select id="act" name="action">'
            '<option value="reindex">reindex</option>'
            '<option value="refresh">refresh</option>'
            '<option value="enrich">enrich</option>'
            '<option value="verify">verify</option></select></div>'
            '<div><label for="env">Среда</label>'
            '<select id="env" name="environment">'
            '<option value="staging">staging</option>'
            '<option value="production">production</option></select></div>'
            '<button name="dryRun" value="1" type="submit">Проверить</button>'
            '<button name="dryRun" value="" type="submit">Поставить</button>'
            "</div></form>"
            '<p class="hint">«Проверить» показывает, что произошло бы, и ничего не меняет.</p>'
            "</div>"
        )
    if "cache:write" in scopes:
        actions.append(
            f'<div class="card"><h2>Кэш</h2>'
            f'<form method="post" action="{_путь()}/sites/{_e(site_id)}/cache">{hidden}'
            '<div class="row">'
            '<div><label for="scope">Область</label>'
            '<select id="scope" name="scope">'
            '<option value="catalog">catalog</option>'
            '<option value="homepage">homepage</option>'
            '<option value="shelves">shelves</option>'
            '<option value="title">title</option></select></div>'
            '<div><label for="keys">Ключи через запятую</label>'
            '<input id="keys" name="keys" placeholder="для области title обязательны"></div>'
            '<button name="dryRun" value="1" type="submit">Проверить</button>'
            '<button name="dryRun" value="" type="submit">Сбросить</button>'
            "</div></form></div>"
        )
    if "config:write" in scopes:
        current = _e(
            json.dumps(
                {
                    k: config.get(k)
                    for k in ("keep_releases", "cache_policy", "feature_flags")
                    if k in config
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        actions.append(
            f'<div class="card"><h2>Настройки</h2>'
            f'<p class="hint">Изменяются только обратимые настройки ядра. Домены, '
            f"канонический хост и флаги индексации отклоняются намеренно.</p>"
            f"<pre><code>{current}</code></pre>"
            f'<form method="post" action="{_путь()}/sites/{_e(site_id)}/settings">{hidden}'
            '<div class="row">'
            '<div><label for="key">Настройка</label>'
            '<select id="key" name="key">'
            '<option value="keep_releases">keep_releases</option>'
            '<option value="cache_policy">cache_policy</option>'
            '<option value="feature_flags">feature_flags</option></select></div>'
            '<div><label for="val">Значение (JSON)</label>'
            '<input id="val" name="value" placeholder="8 или {&quot;homepage_ttl&quot;:60}"></div>'
            '<button name="dryRun" value="1" type="submit">Проверить</button>'
            '<button name="dryRun" value="" type="submit">Применить</button>'
            "</div></form>"
            '<p class="hint">Применение сверяет версию: при чужой правке между чтением '
            "и записью вы получите отказ, а не тихую перезапись.</p></div>"
        )

    return page(
        site_id,
        _flash(flash)
        + f'<p><a href="{_путь()}">← ко всем витринам</a></p>'
        + overview
        + состояние
        + cov
        + "".join(actions),
        session_label=session_label,
        csrf=csrf,
    )


def _отбор_журнала(отбор: dict) -> str:
    """Форма отбора. Значения возвращаются в поля: иначе после отбора не видно,
    что именно отобрано, и следующий запрос делают вслепую."""
    поле = lambda имя, подпись, ширина="": (  # noqa: E731
        f'<div><label for="ф-{имя}">{_e(подпись)}</label>'
        f'<input id="ф-{имя}" name="{имя}" value="{_e(отбор.get(имя, ""))}"{ширина}></div>'
    )
    исход = отбор.get("result", "")
    выбор = "".join(
        f'<option value="{v}"{" selected" if исход == v else ""}>{_e(п)}</option>'
        for v, п in (("", "любой"), ("ok", "удача"), ("error", "отказ"))
    )
    return (
        '<div class="card"><h2>Отбор</h2>'
        f'<form method="get" action="{_путь()}/audit"><div class="row">'
        + поле("actor", "Кто")
        + поле("siteId", "Витрина")
        + поле("action", "Действие (начало имени)")
        + поле("correlationId", "Идентификатор связи")
        + '<div><label for="ф-result">Исход</label>'
        f'<select id="ф-result" name="result">{выбор}</select></div>'
        + поле("since", "С (ISO)")
        + поле("until", "По (ISO)")
        + '<button type="submit">Отобрать</button>'
        f'<a class="ghost" href="{_путь()}/audit">Сбросить</a>'
        "</div></form></div>"
    )


def audit(
    entries: list[dict],
    *,
    total: int,
    session_label: str,
    csrf: str,
    flash: dict | None = None,
    matched: int | None = None,
    отбор: dict | None = None,
) -> str:
    rows = []
    for e in reversed(entries):
        mark = "мутация" if e.get("mutation") else "чтение/отказ"
        # Действующее лицо и исход показываются прямо в строке: без них отбор по
        # ним нечем проверить глазами, а именно эти два поля спрашивают первыми.
        актор = (e.get("extra") or {}).get("actor") or e.get("actor") or ""
        код = e.get("exit_code")
        исход = "удача" if код == 0 or код is None else "отказ"
        rows.append(
            f"<tr><td><code>{_e(e.get('ts'))}</code></td>"
            f"<td>{_e(актор)}</td>"
            f"<td>{_e(e.get('site_id'))}</td>"
            f"<td><code>{_e(e.get('action'))}</code></td>"
            f"<td>{_e(e.get('target'))}</td>"
            f'<td><span class="pill {"ok" if исход == "удача" else "warn"}">{_e(исход)}</span></td>'
            f"<td>{_e(mark)}</td>"
            f"<td><code>{_e((e.get('extra') or {}).get('correlation_id', ''))}</code></td></tr>"
        )
    table = (
        (
            '<div class="scroll-x"><table><thead><tr><th>Время</th><th>Кто</th>'
            "<th>Витрина</th><th>Действие</th>"
            "<th>Цель</th><th>Исход</th><th>Род</th>"
            "<th>Идентификатор связи</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>"
        )
        if rows
        else '<p class="hint">Записей нет.</p>'
    )
    подошло = total if matched is None else matched
    пояснение = (
        f"Показаны последние {len(entries)} из {подошло} подошедших; всего записей {total}. "
        "Отказы записываются наравне с удачными операциями."
    )
    пусто = (
        ""
        if entries or подошло
        else '<p class="hint">Под отбор не подошла ни одна запись. Это ноль совпадений, '
        "а не пустой журнал.</p>"
    )
    return page(
        "Журнал",
        _flash(flash)
        + _отбор_журнала(отбор or {})
        + '<div class="card"><h2>Журнал операций</h2>'
        f'<p class="hint">{пояснение}</p>{пусто}'
        f"{table}</div>",
        session_label=session_label,
        csrf=csrf,
    )


# ---------------------------------------------------------------------------
# Очередь разбора
# ---------------------------------------------------------------------------
#: Сколько записей на странице. Не «все»: очередь на двести тридцать записей
#: не читается человеком целиком, а запрос за ней успевает подвесить страницу.
REVIEW_PAGE = 25


def _состояние_класс(состояние: str) -> str:
    return {
        "OPEN": "warn",
        "IN_REVIEW": "warn",
        "RESOLVED": "ok",
        "DISMISSED": "ok",
        "REVERTED": "warn",
    }.get(состояние, "")


def review_list(
    данные: dict,
    *,
    фильтры: dict,
    flash: dict | None,
    session_label: str,
    csrf: str,
    может_решать: bool,
) -> str:
    """Список спорных записей.

    Показывает оба утверждения прямо в строке. Без этого редактор вынужден
    открывать каждую карточку, чтобы понять, о чём вообще спор, — а спор у
    всех 231 записи один и тот же по форме и разный по существу.
    """
    состояния = данные.get("byState") or {}
    вкладки = "".join(
        f'<a class="tab{" on" if фильтры.get("state") == с else ""}" '
        f'href="{_путь()}/review?state={_e(с)}">{_e(с)} <b>{состояния.get(с, 0)}</b></a>'
        for с in ("OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED")
    )
    вкладки = (
        f'<a class="tab{" on" if not фильтры.get("state") else ""}" '
        f'href="{_путь()}/review">Все <b>{данные.get("totalAll", 0)}</b></a>' + вкладки
    )

    строки = []
    for i in данные.get("items") or []:
        утв = " ".join(
            f'<span class="claim"><b>{_e(c["value"])}</b> '
            f'<span class="mut">{_e(c["source"])}</span></span>'
            for c in i.get("claims") or []
        )
        строки.append(
            f'<tr><td><a href="{_путь()}/review/{_e(i["itemId"])}">{_e(i["title"] or "(без названия)")}</a>'
            f'<div class="mut">{_e(i["siteId"])} · {i.get("year") or "год неизвестен"}</div></td>'
            f"<td>{утв}</td>"
            f'<td><span class="pill {_состояние_класс(i["state"])}">{_e(i["state"])}</span>'
            + (
                f'<div class="mut">{_e(i["decidedValue"])} · {_e(i["decidedBy"])}</div>'
                if i.get("decidedValue")
                else ""
            )
            + f'</td><td class="mut">{_e(i["conflictCode"])}</td></tr>'
        )

    если_пусто = (
        '<tr><td colspan="4" class="mut">Записей нет. Это не ошибка: '
        "очередь пуста, когда спорных записей не осталось.</td></tr>"
    )
    смещение = int(данные.get("offset", 0))
    предел = int(данные.get("limit", REVIEW_PAGE))
    всего = int(данные.get("total", 0))
    состояние_параметр = f'&state={_e(фильтры["state"])}' if фильтры.get("state") else ""
    навигация = (
        '<div class="pager">'
        + (
            f'<a href="{_путь()}/review?offset={max(0, смещение - предел)}{состояние_параметр}">← Назад</a>'
            if смещение > 0
            else '<span class="mut">← Назад</span>'
        )
        + f'<span class="mut">{смещение + 1}–{min(всего, смещение + предел)} из {всего}</span>'
        + (
            f'<a href="{_путь()}/review?offset={смещение + предел}{состояние_параметр}">Вперёд →</a>'
            if смещение + предел < всего
            else '<span class="mut">Вперёд →</span>'
        )
        + "</div>"
    )

    групповое = ""
    if может_решать:
        групповое = (
            '<div class="card"><h2>Групповое решение</h2>'
            '<p class="mut">Сначала сухой прогон: он покажет число, разницу и '
            "поимённую выборку. Применить можно только тот набор, который был "
            "показан.</p>"
            f'<form method="get" action="{_путь()}/review/batch">'
            '<label>Код конфликта<input name="conflictCode" '
            'value="PROVIDER_TYPE_VS_KIND_TAG"></label>'
            '<label>Из значения<input name="fromValue" placeholder="MOVIE"></label>'
            '<label>В значение<input name="toValue" placeholder="OVA"></label>'
            '<button type="submit">Сухой прогон</button></form></div>'
        )

    return page(
        "Очередь разбора",
        _flash(flash)
        + '<div class="card"><h2>Спорные записи</h2>'
        + '<p class="mut">Оба утверждения принадлежат одному источнику и '
        "противоречат друг другу. Система не выбирает за редактора: "
        "рекомендации здесь нет, потому что оснований для неё нет.</p>"
        + f'<div class="tabs">{вкладки}</div>'
        + '<div class="scroll-x"><table><thead><tr><th>Тайтл</th>'
        "<th>Утверждения</th><th>Состояние</th><th>Конфликт</th></tr></thead><tbody>"
        + ("".join(строки) or если_пусто)
        + "</tbody></table></div>"
        + навигация
        + "</div>"
        + групповое,
        session_label=session_label,
        csrf=csrf,
    )


def _поток(i: dict, сверка: dict | None, csrf: str, может: bool) -> str:
    """Путь решения до витрины: сверка, утверждение, публикация, откат.

    Утверждение и публикация разведены намеренно. Записанное решение — ещё не
    изменение витрины, и человек, нажимающий «опубликовать», обязан видеть
    сверку «было/стало», а не доверять строке в списке.
    """
    if not сверка:
        return ""
    состояние = i.get("state", "")
    разница = (
        '<div class="card"><h2>Что изменится на витрине</h2>'
        + _dl(
            [
                ("Было", сверка.get("before")),
                ("Станет", сверка.get("after")),
                ("Опубликовано", "да" if сверка.get("published") else "нет"),
            ]
        )
        + "</div>"
    )
    действия = ""
    if может and состояние == "RESOLVED":
        действия += (
            f'<form method="post" action="{_путь()}/review/{_e(i["itemId"])}/approve">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            f'<input type="hidden" name="expectedVersion" value="{i["version"]}">'
            '<label>Чем подтверждено решение<input name="note" required></label>'
            "<button type=\"submit\">Утвердить</button></form>"
            '<p class="mut">Утверждает не тот, кто решил: второй шаг нужен ради '
            "второй пары глаз, а не ради второго нажатия.</p>"
        )
    if может and состояние == "APPROVED":
        действия += (
            f'<form method="post" action="{_путь()}/review/{_e(i["itemId"])}/publish">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            f'<input type="hidden" name="expectedVersion" value="{i["version"]}">'
            "<button type=\"submit\">Опубликовать на витрину</button></form>"
        )
    if может and состояние == "PUBLISHED":
        действия += (
            f'<form method="post" action="{_путь()}/review/{_e(i["itemId"])}/unpublish">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            '<label>Причина отката<input name="note" required></label>'
            '<button class="ghost" type="submit">Снять с витрины</button></form>'
        )
    return разница + (f'<div class="card"><h2>Публикация</h2>{действия}</div>' if действия else "")


def review_item(
    i: dict,
    *,
    flash: dict | None,
    session_label: str,
    csrf: str,
    может_решать: bool,
    сверка: dict | None = None,
) -> str:
    """Карточка спорной записи: оба утверждения, доказательства, история."""
    утверждения = "".join(
        f'<div class="claim-box"><h3>{_e(c["value"])}</h3>'
        f'<dl><dt>Источник</dt><dd>{_e(c["source"])}</dd>'
        f'<dt>Доказательство</dt><dd><code>{_e(c["evidence"])}</code></dd>'
        f'<dt>Уверенность</dt><dd>{c.get("confidence", 0)}</dd></dl>'
        + (
            f'<form method="post" action="{_путь()}/review/{_e(i["itemId"])}/decide">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            f'<input type="hidden" name="value" value="{_e(c["value"])}">'
            f'<input type="hidden" name="expectedVersion" value="{i["version"]}">'
            f'<label>Обоснование<input name="note" required '
            f'placeholder="почему выбрано это значение"></label>'
            f'<button type="submit">Выбрать {_e(c["value"])}</button></form>'
            if может_решать and i["state"] in ("OPEN", "IN_REVIEW")
            else ""
        )
        + "</div>"
        for c in i.get("claims") or []
    )

    история = "".join(
        f'<tr><td class="mut">{_e(h.get("at", ""))}</td><td>{_e(h.get("action", ""))}</td>'
        f'<td>{_e(h.get("value", ""))}</td><td>{_e(h.get("actor", ""))}</td>'
        f'<td class="mut">{_e(h.get("note", ""))}</td></tr>'
        for h in i.get("history") or []
    )

    идентификаторы = ", ".join(
        f"{_e(k)}:{_e(v)}" for k, v in sorted((i.get("externalIds") or {}).items())
    )
    действия = ""
    if может_решать and i["state"] == "OPEN":
        действия += (
            f'<form method="post" action="{_путь()}/review/{_e(i["itemId"])}/claim">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            "<button class=\"ghost\" type=\"submit\">Взять в работу</button></form>"
        )
    if может_решать and i["state"] in ("RESOLVED", "DISMISSED"):
        действия += (
            f'<form method="post" action="{_путь()}/review/{_e(i["itemId"])}/revert">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            '<label>Причина отмены<input name="note" required></label>'
            '<button class="ghost" type="submit">Отменить решение</button></form>'
        )
    if может_решать and i["state"] in ("OPEN", "IN_REVIEW"):
        действия += (
            f'<form method="post" action="{_путь()}/review/{_e(i["itemId"])}/decide">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            f'<input type="hidden" name="dismiss" value="1">'
            f'<input type="hidden" name="expectedVersion" value="{i["version"]}">'
            '<label>Почему конфликт незначащий<input name="note" required></label>'
            '<button class="ghost" type="submit">Признать незначащим</button></form>'
        )

    return page(
        i.get("title") or "Запись",
        _flash(flash)
        + f'<p><a href="{_путь()}/review">← К очереди</a></p>'
        + f'<div class="card"><h2>{_e(i.get("title") or "(без названия)")}</h2>'
        + _dl(
            [
                ("Витрина", i.get("siteId")),
                ("Год", i.get("year") or "неизвестен"),
                ("Сезон", i.get("seasonNumber") if i.get("seasonNumber") is not None else "—"),
                ("Поле", i.get("field")),
                ("Конфликт", i.get("conflictCode")),
                ("Состояние", i.get("state")),
                ("Версия", i.get("version")),
                ("Идентификаторы", идентификаторы or "нет"),
                ("Сущность", i.get("internalEntityId")),
            ]
        )
        + (f'<p class="mut">{_e(i.get("recommendationReason", ""))}</p>')
        + "</div>"
        + f'<div class="card"><h2>Утверждения</h2><div class="claims">{утверждения}</div>'
        + '<p class="mut">Третье значение ввести нельзя: очередь разрешает '
        "выбрать между утверждениями источников, а не придумать своё.</p></div>"
        + _поток(i, сверка, csrf, может_решать)
        + (f'<div class="card"><h2>Действия</h2>{действия}</div>' if действия else "")
        + '<div class="card"><h2>История</h2><div class="scroll-x"><table>'
        "<thead><tr><th>Когда</th><th>Действие</th><th>Значение</th><th>Кто</th>"
        "<th>Примечание</th></tr></thead><tbody>"
        + (история or '<tr><td colspan="5" class="mut">Действий ещё не было.</td></tr>')
        + "</tbody></table></div></div>",
        session_label=session_label,
        csrf=csrf,
    )


def review_batch(предпросмотр: dict, *, session_label: str, csrf: str) -> str:
    """Сухой прогон группового решения. Применение — отдельным нажатием."""
    выборка = "".join(
        f'<tr><td>{_e(s["title"])}</td><td class="mut">{s.get("year") or ""}</td>'
        f'<td class="mut">{_e(s["siteId"])}</td></tr>'
        for s in предпросмотр.get("sample") or []
    )
    причины = "".join(
        f"<li>{_e(k)}: {v}</li>" for k, v in (предпросмотр.get("skippedReasons") or {}).items()
    )
    однороден = предпросмотр.get("homogeneous")
    предупреждение = (
        ""
        if однороден
        else (
            '<div class="flash bad">Набор неоднороден: групповое действие '
            "допустимо только для одного доказанного класса конфликта.</div>"
        )
    )
    можно = однороден and предпросмотр.get("affected", 0) > 0
    return page(
        "Сухой прогон",
        f'<p><a href="{_путь()}/review">← К очереди</a></p>'
        + предупреждение
        + '<div class="card"><h2>Что будет сделано</h2>'
        + _dl(
            [
                ("Код конфликта", предпросмотр.get("conflictCode")),
                ("Из значения", предпросмотр.get("fromValue") or "(любое)"),
                ("В значение", предпросмотр.get("toValue")),
                ("Затронуто записей", предпросмотр.get("affected")),
                ("Пропущено", предпросмотр.get("skipped")),
                ("Отпечаток набора", предпросмотр.get("versionFingerprint")),
            ]
        )
        + (f'<ul class="mut">{причины}</ul>' if причины else "")
        + "</div>"
        + '<div class="card"><h2>Выборка</h2><div class="scroll-x"><table>'
        "<thead><tr><th>Тайтл</th><th>Год</th><th>Витрина</th></tr></thead><tbody>"
        + (выборка or '<tr><td colspan="3" class="mut">Пусто.</td></tr>')
        + "</tbody></table></div></div>"
        + (
            (
                '<div class="card"><h2>Применить</h2>'
                f'<form method="post" action="{_путь()}/review/batch">'
                f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
                f'<input type="hidden" name="conflictCode" value="{_e(предпросмотр.get("conflictCode", ""))}">'
                f'<input type="hidden" name="fromValue" value="{_e(предпросмотр.get("fromValue", ""))}">'
                f'<input type="hidden" name="toValue" value="{_e(предпросмотр.get("toValue", ""))}">'
                f'<input type="hidden" name="expectedFingerprint" value="{_e(предпросмотр.get("versionFingerprint", ""))}">'
                '<label>Чем доказан однородный класс<input name="note" required></label>'
                f'<button type="submit">Применить к {предпросмотр.get("affected")} записям</button>'
                "</form></div>"
            )
            if можно
            else ""
        ),
        session_label=session_label,
        csrf=csrf,
    )


# ---------------------------------------------------------------------------
# Сводка
# ---------------------------------------------------------------------------
def _доля(значение) -> str:
    """Доля или честный прочерк. Ноль вместо неизмеренного — это ложь."""
    return "—" if значение is None else f"{значение:.1%}"


def _число(значение) -> str:
    return "—" if значение is None else f"{значение}"


def _возраст(секунды) -> str:
    if секунды is None:
        return "неизвестно"
    if секунды < 90:
        return f"{секунды} с"
    if секунды < 5400:
        return f"{секунды // 60} мин"
    return f"{секунды // 3600} ч {(секунды % 3600) // 60} мин"


ВАЖНОСТЬ = {"critical": "bad", "high": "bad", "medium": "warn", "low": ""}


def overview(данные: dict, *, flash: dict | None, session_label: str, csrf: str) -> str:
    """Сводка по массиву. Каждое число посчитано или отсутствует."""
    тревоги = данные.get("alerts") or []
    блок_тревог = (
        '<div class="card"><h2>Тревоги</h2>'
        + (
            "".join(
                f'<div class="flash {ВАЖНОСТЬ.get(t.get("severity"), "")}">'
                f'<b>{_e(t.get("code", ""))}</b> · {_e(t.get("subject", ""))}<br>'
                f'<span class="mut">{_e(t.get("detail", ""))}</span></div>'
                for t in тревоги
            )
            or '<p class="mut">Тревог нет. Пороги: свежесть '
            f'{данные.get("thresholds", {}).get("freshnessSeconds")} с, '
            f'воспроизведение '
            f'{_доля(данные.get("thresholds", {}).get("playbackCoverage"))}.</p>'
        )
        + "</div>"
    )

    строки = "".join(
        f'<tr><td><a href="{_путь()}/content?siteId={_e(в["siteId"])}">{_e(в["siteId"])}</a></td>'
        f'<td>{_число(в["titles"])}</td>'
        f'<td>{_доля(в["playbackCoverage"])}</td>'
        f'<td>{_число(в["blockedByContract"])}</td>'
        f'<td>{_число(в["ratingNumeric"])}</td>'
        f'<td><span class="pill {"ok" if в["freshnessState"] == "FRESH" else "warn"}">'
        f'{_e(в["freshnessState"])}</span> <span class="mut">'
        f'{_e(_возраст(в["freshnessSeconds"]))}</span></td></tr>'
        for в in данные.get("sites") or []
    )

    итоги = данные.get("totals") or {}
    очередь = данные.get("queue")
    очередь_html = (
        '<p class="mut">Очередь недоступна.</p>'
        if очередь is None
        else _dl(sorted(очередь.items()))
    )

    return page(
        "Сводка",
        _flash(flash)
        + блок_тревог
        + '<div class="card"><h2>Всего по массиву</h2>'
        + _dl(
            [
                ("Витрин измерено", f'{итоги.get("sitesMeasured")} из {итоги.get("sitesTotal")}'),
                ("Карточек", _число(итоги.get("titles"))),
                ("С воспроизведением", _число(итоги.get("playable"))),
                ("Покрытие", _доля(итоги.get("playbackCoverage"))),
                ("Ждут разбора", _число(данные.get("identityConflicts"))),
                ("Снято", данные.get("generatedAt", "")),
            ]
        )
        + "</div>"
        + '<div class="card"><h2>Витрины</h2><div class="scroll-x"><table>'
        "<thead><tr><th>Витрина</th><th>Карточек</th><th>Воспроизведение</th>"
        "<th>Запрещено</th><th>С оценкой</th><th>Свежесть</th></tr></thead>"
        f"<tbody>{строки or чтопусто(6)}</tbody></table></div></div>"
        + f'<div class="card"><h2>Очередь заданий</h2>{очередь_html}</div>',
        session_label=session_label,
        csrf=csrf,
    )


def чтопусто(колонок: int, текст: str = "Ничего не найдено.") -> str:
    return f'<tr><td colspan="{колонок}" class="mut">{_e(текст)}</td></tr>'


# ---------------------------------------------------------------------------
# Каталог
# ---------------------------------------------------------------------------
def content_list(
    данные: dict, *, витрины: list, flash: dict | None, session_label: str, csrf: str
) -> str:
    """Каталог витрины. Отбор выполнен на сервере, состояние живёт в ссылке."""
    site = данные.get("siteId", "")
    q = данные.get("query", "") or ""
    вид = данные.get("kind", "") or ""
    причина = данные.get("reason", "") or ""

    def ссылка(**замены) -> str:
        параметры = {
            "siteId": site,
            "q": q,
            "kind": вид,
            "reason": причина,
            "sort": данные.get("sort", "externalId"),
            "offset": данные.get("offset", 0),
        }
        параметры.update(замены)
        return f"{_путь()}/content?" + "&".join(
            f"{k}={_e(str(v))}" for k, v in параметры.items() if v not in ("", None)
        )

    выбор_витрин = "".join(
        f'<option value="{_e(s)}"{" selected" if s == site else ""}>{_e(s)}</option>'
        for s in витрины
    )
    выбор_видов = '<option value="">любой</option>' + "".join(
        f'<option value="{_e(k)}"{" selected" if k == вид else ""}>{_e(k)} ' f"({n})</option>"
        for k, n in sorted((данные.get("byKind") or {}).items())
    )
    выбор_причин = '<option value="">любая</option>' + "".join(
        f'<option value="{_e(k)}"{" selected" if k == причина else ""}>{_e(k)} ' f"({n})</option>"
        for k, n in sorted((данные.get("byReason") or {}).items())
    )

    строки = "".join(
        f'<tr><td><a href="{_путь()}/content/{_e(site)}/{_e(str(i["externalId"]))}">'
        f'{_e(str(i["title"] or "(без названия)"))}</a>'
        f'<div class="mut">{_e(str(i["externalId"]))}</div></td>'
        f'<td class="mut">{_e(str(i.get("year") or "—"))}</td>'
        f'<td><code>{_e(str(i["contentKind"]))}</code></td>'
        f'<td class="mut">{_e(str(i.get("playbackAggregator") or "—"))}</td>'
        f'<td><span class="pill {"ok" if i["playbackReason"] == "OK" else "warn"}">'
        f'{_e(str(i["playbackReason"]))}</span></td>'
        f'<td class="mut">{_e(str(i["ratingState"]))}</td></tr>'
        for i in данные.get("items") or []
    )

    смещение = int(данные.get("offset", 0))
    предел = int(данные.get("limit", 25))
    всего = int(данные.get("total", 0))
    навигация = (
        '<div class="pager">'
        + (
            f'<a href="{ссылка(offset=max(0, смещение - предел))}">← Назад</a>'
            if смещение > 0
            else '<span class="mut">← Назад</span>'
        )
        + f'<span class="mut">{(смещение + 1) if всего else 0}–'
        f'{min(всего, смещение + предел)} из {всего} '
        f'(в каталоге {данные.get("totalAll", 0)})</span>'
        + (
            f'<a href="{ссылка(offset=смещение + предел)}">Вперёд →</a>'
            if смещение + предел < всего
            else '<span class="mut">Вперёд →</span>'
        )
        + "</div>"
    )

    return page(
        "Каталог",
        _flash(flash) + '<div class="card"><h2>Отбор</h2>'
        f'<form method="get" action="{_путь()}/content">'
        f'<label>Витрина<select name="siteId">{выбор_витрин}</select></label>'
        f'<label>Поиск<input name="q" value="{_e(q)}" '
        'placeholder="название или идентификатор"></label>'
        f'<label>Вид<select name="kind">{выбор_видов}</select></label>'
        f'<label>Причина<select name="reason">{выбор_причин}</select></label>'
        '<button type="submit">Показать</button></form>'
        '<p class="mut">Отбор выполняется на сервере по всему каталогу, а не '
        "поверх текущей страницы.</p>"
        # Постоянная ссылка на текущий вид. Без неё состояние отбора живёт
        # только в кнопках постраничной навигации, а те исчезают, когда
        # результат помещается на одну страницу: оператор обновляет вкладку и
        # теряет свой отбор.
        f'<p class="mut">Ссылка на этот вид: <code>{_e(ссылка())}</code></p>'
        "</div>" + '<div class="card"><h2>Записи</h2><div class="scroll-x"><table>'
        "<thead><tr><th>Тайтл</th><th>Год</th><th>Вид</th><th>Агрегатор</th>"
        "<th>Причина</th><th>Оценка</th></tr></thead>"
        f'<tbody>{строки or чтопусто(6, "Ничего не найдено по этому отбору.")}'
        "</tbody></table></div>" + навигация + "</div>",
        session_label=session_label,
        csrf=csrf,
    )


def _оценки(оценки: dict) -> str:
    """Оценки с происхождением. Число без происхождения через месяц
    неотличимо от скачанного со стороны, поэтому источник, основание и время
    забора фида стоят рядом со значением, а не в описании раздела."""
    if not оценки:
        return ""
    состояние = str(оценки.get("state") or "")
    значения = оценки.get("values") or []
    строки = "".join(
        f'<tr><td><code>{_e(str(з.get("metric", "")))}</code></td>'
        f'<td><b>{_e(str(з.get("value", "")))}</b> '
        f'<span class="mut">из {_e(str(з.get("scale", "")))}</span></td>'
        f'<td class="mut">{_e(str(з.get("source", "")))}</td>'
        f'<td class="mut">{_e(str(з.get("legalBasis", "")))}</td>'
        f'<td class="mut">{_e(str(з.get("feedFetchedAt", "")))}</td></tr>'
        for з in значения
    )
    пояснение = ""
    if оценки.get("primaryReason") == "MULTIPLE_METRICS_NOT_RECONCILED":
        пояснение = (
            '<p class="hint">Главного значения нет намеренно: две метрики меряют '
            "разные совокупности зрителей, и выбор между ними — решение о "
            "представлении, которого владелец не принимал. Среднее не считается: "
            "это третье число, которого не сообщал никто.</p>"
        )
    elif оценки.get("reason"):
        пояснение = f'<p class="hint">{_e(str(оценки["reason"]))}</p>'
    return (
        '<div class="card"><h2>Оценки</h2>'
        f'<p><span class="pill {"ok" if состояние == "AVAILABLE" else "warn"}">'
        f"{_e(состояние)}</span></p>" + пояснение + '<div class="scroll-x"><table>'
        "<thead><tr><th>Метрика</th><th>Значение</th><th>Источник</th>"
        "<th>Основание</th><th>Фид забран</th></tr></thead><tbody>"
        + (строки or чтопусто(5, "Оценок в фиде нет."))
        + "</tbody></table></div></div>"
    )


def content_item(данные: dict, *, flash: dict | None, session_label: str, csrf: str) -> str:
    """Карточка записи: идентификаторы, происхождение, состояния, история."""
    идентификаторы = (
        ", ".join(
            f"{_e(k)}:{_e(str(v))}" for k, v in sorted((данные.get("externalIds") or {}).items())
        )
        or "нет"
    )
    источники = "".join(
        f'<li>{_e(s.get("source", ""))} · <code>{_e(str(s.get("sourceEntityId", "")))}'
        f'</code> · {_e(str(s.get("updatedAt") or ""))}</li>'
        for s in данные.get("sourceRefs") or []
    )
    история = "".join(
        f'<tr><td class="mut">{_e(str(с.get("at", "")))}</td>'
        f'<td>{_e(str(с.get("event", "")))}</td>'
        f'<td class="mut">{_e(str(с.get("actor", "")))}</td></tr>'
        for с in данные.get("timeline") or []
    )
    разбор = данные.get("review")
    разбор_html = (
        ""
        if not разбор
        else '<div class="card"><h2>Разбор</h2>'
        + _dl(
            [
                ("Состояние", разбор.get("state")),
                ("Решение", разбор.get("decidedValue") or "—"),
                ("Кто", разбор.get("decidedBy") or "—"),
            ]
        )
        + f'<p><a href="{_путь()}/review/{_e(str(разбор.get("itemId", "")))}">'
        "Открыть в очереди разбора →</a></p></div>"
    )
    оценки = данные.get("ratings") or {}
    оценки_html = _оценки(оценки)

    return page(
        str(данные.get("title") or "Запись"),
        _flash(flash) + f'<p><a href="{_путь()}/content?siteId={_e(str(данные.get("siteId", "")))}">'
        "← К каталогу</a></p>"
        + f'<div class="card"><h2>{_e(str(данные.get("title") or "(без названия)"))}</h2>'
        + _dl(
            [
                ("Витрина", данные.get("siteId")),
                ("Идентификатор", данные.get("externalId")),
                ("Год", данные.get("year") if данные.get("year") is not None else "—"),
                ("Вид", данные.get("contentKind")),
                ("Тип поставщика", данные.get("providerType")),
                ("Анимация", "да" if данные.get("isAnimation") else "не отмечено"),
                ("Теги", ", ".join(str(t) for t in данные.get("tags") or []) or "нет"),
                ("Идентификаторы", идентификаторы),
                (
                    "Сезонов",
                    данные.get("seasons") if данные.get("seasons") is not None else "неизвестно",
                ),
                (
                    "Серий",
                    данные.get("episodes") if данные.get("episodes") is not None else "неизвестно",
                ),
                (
                    "Длительность",
                    данные.get("duration") if данные.get("duration") is not None else "не измерена",
                ),
            ]
        )
        + "</div>"
        + '<div class="card"><h2>Состояния</h2>'
        + _dl(
            [
                ("Воспроизведение", данные.get("playbackReason")),
                ("Агрегатор", данные.get("playbackAggregator") or "—"),
                ("Оценка", данные.get("ratingState")),
                ("SEO", данные.get("seoState")),
                ("Конфликты вида", ", ".join(данные.get("kindConflicts") or []) or "нет"),
            ]
        )
        + f'<p class="mut">{_e(str(данные.get("kindReason", "")))}</p></div>'
        + оценки_html
        + разбор_html
        + f'<div class="card"><h2>Происхождение</h2><ul>{источники}</ul></div>'
        + '<div class="card"><h2>История</h2><div class="scroll-x"><table>'
        "<thead><tr><th>Когда</th><th>Событие</th><th>Кто</th></tr></thead>"
        f"<tbody>{история or чтопусто(3, 'Событий нет.')}</tbody></table></div></div>",
        session_label=session_label,
        csrf=csrf,
    )


# ---------------------------------------------------------------------------
# Задания и витрины
# ---------------------------------------------------------------------------
СОСТОЯНИЕ_ЗАДАНИЯ = {"SUCCEEDED": "ok", "FAILED": "bad", "BLOCKED": "warn", "UNKNOWN": ""}


def jobs(данные: dict, *, flash: dict | None, session_label: str, csrf: str) -> str:
    """Задания. Принятое в очередь не называется выполненным."""
    очередь = данные.get("queue")
    очередь_html = (
        '<p class="mut">Очередь недоступна.</p>'
        if очередь is None
        else _dl(sorted(очередь.items()))
    )
    строки = "".join(
        f'<tr><td><code>{_e(str(i.get("jobId")))}</code>'
        f'<div class="mut">{_e(str(i.get("siteId") or ""))}</div></td>'
        f'<td><span class="pill {СОСТОЯНИЕ_ЗАДАНИЯ.get(i.get("state"), "")}">'
        f'{_e(str(i.get("state")))}</span>'
        f'<div class="mut">{_e(str(i.get("status") or ""))}</div></td>'
        f'<td>{"да" if i.get("succeeded") else "нет"}</td>'
        f'<td class="mut">{_e(", ".join(i.get("failedChecks") or []) or "—")}</td>'
        f'<td class="mut">{_e(str(i.get("finishedAt") or "—"))}</td></tr>'
        for i in данные.get("items") or []
    )
    return page(
        "Задания",
        _flash(flash) + f'<div class="card"><h2>Очередь</h2>{очередь_html}'
        '<p class="mut">Принятое в очередь задание ещё не выполнено: работа '
        "начинается, когда исполнитель его заберёт.</p></div>"
        + '<div class="card"><h2>Задания</h2><div class="scroll-x"><table>'
        "<thead><tr><th>Задание</th><th>Состояние</th><th>Успех</th>"
        "<th>Не прошли</th><th>Завершено</th></tr></thead>"
        f"<tbody>{строки or чтопусто(5, 'Заданий нет.')}</tbody></table></div>"
        f'<p class="mut">Всего: {данные.get("total", 0)}. По состояниям: '
        f'{_e(str(данные.get("byState") or {}))}</p></div>',
        session_label=session_label,
        csrf=csrf,
    )


ЗДОРОВЬЕ = {"HEALTHY": "ok", "DEGRADED": "warn", "UNHEALTHY": "bad", "UNKNOWN": ""}


def sites_list(данные: dict, *, flash: dict | None, session_label: str, csrf: str) -> str:
    строки = "".join(
        f'<tr><td><a href="{_путь()}/sites/{_e(str(i.get("siteId")))}">'
        f'{_e(str(i.get("siteId")))}</a>'
        f'<div class="mut">{_e(", ".join(i.get("domains") or []))}</div></td>'
        f'<td><span class="pill {ЗДОРОВЬЕ.get((i.get("health") or {}).get("state"), "")}">'
        f'{_e(str((i.get("health") or {}).get("state")))}</span>'
        f'<div class="mut">{_e(", ".join((i.get("health") or {}).get("problems") or []))}'
        "</div></td>"
        f'<td>{_число((i.get("catalog") or {}).get("titles"))}</td>'
        f'<td>{_доля((i.get("catalog") or {}).get("playbackCoverage"))}</td>'
        f'<td class="mut">{_e(str((i.get("freshness") or {}).get("state") or ""))}</td>'
        "</tr>"
        for i in данные.get("items") or []
    )
    return page(
        "Витрины",
        _flash(flash) + '<div class="card"><h2>Витрины</h2><div class="scroll-x"><table>'
        "<thead><tr><th>Витрина</th><th>Здоровье</th><th>Карточек</th>"
        "<th>Воспроизведение</th><th>Свежесть</th></tr></thead>"
        f"<tbody>{строки or чтопусто(5, 'Витрин нет.')}</tbody></table></div>"
        '<p class="mut">Здоровье считается по содержимому каталога, а не по '
        "коду ответа: витрина с пустым каталогом отвечает 200.</p></div>",
        session_label=session_label,
        csrf=csrf,
    )


def _значение(значение) -> str:
    """Текущее значение настройки в том виде, в каком его можно ввести обратно."""
    if значение is None:
        return "—"
    if isinstance(значение, dict | list):
        return json.dumps(значение, ensure_ascii=False)
    if isinstance(значение, bool):
        return "true" if значение else "false"
    return str(значение)


def _разница(diff: dict) -> str:
    """Сравнение «было/станет» таблицей, а не текстом ответа.

    Разница возвращалась и раньше, но приходила оператору строкой в сообщении.
    Прочитать в ней, что именно поменяется, можно было только зная формат.
    """
    if not diff:
        return (
            '<div class="card"><h2>Проверка</h2>'
            '<p class="mut">Ничего не изменится: значение уже такое.</p></div>'
        )
    строки = "".join(
        f"<tr><td><code>{_e(ключ)}</code></td>"
        f"<td>было <code>{_e(_значение(пара.get('before')))}</code></td>"
        f"<td>станет <code>{_e(_значение(пара.get('after')))}</code></td></tr>"
        for ключ, пара in sorted(diff.items())
    )
    return (
        '<div class="card"><h2>Проверка</h2>'
        '<p class="hint">Ничего не записано. Это только сравнение.</p>'
        f'<div class="scroll-x"><table><tbody>{строки}</tbody></table></div></div>'
    )


def settings(
    данные: dict,
    витрины: list,
    *,
    предпросмотр: dict | None,
    flash: dict | None,
    session_label: str,
    csrf: str,
) -> str:
    """Настройки витрины: схема, значения, отклонённое, секреты, откат."""
    site_id = данные.get("siteId", "")
    может = bool(данные.get("canWrite"))
    hidden = f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
    версия = данные.get("version", "")

    выбор = "".join(
        f'<option value="{_e(s)}"{" selected" if s == site_id else ""}>{_e(s)}</option>'
        for s in витрины
    )
    переключатель = (
        f'<div class="card"><form method="get" action="{_путь()}/settings">'
        '<div class="row"><div><label for="site">Витрина</label>'
        f'<select id="site" name="site">{выбор}</select></div>'
        '<button type="submit">Открыть</button></div></form>'
        f'<p class="mut">Версия конфигурации: <code>{_e(версия)}</code></p></div>'
    )

    строки = []
    for поле in данные.get("fields") or []:
        форма = ""
        if может:
            форма = (
                f'<form method="post" action="{_путь()}/settings">{hidden}'
                f'<input type="hidden" name="site" value="{_e(site_id)}">'
                f'<input type="hidden" name="key" value="{_e(поле["key"])}">'
                f'<input type="hidden" name="expectedVersion" value="{_e(версия)}">'
                f'<input name="value" aria-label="Новое значение {_e(поле["key"])}" '
                f'value="{_e(_значение(поле.get("value")))}">'
                '<button name="dryRun" value="1" type="submit">Проверить</button>'
                '<button name="dryRun" value="" type="submit">Применить</button>'
                "</form>"
            )
        выкат = (
            "сначала на канарейке"
            if поле.get("rollout") == "canary"
            else "действует сразу целиком"
        )
        строки.append(
            f'<tr><td><code>{_e(поле["key"])}</code><br>'
            f'<span class="mut">{_e(поле.get("description", ""))}</span></td>'
            f'<td class="mut">{_e(поле.get("type", ""))}'
            + (f'<br>{_e(поле["limits"])}' if поле.get("limits") else "")
            + "</td>"
            f'<td><code>{_e(_значение(поле.get("value")))}</code></td>'
            f'<td class="mut">{_e(выкат)}</td>'
            f"<td>{форма}</td></tr>"
        )

    отказы = "".join(
        f'<tr><td><code>{_e(r["key"])}</code></td><td class="mut">{_e(r["reason"])}</td></tr>'
        for r in данные.get("refused") or []
    )

    секреты = "".join(
        f'<tr><td><code>{_e(s["key"])}</code></td><td class="mut">{_e(s.get("store", ""))}</td>'
        f'<td><code>{_e(s.get("ref", ""))}</code></td>'
        f'<td class="mut">{_e(s.get("value", ""))}</td></tr>'
        for s in данные.get("secretRefs") or []
    )

    откат = данные.get("rollback") or {}
    if откат.get("available") and может:
        назад = ", ".join(
            f"{_e(k)} → {_e(_значение(v))}" for k, v in sorted((откат.get("changes") or {}).items())
        )
        блок_отката = (
            '<div class="card"><h2>Откат</h2>'
            f'<p>Последнее изменение записано {_e(откат.get("recordedAt", ""))}. '
            f"Вернуть: {назад}.</p>"
            f'<form method="post" action="{_путь()}/settings/rollback">{hidden}'
            f'<input type="hidden" name="site" value="{_e(site_id)}">'
            '<button name="dryRun" value="1" type="submit">Проверить откат</button>'
            '<button type="submit">Откатить</button></form></div>'
        )
    else:
        причина = откат.get("reason") or "откатывать нечего"
        блок_отката = (
            f'<div class="card"><h2>Откат</h2><p class="mut">{_e(причина)}.</p></div>'
        )

    предупреждение = (
        ""
        if может
        else '<div class="flash warn">У вас нет права config:write: '
        "раздел открыт только для чтения.</div>"
    )

    return page(
        "Настройки",
        _flash(flash)
        + предупреждение
        + переключатель
        + (_разница(предпросмотр or {}) if предпросмотр is not None else "")
        + '<div class="card"><h2>Изменяемые настройки</h2>'
        '<p class="hint">Границы показаны до ввода. Значение вне границ '
        "отклоняется целиком, а не обрезается.</p>"
        '<div class="scroll-x"><table>'
        "<thead><tr><th>Настройка</th><th>Тип и границы</th><th>Сейчас</th>"
        "<th>Как действует</th><th></th></tr></thead><tbody>"
        + ("".join(строки) or чтопусто(5))
        + "</tbody></table></div></div>"
        + блок_отката
        + '<div class="card"><h2>Секреты</h2>'
        '<p class="hint">Панель показывает ссылку на хранилище. Значение '
        "секрета не читается и не отображается никогда.</p>"
        '<div class="scroll-x"><table>'
        "<thead><tr><th>Имя</th><th>Хранилище</th><th>Ссылка</th><th>Значение</th>"
        "</tr></thead><tbody>"
        + (секреты or чтопусто(4, "Секретов не подключено."))
        + "</tbody></table></div></div>"
        + '<div class="card"><h2>Отклоняется намеренно</h2>'
        '<p class="hint">Это правило, а не пробел в реализации: каждое из этих '
        "полей меняется выкладкой, а не панелью.</p>"
        '<div class="scroll-x"><table>'
        "<thead><tr><th>Поле</th><th>Почему</th></tr></thead><tbody>"
        + (отказы or чтопусто(2))
        + "</tbody></table></div></div>",
        session_label=session_label,
        csrf=csrf,
    )


def _источник_недоступен(данные: dict, что: str) -> str:
    """Недоступный источник называется словами и причиной.

    Пустая таблица на его месте читается как «ничего не было» — ровно та ложь,
    из-за которой каталог тридцатипятичасовой давности месяцами считался
    работающим.
    """
    return (
        f'<div class="card"><h2>{_e(что)}</h2>'
        '<div class="flash bad">Источник недоступен, поэтому список не показан. '
        f'Причина: {_e(данные.get("reason", "не указана"))}.</div>'
        '<p class="hint">Это не то же самое, что «записей нет».</p></div>'
    )


def releases(данные: dict, *, flash: dict | None, session_label: str, csrf: str) -> str:
    """Выпуски: что выложено, когда и куда откатываться."""
    if not данные.get("available"):
        return page(
            "Выпуски",
            _flash(flash) + _источник_недоступен(данные, "Выпуски"),
            session_label=session_label,
            csrf=csrf,
        )
    строки = "".join(
        f'<tr><td><code>{_e(з["releaseId"])}</code><br>'
        f'<span class="mut">{_e(з.get("iteration", ""))}</span></td>'
        f'<td class="mut">{_e(з.get("branch", ""))}</td>'
        f'<td><code>{_e((з.get("headSha") or "")[:12])}</code></td>'
        f'<td><code>{_e((з.get("deployedSha") or "")[:12])}</code><br>'
        f'<span class="mut">{_e(з.get("deployedAt", ""))}</span></td>'
        f'<td class="mut">{_e(з.get("component", ""))}</td>'
        + (
            f'<td><code>{_e((з.get("rollbackTo") or "")[:12])}</code></td>'
            if з.get("rollbackAvailable")
            else '<td class="mut">откат не записан</td>'
        )
        + "</tr>"
        for з in данные.get("items") or []
    )
    битые = данные.get("unreadable") or []
    предупреждение = (
        ""
        if not битые
        else '<div class="flash warn">Не прочитаны записи: '
        + _e(", ".join(битые))
        + ". Они не показаны и не учтены.</div>"
    )
    return page(
        "Выпуски",
        _flash(flash)
        + предупреждение
        + '<div class="card"><h2>Выпуски</h2>'
        f'<p class="hint">Источник: <code>{_e(данные.get("source", ""))}</code>. '
        "Панель только читает: записи ведёт координация программы.</p>"
        '<div class="scroll-x"><table><thead><tr><th>Выпуск</th><th>Ветка</th>'
        "<th>Голова</th><th>Выложено</th><th>Компонент</th><th>Откат к</th>"
        "</tr></thead><tbody>"
        + (строки or чтопусто(6, "Выпусков не записано."))
        + "</tbody></table></div></div>",
        session_label=session_label,
        csrf=csrf,
    )


def incidents(данные: dict, *, flash: dict | None, session_label: str, csrf: str) -> str:
    """Происшествия: открытые отделены от закрытых."""
    if not данные.get("available"):
        return page(
            "Происшествия",
            _flash(flash) + _источник_недоступен(данные, "Происшествия"),
            session_label=session_label,
            csrf=csrf,
        )
    строки = "".join(
        f'<tr><td><code>{_e(з["incidentId"])}</code></td>'
        f'<td>{_e(з.get("title", ""))}</td>'
        f'<td><span class="pill {"warn" if з.get("open") else "ok"}">'
        f'{_e(з.get("state", ""))}</span></td>'
        f'<td class="mut">{_e(з.get("impact", ""))}</td>'
        f'<td class="mut">{_e(з.get("detectedAt", ""))}</td></tr>'
        for з in данные.get("items") or []
    )
    открытых = данные.get("open", 0)
    сводка = (
        f'<div class="flash {"warn" if открытых else "ok"}">Открытых происшествий: '
        f"{открытых} из {данные.get('total', 0)}.</div>"
    )
    return page(
        "Происшествия",
        _flash(flash)
        + сводка
        + '<div class="card"><h2>Происшествия</h2>'
        f'<p class="hint">Источник: <code>{_e(данные.get("source", ""))}</code>. '
        "Происшествие без строки состояния считается открытым: молчаливое "
        "закрытие хуже честно неизвестного состояния.</p>"
        '<div class="scroll-x"><table><thead><tr><th>Номер</th><th>Что случилось</th>'
        "<th>Состояние</th><th>Влияние</th><th>Обнаружено</th></tr></thead><tbody>"
        + (строки or чтопусто(5, "Происшествий не записано."))
        + "</tbody></table></div></div>",
        session_label=session_label,
        csrf=csrf,
    )


#: Подписи и вид поля для каждого шага мастера. Список полей живёт рядом с
#: формой, а правила проверки — в ядре: разметка не должна решать, что годится.
ПОЛЯ_ШАГА: dict[str, list[tuple[str, str, str]]] = {
    "domain": [("domain", "Домен", "text"), ("aliases", "Псевдонимы через запятую", "text")],
    "profile": [
        ("environment", "Среда", "select:staging,production"),
        ("targetRef", "Площадка", "text"),
        ("seoProfile", "Профиль разделов", "select:catalog_authority,release_pulse,editorial_guide"),
    ],
    "content": [
        ("contentSource", "Источник", "text"),
        ("contentTypes", "Типы через запятую", "text"),
    ],
    "template": [("themeRef", "Шаблон", "text")],
    "branding": [
        ("brandName", "Название", "text"),
        ("legalName", "Юридическое лицо", "text"),
        ("primaryColor", "Основной цвет", "text"),
    ],
    "seo": [
        ("canonicalHostForm", "Канонический хост", "select:non_www,www"),
        ("trailingSlash", "Слэш на конце", "checkbox"),
    ],
    "analytics": [
        ("analyticsRef", "Ссылка на ключ аналитики", "text"),
        ("adsRef", "Ссылка на рекламный аккаунт", "text"),
    ],
    "legal": [
        ("legalEntity", "Правообладатель", "text"),
        ("contactEmail", "Контактная почта", "text"),
        ("rightsConfirmed", "Права на содержимое подтверждены", "checkbox"),
    ],
}


def _поле_шага(имя: str, подпись: str, вид: str) -> str:
    if вид.startswith("select:"):
        значения = вид.split(":", 1)[1].split(",")
        выбор = "".join(f'<option value="{_e(v)}">{_e(v)}</option>' for v in значения)
        поле = f'<select id="п-{_e(имя)}" name="{_e(имя)}">{выбор}</select>'
    elif вид == "checkbox":
        поле = f'<input id="п-{_e(имя)}" name="{_e(имя)}" type="checkbox" value="1">'
    else:
        поле = f'<input id="п-{_e(имя)}" name="{_e(имя)}">'
    return f'<div><label for="п-{_e(имя)}">{_e(подпись)}</label>{поле}</div>'


def _план(план: dict) -> str:
    """План показывается целиком: шаги, ресурсы, замки, контракты и откат."""
    if not план:
        return ""
    недостаёт = план.get("missingAssets") or []
    файлы = (
        ""
        if not недостаёт
        else '<div class="flash warn">Для публикации не хватает файлов витрины: '
        + _e(", ".join(sorted(б.get("field", "") for б in недостаёт)))
        + ". Канарейке они не мешают: она не индексируется и никому не показана.</div>"
    )
    шаги = "".join(
        f'<tr><td><code>{_e(ш["id"])}</code></td><td>{_e(ш["detail"])}</td>'
        f'<td class="mut">{"изменение" if ш.get("mutation") else "проверка"}</td></tr>'
        for ш in план.get("steps") or []
    )
    требования = "".join(
        f'<tr><td><code>{_e(т.get("step", ""))}</code></td><td>{_e(т.get("title", ""))}</td>'
        f'<td class="mut">{_e(т.get("required_input", ""))}</td></tr>'
        for т in план.get("requirements") or []
    )
    откат = "".join(
        f'<li><code>{_e(ш["id"])}</code> — {_e(ш["detail"])}</li>'
        for ш in (план.get("rollback") or {}).get("steps") or []
    )
    список = lambda имя, значения: (  # noqa: E731
        f'<p><b>{_e(имя)}:</b> '
        + ", ".join(f"<code>{_e(str(з))}</code>" for з in значения or [])
        + "</p>"
    )
    готов = план.get("canaryReady")
    return (
        файлы
        + f'<div class="card"><h2>Сухой прогон</h2>'
        f'<div class="flash {"ok" if готов else "warn"}">'
        + (
            "Заявка готова к канарейке."
            if готов
            else "Заявка ещё не готова: см. требования."
        )
        + f' Изменений выполнено: {план.get("mutations", 0)}.</div>'
        f'<p class="hint">Отпечаток плана <code>{_e(план.get("planHash", ""))}</code>. '
        "Один и тот же ввод даёт один и тот же отпечаток: подтверждают именно то, "
        "что выполнится.</p>"
        '<div class="scroll-x"><table><thead><tr><th>Шаг</th><th>Что будет сделано</th>'
        "<th>Род</th></tr></thead><tbody>"
        + (шаги or чтопусто(3))
        + "</tbody></table></div>"
        + список("Затрагиваемые ресурсы", план.get("resources"))
        + список("Замки", план.get("locks"))
        + список("Контракты", план.get("contracts"))
        + "</div>"
        + '<div class="card"><h2>Чего не хватает</h2>'
        '<div class="scroll-x"><table><thead><tr><th>Где</th><th>Что не так</th>'
        "<th>Что нужно</th></tr></thead><tbody>"
        + (требования or чтопусто(3, "Всё заполнено."))
        + "</tbody></table></div></div>"
        + f'<div class="card"><h2>Откат</h2><ul>{откат}</ul>'
        f'<p class="hint">{_e((план.get("rollback") or {}).get("note", ""))}</p></div>'
    )


#: Порядок шагов для показа «что спросят». Берётся из ядра, а не переписан
#: здесь: два списка шагов разошлись бы на первом же изменении мастера.
def _порядок_шагов() -> list[tuple[str, str, str]]:
    from factory.site_engine.site_request import ШАГИ

    return [(ш.id, ш.title, ш.подсказка) for ш in ШАГИ]


ПОРЯДОК_ШАГОВ = _порядок_шагов()


def new_site(
    заявки: list,
    заявка: dict | None,
    план: dict | None,
    *,
    может: bool,
    flash: dict | None,
    session_label: str,
    csrf: str,
) -> str:
    """Мастер заведения витрины: шаги, состояние и сухой прогон."""
    hidden = f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
    список = "".join(
        f'<tr><td><a href="{_путь()}/new-site?request={_e(з["requestId"])}">'
        f'{_e(з["siteId"])}</a></td>'
        f'<td class="mut">{_e(з.get("createdAt", ""))}</td>'
        f'<td><span class="pill {"ok" if з.get("complete") else "warn"}">'
        f'{"заполнена" if з.get("complete") else _e(з.get("nextStep") or "")}</span></td></tr>'
        for з in заявки
    )
    # Что спросят — видно до начала. Мастер, показывающий шаг только после
    # предыдущего, заставляет узнавать требования по одному: половина заявок
    # так и застревает на шаге, к которому нечего было приготовить.
    порядок = "".join(
        f'<tr><td>{n_}</td><td><code>{_e(и)}</code></td><td>{_e(п)}</td>'
        f'<td class="mut">{_e(х)}</td></tr>'
        for n_, (и, п, х) in enumerate(ПОРЯДОК_ШАГОВ, 1)
    )
    что_спросят = (
        '<div class="card"><h2>Что спросят</h2>'
        '<div class="scroll-x"><table><thead><tr><th>№</th><th>Шаг</th>'
        "<th>Название</th><th>Пояснение</th></tr></thead><tbody>"
        + порядок
        + "</tbody></table></div></div>"
    )
    создание = (
        ""
        if not может
        else '<div class="card"><h2>Новая заявка</h2>'
        '<p class="hint">Ни SSH, ни правка файлов не нужны: весь путь проходится здесь.</p>'
        f'<form method="post" action="{_путь()}/new-site">{hidden}'
        '<label for="siteId">Идентификатор витрины</label>'
        '<input id="siteId" name="siteId" placeholder="строчные буквы, цифры и дефис">'
        '<button type="submit">Завести заявку</button></form></div>'
    )

    подробно = ""
    исполнение = ""
    if заявка and может:
        состояние = заявка.get("state", "DRAFT")
        rid = _e(заявка["requestId"])
        отпечаток = _e((план or {}).get("planHash", ""))
        # Канарейку можно завести без логотипа и юридических текстов, а
        # опубликовать — нет. Это два разных ответа, и кнопка опирается на тот,
        # который относится к следующему шагу.
        готов = bool((план or {}).get("canaryReady"))
        кнопки = []
        if состояние == "DRAFT" and готов:
            кнопки.append(
                f'<form method="post" action="{_путь()}/new-site/{rid}/approve">{hidden}'
                f'<input type="hidden" name="planHash" value="{отпечаток}">'
                "<button type=\"submit\">Подтвердить план</button></form>"
            )
        if состояние == "APPROVED":
            кнопки.append(
                f'<form method="post" action="{_путь()}/new-site/{rid}/provision">{hidden}'
                "<button type=\"submit\">Выложить канарейку</button></form>"
            )
        if состояние == "PROVISIONED":
            кнопки.append(
                f'<form method="post" action="{_путь()}/new-site/{rid}/publish">{hidden}'
                '<button class="ghost" type="submit">Опубликовать</button></form>'
                f'<form method="post" action="{_путь()}/new-site/{rid}/rollback">{hidden}'
                "<button type=\"submit\">Откатить</button></form>"
            )
        пояснение = {
            "DRAFT": "План подтверждают до выкладки: подтверждение привязано к отпечатку, "
            "и после изменения ответов его придётся дать заново.",
            "APPROVED": "Выкладка создаёт канарейку под NOINDEX в отдельном наложении. "
            "В общий каталог витрин она не попадает.",
            "PROVISIONED": "Публикация в боевой контур требует разрешения владельца и "
            "мастером не выдаётся. Откат снимает всё созданное и освобождает домен.",
            "ROLLED_BACK": "Откат выполнен: наложение, состояние канарейки и бронь домена сняты.",
        }.get(состояние, "")
        исполнение = (
            f'<div class="card"><h2>Исполнение</h2>'
            f'<p>Состояние заявки: <span class="pill '
            f'{"ok" if состояние in ("APPROVED", "PROVISIONED") else "warn"}">'
            f'{_e(состояние)}</span></p>'
            f'<p class="hint">{_e(пояснение)}</p>'
            f'<div class="row">{"".join(кнопки) or "<span class=&quot;mut&quot;>Действий нет.</span>"}'
            "</div></div>"
        )
    if заявка:
        шаги = "".join(
            f'<tr><td><code>{_e(ш["id"])}</code></td><td>{_e(ш["title"])}</td>'
            f'<td><span class="pill {"ok" if ш["done"] else "warn"}">'
            f'{"готово" if ш["done"] else "ждёт"}</span></td>'
            f'<td class="mut">{_e(ш["hint"])}</td></tr>'
            for ш in заявка.get("steps") or []
        )
        следующий = заявка.get("nextStep")
        форма = ""
        if может and следующий:
            поля = "".join(
                _поле_шага(*описание) for описание in ПОЛЯ_ШАГА.get(следующий, [])
            )
            форма = (
                f'<div class="card"><h2>Шаг: {_e(следующий)}</h2>'
                f'<form method="post" action="{_путь()}/new-site/{_e(заявка["requestId"])}">'
                f'{hidden}<input type="hidden" name="step" value="{_e(следующий)}">'
                f'<div class="row">{поля}<button type="submit">Дальше</button></div>'
                "</form></div>"
            )
        подробно = (
            f'<div class="card"><h2>Заявка на {_e(заявка["siteId"])}</h2>'
            '<div class="scroll-x"><table><thead><tr><th>Шаг</th><th>Что спрашивают</th>'
            "<th>Состояние</th><th>Пояснение</th></tr></thead><tbody>"
            + шаги
            + "</tbody></table></div></div>"
            + форма
            + исполнение
            + _план(план or {})
        )

    return page(
        "Новая витрина",
        _flash(flash)
        + создание
        + что_спросят
        + '<div class="card"><h2>Заявки</h2><div class="scroll-x"><table>'
        "<thead><tr><th>Витрина</th><th>Заведена</th><th>Состояние</th></tr></thead><tbody>"
        + (список or чтопусто(3, "Заявок нет."))
        + "</tbody></table></div></div>"
        + подробно,
        session_label=session_label,
        csrf=csrf,
    )


def _источники_оценок(данные: dict) -> str:
    """Почему оценок нет. Причина называется, а не подразумевается.

    Пустой раздел на этом месте читался бы как «оценки просто не сделали».
    Оценок нет потому, что ни один источник не разрешён, — и это решение
    владельца, которое видно здесь целиком, вместе с объяснением по каждому
    источнику.
    """
    if not данные:
        return ""
    строки = "".join(
        f'<tr><td><code>{_e(и["id"])}</code></td>'
        f'<td><span class="pill {"ok" if и["authorization"]["status"] == "granted" else "warn"}">'
        f'{_e(и["authorization"]["status"])}</span></td>'
        f'<td class="mut">{_e(и["authorization"].get("reason", ""))}</td>'
        f'<td class="mut">{_e(и["authorization"].get("document", "") or "—")}</td></tr>'
        for и in данные.get("known") or []
    )
    блокер = данные.get("blocker") or ""
    return (
        '<div class="card"><h2>Источники оценок</h2>'
        + (f'<div class="flash warn">{_e(блокер)}</div>' if блокер else "")
        + '<div class="scroll-x"><table><thead><tr><th>Источник</th><th>Разрешение</th>'
        "<th>Почему</th><th>Документ</th></tr></thead><tbody>"
        + (строки or чтопусто(4))
        + "</tbody></table></div></div>"
    )


def readiness(
    табель: dict,
    тревоги: dict,
    опись: dict,
    оценки: dict | None = None,
    *,
    flash: dict | None,
    session_label: str,
    csrf: str,
) -> str:
    """Готовность: оценки с основанием, тревоги с инструкцией, опись состояния."""
    строки = "".join(
        f'<tr><td><code>{_e(в["id"])}</code></td>'
        + (
            f'<td><span class="pill {"ok" if (в.get("score") or 0) >= 8 else "warn"}">'
            f'{_e(str(в["score"]))}</span></td>'
            if в.get("measured")
            else '<td><span class="pill warn">не измерено</span></td>'
        )
        + f'<td class="mut">{_e(в.get("basis", ""))}</td></tr>'
        for в in табель.get("gates") or []
    )
    тревоги_html = "".join(
        f'<tr><td><code>{_e(т["code"])}</code></td>'
        f'<td><span class="pill {"warn" if т.get("severity") != "info" else ""}">'
        f'{_e(т.get("severity", ""))}</span></td>'
        f'<td>{_e(т.get("meaning", ""))}</td>'
        f'<td><code>{_e(т.get("runbook", ""))}</code></td></tr>'
        for т in тревоги.get("items") or []
    )
    опись_html = "".join(
        f'<tr><td><code>{_e(х["id"])}</code></td>'
        f'<td class="mut">{_e(х.get("path", ""))}</td>'
        f'<td>{_e(х.get("meaning", ""))}</td>'
        f'<td><span class="pill {"ok" if х.get("present") else "warn"}">'
        f'{"есть" if х.get("present") else "пусто"}</span></td>'
        f'<td class="mut">{_число(х.get("files"))}</td></tr>'
        for х in опись.get("items") or []
    )
    измерено = табель.get("measuredCount", 0)
    всего = табель.get("total", 0)
    return page(
        "Готовность",
        _flash(flash)
        + f'<div class="card"><h2>Табель</h2>'
        f'<p class="hint">Измерено {измерено} из {всего}. Неизмеренное показано '
        "как «не измерено» и не имеет числа: оценка «примерно» — то же усреднение, "
        "которым закрывают ворота без доказательств.</p>"
        '<div class="scroll-x"><table><thead><tr><th>Ворота</th><th>Оценка</th>'
        "<th>На чём основана</th></tr></thead><tbody>"
        + (строки or чтопусто(3))
        + "</tbody></table></div></div>"
        + '<div class="card"><h2>Тревоги и инструкции</h2>'
        '<p class="hint">Код без инструкции сообщает дежурному, что что-то не так, '
        "и ничего не говорит о том, что делать.</p>"
        '<div class="scroll-x"><table><thead><tr><th>Код</th><th>Значимость</th>'
        "<th>Что означает</th><th>Инструкция</th></tr></thead><tbody>"
        + (тревоги_html or чтопусто(4))
        + "</tbody></table></div></div>"
        + _источники_оценок(оценки or {})
        + '<div class="card"><h2>Состояние службы</h2>'
        '<p class="hint">Хранилище, не попавшее в опись, не попадёт и в копию — '
        "и обнаружится это при восстановлении.</p>"
        '<div class="scroll-x"><table><thead><tr><th>Хранилище</th><th>Путь</th>'
        "<th>Что там</th><th>Наличие</th><th>Файлов</th></tr></thead><tbody>"
        + (опись_html or чтопусто(5))
        + "</tbody></table></div></div>",
        session_label=session_label,
        csrf=csrf,
    )


def fleet(витрины: list, *, flash: dict | None, session_label: str, csrf: str) -> str:
    """Массив витрин: состояние, признаки и переход в контур каждой.

    Список, который надо собирать переходами по сайтам, на практике не
    собирают. Поэтому массив виден одним экраном, и с него же происходит
    переключение — явное, а не как побочный эффект открытия чужой страницы.
    """
    hidden = f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
    строки = "".join(
        f'<tr><td><a href="/s/{_e(в["siteId"])}/admin">{_e(в.get("brand") or в["siteId"])}</a>'
        f'<br><span class="mut">{_e(в["siteId"])}</span></td>'
        f'<td class="mut">{_e(", ".join(в.get("domains") or []) or "—")}</td>'
        f'<td class="mut">{_e(в.get("family") or "—")}</td>'
        f'<td><span class="pill {"ok" if в.get("registration") else "warn"}">'
        f'{"регистрация включена" if в.get("registration") else "регистрация выключена"}'
        "</span></td>"
        f'<td><form method="post" action="{_путь()}/fleet/switch">{hidden}'
        f'<input type="hidden" name="siteId" value="{_e(в["siteId"])}">'
        '<button type="submit">Открыть</button></form></td></tr>'
        for в in витрины
    )
    return page(
        "Массив витрин",
        _flash(flash)
        + '<div class="card"><h2>Витрины массива</h2>'
        '<p class="hint">Переход в контур витрины записывается в журнал: по нему '
        "должно быть видно, кто и куда смотрел.</p>"
        '<div class="scroll-x"><table><thead><tr><th>Витрина</th><th>Домены</th>'
        "<th>Семейство</th><th>Регистрация</th><th></th></tr></thead><tbody>"
        + (строки or чтопусто(5, "Витрин нет."))
        + "</tbody></table></div></div>",
        session_label=session_label,
        csrf=csrf,
    )

