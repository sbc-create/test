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


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def page(title: str, body: str, *, session_label: str = "", csrf: str = "") -> str:
    nav = ""
    if session_label:
        nav = (
            f'<span class="mut">{_e(session_label)}</span>'
            f'<form method="post" action="/admin/logout" style="margin:0">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            f'<button class="ghost" type="submit">Выйти</button></form>'
        )
    return (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        f"<title>{_e(title)} — админка фабрики</title><style>{STYLE}</style></head><body>"
        '<header><h1><a href="/admin" style="color:inherit;text-decoration:none">'
        "Админка фабрики</a></h1>"
        '<a href="/admin/overview">Сводка</a>'
        '<a href="/admin/content">Каталог</a>'
        '<a href="/admin/review">Разбор</a>'
        '<a href="/admin/users">Люди</a>'
        '<a href="/admin/audit">Журнал</a><span class="sp"></span>'
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
            '<form method="post" action="/admin/login">'
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
        '<form method="post" action="/admin/login">'
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
        '<form method="post" action="/admin/invite/accept">'
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
        f'<p><code id="invite-link">/admin/invite?secret={_e(секрет)}</code></p>'
        f'<p class="mut">Действует до {_e(приглашение.get("expiresAt", ""))}.</p>'
        '<p><a href="/admin/users">← К списку людей</a></p></div>',
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
                f'<form method="post" action="/admin/users/{_e(o["operatorId"])}/roles">'
                f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
                f'<select name="role" aria-label="Роль">{выбор}</select>'
                '<button type="submit">Роль</button></form>'
                + (
                    f'<form method="post" action="/admin/users/{_e(o["operatorId"])}/unblock">'
                    f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
                    '<button class="ghost" type="submit">Разблокировать</button></form>'
                    if o["state"] == "BLOCKED"
                    else f'<form method="post" action="/admin/users/{_e(o["operatorId"])}/block">'
                    f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
                    '<input name="reason" placeholder="причина" required>'
                    '<button class="ghost" type="submit">Заблокировать</button></form>'
                )
                + f'<form method="post" action="/admin/users/{_e(o["operatorId"])}/revoke-sessions">'
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
            f'<td><form method="post" action="/admin/users/invites/{_e(i["inviteId"])}/revoke">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            '<button class="ghost" type="submit">Отозвать</button></form></td>'
            if может and i["state"] == "PENDING"
            else "<td></td>"
        )
        + "</tr>"
        for i in приглашения
    )

    сессии_html = "".join(
        f'<tr><td>{_e(s["operatorId"][:12])}</td><td class="mut">{_e(s["createdAt"])}</td>'
        f'<td class="mut">{_e(s["lastSeen"])}</td><td class="mut">{_e(s["userAgent"])}</td>'
        + (
            f'<td><form method="post" action="/admin/users/sessions/revoke">'
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
        '<form method="post" action="/admin/users/invites">'
        f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
        '<label>Адрес<input name="email" type="email" required></label>'
        '<label>Роль<select name="role">'
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
        "<thead><tr><th>Оператор</th><th>Начата</th><th>Последний запрос</th>"
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
            f'<a href="/admin/sites/{_e(sid)}">{_e(sid)}</a></h2>'
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
            f'<form method="post" action="/admin/sites/{_e(site_id)}/jobs">{hidden}'
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
            f'<form method="post" action="/admin/sites/{_e(site_id)}/cache">{hidden}'
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
            f'<form method="post" action="/admin/sites/{_e(site_id)}/settings">{hidden}'
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
        + '<p><a href="/admin">← ко всем витринам</a></p>'
        + overview
        + состояние
        + cov
        + "".join(actions),
        session_label=session_label,
        csrf=csrf,
    )


def audit(
    entries: list[dict], *, total: int, session_label: str, csrf: str, flash: dict | None = None
) -> str:
    rows = []
    for e in reversed(entries):
        mark = "мутация" if e.get("mutation") else "чтение/отказ"
        rows.append(
            f"<tr><td><code>{_e(e.get('ts'))}</code></td>"
            f"<td>{_e(e.get('site_id'))}</td>"
            f"<td><code>{_e(e.get('action'))}</code></td>"
            f"<td>{_e(e.get('target'))}</td>"
            f"<td>{_e(mark)}</td>"
            f"<td><code>{_e((e.get('extra') or {}).get('correlation_id', ''))}</code></td></tr>"
        )
    table = (
        (
            '<div class="scroll-x"><table><thead><tr><th>Время</th>'
            "<th>Витрина</th><th>Действие</th>"
            "<th>Цель</th><th>Род</th><th>Идентификатор связи</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>"
        )
        if rows
        else '<p class="hint">Записей нет.</p>'
    )
    return page(
        "Журнал",
        _flash(flash) + f'<div class="card"><h2>Журнал операций</h2>'
        f'<p class="hint">Показаны последние {len(entries)} из {total}. '
        "Отказы записываются наравне с удачными операциями.</p>"
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
        f'href="/admin/review?state={_e(с)}">{_e(с)} <b>{состояния.get(с, 0)}</b></a>'
        for с in ("OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED")
    )
    вкладки = (
        f'<a class="tab{" on" if not фильтры.get("state") else ""}" '
        f'href="/admin/review">Все <b>{данные.get("totalAll", 0)}</b></a>' + вкладки
    )

    строки = []
    for i in данные.get("items") or []:
        утв = " ".join(
            f'<span class="claim"><b>{_e(c["value"])}</b> '
            f'<span class="mut">{_e(c["source"])}</span></span>'
            for c in i.get("claims") or []
        )
        строки.append(
            f'<tr><td><a href="/admin/review/{_e(i["itemId"])}">{_e(i["title"] or "(без названия)")}</a>'
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
            f'<a href="/admin/review?offset={max(0, смещение - предел)}{состояние_параметр}">← Назад</a>'
            if смещение > 0
            else '<span class="mut">← Назад</span>'
        )
        + f'<span class="mut">{смещение + 1}–{min(всего, смещение + предел)} из {всего}</span>'
        + (
            f'<a href="/admin/review?offset={смещение + предел}{состояние_параметр}">Вперёд →</a>'
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
            '<form method="get" action="/admin/review/batch">'
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
            f'<form method="post" action="/admin/review/{_e(i["itemId"])}/approve">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            f'<input type="hidden" name="expectedVersion" value="{i["version"]}">'
            '<label>Чем подтверждено решение<input name="note" required></label>'
            "<button type=\"submit\">Утвердить</button></form>"
            '<p class="mut">Утверждает не тот, кто решил: второй шаг нужен ради '
            "второй пары глаз, а не ради второго нажатия.</p>"
        )
    if может and состояние == "APPROVED":
        действия += (
            f'<form method="post" action="/admin/review/{_e(i["itemId"])}/publish">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            f'<input type="hidden" name="expectedVersion" value="{i["version"]}">'
            "<button type=\"submit\">Опубликовать на витрину</button></form>"
        )
    if может and состояние == "PUBLISHED":
        действия += (
            f'<form method="post" action="/admin/review/{_e(i["itemId"])}/unpublish">'
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
            f'<form method="post" action="/admin/review/{_e(i["itemId"])}/decide">'
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
            f'<form method="post" action="/admin/review/{_e(i["itemId"])}/claim">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            "<button class=\"ghost\" type=\"submit\">Взять в работу</button></form>"
        )
    if может_решать and i["state"] in ("RESOLVED", "DISMISSED"):
        действия += (
            f'<form method="post" action="/admin/review/{_e(i["itemId"])}/revert">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            '<label>Причина отмены<input name="note" required></label>'
            '<button class="ghost" type="submit">Отменить решение</button></form>'
        )
    if может_решать and i["state"] in ("OPEN", "IN_REVIEW"):
        действия += (
            f'<form method="post" action="/admin/review/{_e(i["itemId"])}/decide">'
            f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
            f'<input type="hidden" name="dismiss" value="1">'
            f'<input type="hidden" name="expectedVersion" value="{i["version"]}">'
            '<label>Почему конфликт незначащий<input name="note" required></label>'
            '<button class="ghost" type="submit">Признать незначащим</button></form>'
        )

    return page(
        i.get("title") or "Запись",
        _flash(flash)
        + '<p><a href="/admin/review">← К очереди</a></p>'
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
        '<p><a href="/admin/review">← К очереди</a></p>'
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
                '<form method="post" action="/admin/review/batch">'
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
        f'<tr><td><a href="/admin/content?siteId={_e(в["siteId"])}">{_e(в["siteId"])}</a></td>'
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
        return "/admin/content?" + "&".join(
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
        f'<tr><td><a href="/admin/content/{_e(site)}/{_e(str(i["externalId"]))}">'
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
        '<form method="get" action="/admin/content">'
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
        + f'<p><a href="/admin/review/{_e(str(разбор.get("itemId", "")))}">'
        "Открыть в очереди разбора →</a></p></div>"
    )
    оценки = данные.get("ratings") or {}

    return page(
        str(данные.get("title") or "Запись"),
        _flash(flash) + f'<p><a href="/admin/content?siteId={_e(str(данные.get("siteId", "")))}">'
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
                (
                    "Кинопоиск",
                    оценки.get("kinopoisk")
                    if оценки.get("kinopoisk") is not None
                    else "нет данных",
                ),
                ("IMDb", оценки.get("imdb") if оценки.get("imdb") is not None else "нет данных"),
                ("SEO", данные.get("seoState")),
                ("Конфликты вида", ", ".join(данные.get("kindConflicts") or []) or "нет"),
            ]
        )
        + f'<p class="mut">{_e(str(данные.get("kindReason", "")))}</p></div>'
        + разбор_html
        + f'<div class="card"><h2>Происхождение</h2><ul>{источники}</ul></div>'
        + '<div class="card"><h2>История</h2><div class="scroll-x"><table>'
        "<thead><tr><th>Когда</th><th>Событие</th><th>Кто</th></tr></thead>"
        f"<tbody>{история or чтопусто(3, 'Событий нет.')}</tbody></table></div></div>",
        session_label=session_label,
        csrf=csrf,
    )
