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
header{border-bottom:1px solid var(--line);padding:14px 20px;display:flex;
align-items:center;gap:16px;flex-wrap:wrap}
header h1{font-size:16px;margin:0;font-weight:650}
header .sp{flex:1}
main{max-width:1000px;margin:0 auto;padding:22px 20px 60px}
a{color:var(--acc)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:16px 18px;margin:0 0 14px}
.card h2{margin:0 0 10px;font-size:15px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
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
        "<!doctype html><html lang=\"ru\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<meta name=\"robots\" content=\"noindex,nofollow\">"
        f"<title>{_e(title)} — админка фабрики</title><style>{STYLE}</style></head><body>"
        '<header><h1><a href="/admin" style="color:inherit;text-decoration:none">'
        "Админка фабрики</a></h1>"
        '<a href="/admin/audit">Журнал</a><span class="sp"></span>'
        f"{nav}</header><main>{body}</main></body></html>"
    )


def login(*, error: str = "") -> str:
    warn = f'<div class="flash bad">{_e(error)}</div>' if error else ""
    return page(
        "Вход",
        warn
        + '<div class="card"><h2>Вход по токену Control API</h2>'
        '<p class="hint">Панель не заводит собственных учётных записей. '
        "Права оператора — это области выданного токена.</p>"
        '<form method="post" action="/admin/login">'
        '<label for="tok">Токен</label>'
        '<input id="tok" name="token" type="password" autocomplete="off" required>'
        '<div class="row"><button type="submit">Войти</button></div></form></div>',
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


def dashboard(sites: list[dict], *, flash: dict | None, session_label: str,
              csrf: str, read_problem: str = "",
              compat_by_site: dict[str, dict] | None = None) -> str:
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


def site_detail(site_id: str, *, info: dict, config: dict, coverage: dict,
                scopes: list[str], flash: dict | None, session_label: str,
                csrf: str, compatibility: dict | None = None) -> str:
    hidden = f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
    tags = "".join(f'<span class="tag">{_e(s)}</span>' for s in scopes)

    overview = (
        f'<div class="card"><h2>{_e(site_id)}</h2>'
        + _dl([
            ("Тип", info.get("site_type")),
            ("Домены", ", ".join(info.get("domains") or [])),
            ("Локаль", info.get("locale")),
            ("Рендеринг", info.get("render_mode")),
            ("Модулей", len(info.get("modules") or [])),
        ])
        + f'<p class="hint">Права токена: {tags or "нет"}</p></div>'
    )

    состояние = ""
    if compatibility:
        kind = _STATE_KIND.get(compatibility.get("state", ""), "warn")
        состояние = (
            f'<div class="card {kind}"><h2><span class="dot"></span>Контракт CMS</h2>'
            + _dl([
                ("Состояние", _STATE_WORDS.get(compatibility.get("state", ""), "неизвестно")),
                ("Объявлено витриной", compatibility.get("declared") or "не объявлено"),
                ("Реализует движок", compatibility.get("engine")),
                ("Управление", "разрешено" if compatibility.get("manageable") else "запрещено"),
            ])
            + f'<p class="hint">{_e(compatibility.get("reason", ""))}</p></div>'
        )

    cov = (
        '<div class="card"><h2>Полнота каталога</h2>'
        + _dl(list(coverage.items())[:8])
        + "</div>"
    ) if coverage else ""

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
        current = _e(json.dumps(
            {k: config.get(k) for k in ("keep_releases", "cache_policy", "feature_flags")
             if k in config}, ensure_ascii=False, indent=2))
        actions.append(
            f'<div class="card"><h2>Настройки</h2>'
            f'<p class="hint">Изменяются только обратимые настройки ядра. Домены, '
            f'канонический хост и флаги индексации отклоняются намеренно.</p>'
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
        _flash(flash) + '<p><a href="/admin">← ко всем витринам</a></p>'
        + overview + состояние + cov + "".join(actions),
        session_label=session_label,
        csrf=csrf,
    )


def audit(entries: list[dict], *, total: int, session_label: str, csrf: str,
          flash: dict | None = None) -> str:
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
        "<table><thead><tr><th>Время</th><th>Витрина</th><th>Действие</th>"
        "<th>Цель</th><th>Род</th><th>Идентификатор связи</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    ) if rows else '<p class="hint">Записей нет.</p>'
    return page(
        "Журнал",
        _flash(flash)
        + f'<div class="card"><h2>Журнал операций</h2>'
        f'<p class="hint">Показаны последние {len(entries)} из {total}. '
        "Отказы записываются наравне с удачными операциями.</p>"
        f"{table}</div>",
        session_label=session_label,
        csrf=csrf,
    )
