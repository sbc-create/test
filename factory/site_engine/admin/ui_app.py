"""Разметка раздела «Приложение „Кинатека“».

Те же правила, что у остальной панели (`ui.py`): серверный HTML, всё внешнее —
через экранирование, кнопки записи скрыты без области `app:write`, но запрет
держит API. Предпросмотр строится из ответа API (`preview`) — того же вида,
который отдаст приложению служба чтения, а не из отдельной логики панели.
"""
from __future__ import annotations

import json
from typing import Any

from factory.site_engine.admin import CSRF_FIELD
from factory.site_engine.admin.ui import _e, _flash, page

BASE = "/admin/apps/kinateka"

STYLE = """<style>
.rowp{display:flex;gap:10px;overflow-x:auto;padding:6px 0 10px}
.rowp figure{margin:0;flex:0 0 92px}
.rowp img{width:92px;height:138px;object-fit:cover;border-radius:8px;border:1px solid var(--line);
background:var(--line)}
.rowp.land figure{flex-basis:164px}.rowp.land img{width:164px;height:92px}
.rowp figcaption{font-size:12px;line-height:1.3;margin-top:4px;color:var(--mut);
overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.hero{display:flex;gap:14px;align-items:flex-end;border-radius:12px;padding:14px;
background:linear-gradient(90deg,#000c,#0004),var(--line);color:#fff;margin:6px 0 14px}
.hero img{width:110px;height:165px;object-fit:cover;border-radius:8px}
.hidden{opacity:.45}
.sw{display:inline-block;width:18px;height:18px;border-radius:5px;vertical-align:middle;
border:1px solid var(--line);margin-right:6px}
td input,td select{min-width:70px}
td.n input{width:64px;min-width:0}
td.t{max-width:260px}
td.r{min-width:300px}td.r textarea{font-size:13.5px}
td.s{width:170px}td.s input{margin-bottom:4px;font-size:12.5px}
.thumb{width:46px;height:69px;object-fit:cover;border-radius:5px;background:var(--line)}
.problems li{color:var(--bad)}
.pill{display:inline-block;border-radius:20px;padding:1px 9px;font-size:12px;border:1px solid}
.pill.ok{color:var(--ok);border-color:var(--ok)}.pill.bad{color:var(--bad);border-color:var(--bad)}
input[type=color]{height:36px;padding:3px}
textarea.json{min-height:320px;font:12.5px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}
</style>"""

KIND_WORDS = {"hero": "баннер", "continue": "продолжить просмотр", "collection": "подборка",
              "recent": "недавно добавлено", "genre": "жанр"}
CHANNEL_WORDS = {"sandbox": "песочница (видит сборка sandbox)",
                 "production": "рабочий (видит рабочая сборка)"}


def _hidden(csrf: str, version: str = "") -> str:
    out = f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
    if version:
        out += f'<input type="hidden" name="draftVersion" value="{_e(version)}">'
    return out


def _select(name: str, value: Any, options: list[tuple[str, str]], disabled: str = "") -> str:
    opts = "".join(f'<option value="{_e(v)}"{" selected" if v == value else ""}>{_e(t)}</option>'
                   for v, t in options)
    return f'<select name="{_e(name)}"{disabled}>{opts}</select>'


def unavailable(response, label: str, csrf: str) -> str:
    body = response.body if isinstance(response.body, dict) else {}
    err = body.get("error", {})
    return page("Кинатека", f'<div class="flash bad">Раздел недоступен: {response.status} '
                            f'{_e(err.get("code", ""))} {_e(err.get("message", ""))}</div>',
                session_label=label, csrf=csrf)


def _nav(channel: str | None = None) -> str:
    links = [f'<a href="{BASE}">Кинатека</a>']
    if channel:
        links.append(f'<a href="{BASE}/{_e(channel)}">канал {_e(channel)}</a>')
    return '<p class="hint">' + " → ".join(links) + "</p>"


def overview(body: dict, *, flash, session_label: str, csrf: str, can_write: bool) -> str:
    cards = []
    for channel, st in (body.get("channels") or {}).items():
        current = st.get("current")
        state = (f'ревизия <b>{_e(current)}</b> <code>{_e(st.get("revisionId"))}</code><br>'
                 f'<span class="mut">{_e(st.get("publishedAt"))} · {_e(st.get("publishedBy"))}</span>'
                 if current else '<span class="mut">ничего не опубликовано — приложение строит свою главную</span>')
        cards.append(f'<div class="card"><h2>Канал {_e(channel)}</h2><p class="hint">'
                     f'{_e(CHANNEL_WORDS.get(channel, ""))}</p><p>{state}</p>'
                     f'<p><a href="{BASE}/{_e(channel)}">Открыть: главная, подборки, оформление →</a></p></div>')
    warn = ""
    if not body.get("writesEnabled"):
        warn = ('<div class="flash bad">Запись конфигурации приложения на сервере выключена '
                "(SITE_ENGINE_APP_CONFIG_WRITES). Просмотр работает, сохранение и публикация — нет.</div>")
    elif not can_write:
        warn = ('<div class="flash bad">У вашего токена нет области app:write: '
                "раздел доступен только для просмотра.</div>")
    return page("Кинатека", STYLE + _flash(flash) + warn
                + '<div class="card"><h2>Приложение «Кинатека»</h2><p class="hint">Главная, подборки и оформление '
                  'Android-приложения и Android TV. Изменения — в черновике канала; приложение видит только '
                  'опубликованную ревизию (на следующем запуске или возврате на главную). Откат — переводом '
                  'канала на прежнюю ревизию. Схема '
                + f'<code>{_e(body.get("schema"))}</code>, каталог витрины <code>{_e(body.get("site"))}</code>.</p></div>'
                + '<div class="grid">' + "".join(cards) + "</div>"
                + _history(body.get("history") or [], None, csrf, can_write=False),
                session_label=session_label, csrf=csrf)


def _history(rows: list[dict], channel: str | None, csrf: str, *, can_write: bool,
             current: int | None = None) -> str:
    if not rows:
        return '<div class="card"><h2>История</h2><p class="mut">Публикаций ещё не было.</p></div>'
    seen_published: set[int] = set()
    lines = []
    for h in rows:
        rev = h.get("revision")
        action = {"publish": "публикация", "rollback": "откат", "import": "перенос"}.get(
            h.get("action"), h.get("action"))
        button = ""
        if (can_write and channel and h.get("action") == "publish" and rev != current
                and rev not in seen_published):
            button = (f'<form method="post" action="{BASE}/{_e(channel)}/rollback" style="margin:0">'
                      f'{_hidden(csrf)}<input type="hidden" name="toRevision" value="{_e(rev)}">'
                      f'<input type="hidden" name="expectedRevision" value="{_e(current if current is not None else "")}">'
                      f'<button class="ghost" type="submit">Вернуть ревизию {_e(rev)}</button></form>')
        if h.get("action") == "publish":
            seen_published.add(rev)
        mark = " ← действует" if rev == current and h is rows[0] else ""
        lines.append(f"<tr><td>{_e(h.get('at'))}</td><td>{_e(h.get('channel'))}</td><td>{_e(action)}</td>"
                     f"<td><b>{_e(rev)}</b> <code>{_e(h.get('revisionId'))}</code>{_e(mark)}</td>"
                     f"<td>{_e(h.get('previous'))}</td><td><code>{_e(h.get('by'))}</code></td>"
                     f"<td>{_e(h.get('comment'))}</td><td>{button}</td></tr>")
    return ('<div class="card" id="history"><h2>История</h2><table><tr><th>Когда</th><th>Канал</th><th>Что</th>'
            '<th>Ревизия</th><th>Было</th><th>Кто (токен)</th><th>Комментарий</th><th></th></tr>'
            + "".join(lines) + "</table></div>")


def _problems(problems: list[dict], only: str | None = None) -> str:
    rows = [p for p in problems if only is None or only in p.get("where", "")]
    if not rows:
        return ""
    return ('<ul class="problems">' + "".join(
        f"<li><b>{_e(p.get('where'))}</b>: {_e(p.get('problem'))}</li>" for p in rows) + "</ul>")


def _poster_row(items: list[dict], land: bool) -> str:
    figs = "".join(
        f'<figure><img loading="lazy" alt="" src="{_e(it.get("posterUrl") or "")}">'
        f"<figcaption>{_e(it.get('title'))}</figcaption></figure>" for it in items[:10])
    return f'<div class="rowp{" land" if land else ""}">{figs or "<span class=mut>пусто</span>"}</div>'


def _preview(preview: dict | None) -> str:
    if not preview:
        return ""
    cols = {c.get("id"): c for c in preview.get("collections") or []}
    ap = preview.get("appearance") or {}
    out = []
    for b in (preview.get("home") or {}).get("blocks") or []:
        hidden = b.get("visible") is False
        cls = ' class="hidden"' if hidden else ""
        note = " (скрыт)" if hidden else ""
        kind = b.get("kind")
        if kind == "hero":
            c = cols.get(b.get("collectionId")) or {}
            first = (c.get("items") or [{}])[0]
            out.append(f'<div{cls}><div class="hero"><img alt="" src="{_e(first.get("posterUrl") or "")}">'
                       f'<div><div style="color:{_e(ap.get("accent", "#E3B26B"))}">{_e(c.get("title"))}</div>'
                       f'<div style="font-size:20px;font-weight:650">{_e(first.get("title"))}</div>'
                       f'<div class="hint" style="color:#ddd">баннер{_e(note)}</div></div></div></div>')
        elif kind == "collection":
            c = cols.get(b.get("collectionId")) or {}
            land = (b.get("cardStyle") or ap.get("rowCardStyle")) == "landscape"
            miss = f' · <span class="mut">не показано: {len(c.get("missing") or [])}</span>' if c.get("missing") else ""
            out.append(f"<div{cls}><b>{_e(b.get('title'))}</b>{_e(note)} "
                       f'<span class="mut">— {_e(c.get("subtitle") or "")}</span>{miss}'
                       + _poster_row(c.get("items") or [], land) + "</div>")
        else:
            words = {"continue": "Продолжить просмотр — из истории на устройстве",
                     "recent": f"{b.get('title')} — новое в каталоге",
                     "genre": f"{b.get('title')} — жанр «{b.get('genre')}»"}.get(kind, kind)
            out.append(f'<div{cls}><p><b>{_e(words)}</b>{_e(note)} '
                       '<span class="mut">(строится приложением)</span></p></div>')
    accent = ap.get("accent", "")
    return ('<div class="card" id="preview"><h2>Предпросмотр черновика</h2><p class="hint">'
            f'<span class="sw" style="background:{_e(accent)}"></span>акцент {_e(accent)} · баннер '
            f'{_e(ap.get("heroStyle"))} · карточки {_e(ap.get("rowCardStyle"))} · фокус ×{_e(ap.get("focusScale"))}. '
            "Названия и постеры — из текущего каталога, как их получит приложение.</p>"
            + "".join(out) + "</div>")


def channel(body: dict, *, flash, session_label: str, csrf: str, can_write: bool) -> str:
    ch = body.get("channel", "")
    draft = body.get("draft") or {}
    version = body.get("draftVersion", "")
    problems = body.get("problems") or []
    current = body.get("current")
    dis = "" if can_write else " disabled"
    base = f"{BASE}/{_e(ch)}"

    cur = body.get("currentRevision") or {}
    status = (f'Действует ревизия <b>{_e(current)}</b> <code>{_e(cur.get("revisionId"))}</code>, '
              f'опубликована {_e(cur.get("publishedAt"))}.' if current
              else "В канале ничего не опубликовано: приложение строит свою главную.")
    ready = ('<span class="pill ok">черновик готов к публикации</span>' if not problems
             else f'<span class="pill bad">исправить до публикации: {len(problems)}</span>')
    publish = (f'<form method="post" action="{base}/publish">{_hidden(csrf, version)}'
               f'<input type="hidden" name="expectedRevision" value="{_e(current if current is not None else "")}">'
               '<div class="row"><div><label>Комментарий к публикации</label>'
               '<input name="comment" maxlength="300" placeholder="что изменилось"></div>'
               f'<button type="submit"{dis if not problems else " disabled"}>Опубликовать в {_e(ch)}</button></div></form>')
    differs = ""
    if current and body.get("draftDiffersFromCurrent"):
        differs = (f'<p class="hint">Черновик отличается от действующей ревизии {_e(current)} — '
                   "приложение получает действующую, а не черновик.</p>")
    imp = ""
    if can_write:
        label = ("Перенести ревизию sandbox в черновик production (номер)" if ch == "production"
                 else "Взять ревизию в черновик (номер) — например, после отката")
        imp = (f'<form method="post" action="{base}/import">{_hidden(csrf, version)}'
               f'<div class="row"><div><label>{label}</label>'
               f'<input name="fromRevision" inputmode="numeric" value="{_e(current or "")}" required></div>'
               '<button class="ghost" type="submit">Скопировать в черновик</button></div></form>')
    head = (f'<div class="card"><h2>Кинатека · канал {_e(ch)}</h2><p class="hint">{_e(CHANNEL_WORDS.get(ch, ""))}. '
            f'Каталог <code>{_e((body.get("catalogRevision") or "")[:12])}</code>'
            + (f' — <span style="color:var(--bad)">{_e(body.get("catalogError"))}</span>' if body.get("catalogError") else "")
            + f'</p><p>{status}</p>{differs}<p>{ready}</p>{_problems(problems)}{publish}{imp}</div>')

    # блоки главной
    cols = [c.get("id") for c in draft.get("collections") or []]
    rows = []
    for i, b in enumerate((draft.get("home") or {}).get("blocks") or []):
        bid = b.get("id", "")
        kind = b.get("kind")
        title = ("—" if kind == "continue" else
                 f'<input name="title_{_e(bid)}" value="{_e(b.get("title") or "")}"{dis}>')
        extra = ""
        if kind == "collection":
            extra = (_select(f"cardStyle_{bid}", b.get("cardStyle") or "poster",
                             [("poster", "постеры"), ("landscape", "кадры")], dis)
                     + f'<input name="cover_{_e(bid)}" placeholder="обложка https://… (по желанию)" '
                       f'value="{_e(b.get("cover") or "")}"{dis}>')
        ref = (f'<a href="{base}/collections/{_e(b.get("collectionId"))}">{_e(b.get("collectionId"))}</a>'
               if kind in ("hero", "collection") else _e(b.get("genre") or ""))
        checked = " checked" if b.get("visible", True) is not False else ""
        rows.append(f'<tr><td class="n"><input name="order_{_e(bid)}" value="{i + 1}" inputmode="numeric"{dis}></td>'
                    f"<td><code>{_e(bid)}</code><br><span class='mut'>{_e(KIND_WORDS.get(kind, kind))}</span></td>"
                    f"<td>{ref}</td><td>{title}{extra}</td>"
                    f'<td><input type="checkbox" name="visible_{_e(bid)}" value="1"{checked}{dis}></td>'
                    f'<td><input type="checkbox" name="delete_{_e(bid)}" value="1"{dis}></td></tr>')
    blocks = (f'<div class="card" id="blocks"><h2>Блоки главной</h2><p class="hint">Порядок — числами в первой '
              'колонке; «виден» снят — блок не показывается; «убрать» — удалить из главной.</p>'
              f'<form method="post" action="{base}/blocks">{_hidden(csrf, version)}<table>'
              '<tr><th>№</th><th>Блок</th><th>Подборка / жанр</th><th>Заголовок и вид</th><th>Виден</th><th>Убрать</th></tr>'
              + "".join(rows) + f'</table><div class="row"><button type="submit"{dis}>Сохранить блоки</button></div></form>'
              f'<form method="post" action="{base}/blocks/add">{_hidden(csrf, version)}<div class="row">'
              '<div><label>Новый блок: id</label><input name="id" placeholder="naprimer-sport" required></div>'
              '<div><label>Вид</label>' + _select("kind", "collection", list(KIND_WORDS.items())) + "</div>"
              '<div><label>Подборка</label>' + _select("collectionId", cols[0] if cols else "",
                                                       [(c, c) for c in cols] or [("", "—")]) + "</div>"
              '<div><label>Жанр (для вида «жанр»)</label><input name="genre"></div>'
              '<div><label>Заголовок</label><input name="title"></div>'
              f'<button class="ghost" type="submit"{dis}>Добавить</button></div></form>{_problems(problems, "блок")}</div>')

    # подборки
    crow = []
    preview = {c.get("id"): c for c in (body.get("preview") or {}).get("collections") or []}
    for c in draft.get("collections") or []:
        pv = preview.get(c.get("id")) or {}
        crow.append(f'<tr><td><a href="{base}/collections/{_e(c.get("id"))}"><b>{_e(c.get("title"))}</b></a>'
                    f'<br><code>{_e(c.get("id"))}</code></td><td>{len(c.get("items") or [])}</td>'
                    f'<td>{len(pv.get("missing") or [])}</td><td>{_e(c.get("source"))}</td>'
                    f'<td>{_e(c.get("checkedAt"))}</td><td>{_e(c.get("validUntil") or "")}</td></tr>')
    collections = (f'<div class="card" id="collections"><h2>Подборки</h2><table><tr><th>Подборка</th><th>Позиций</th>'
                   '<th>Не покажется</th><th>Источник</th><th>Проверено</th><th>Действует до</th></tr>'
                   + "".join(crow) + "</table>"
                   f'<form method="post" action="{base}/collections/add">{_hidden(csrf, version)}<div class="row">'
                   '<div><label>Новая подборка: id</label><input name="id" placeholder="anime-2025" required></div>'
                   '<div><label>Название</label><input name="title" maxlength="60" required></div>'
                   f'<button class="ghost" type="submit"{dis}>Создать</button></div></form></div>')

    ap = draft.get("appearance") or {}
    appearance = (f'<div class="card" id="appearance"><h2>Оформление</h2><p class="hint">Только параметры, которые '
                  'понимает приложение. Недопустимое значение не опубликуется.</p>'
                  f'<form method="post" action="{base}/appearance">{_hidden(csrf, version)}<div class="row">'
                  f'<div><label>Акцент</label><input type="color" name="accent" value="{_e(ap.get("accent", "#E3B26B"))}"{dis}></div>'
                  '<div><label>Баннер</label>' + _select("heroStyle", ap.get("heroStyle", "backdrop"),
                                                       [("backdrop", "кадр во всю ширину"), ("poster", "постер")], dis) + "</div>"
                  '<div><label>Карточки рядов</label>' + _select("rowCardStyle", ap.get("rowCardStyle", "poster"),
                                                               [("poster", "постеры"), ("landscape", "кадры")], dis) + "</div>"
                  f'<div><label>Увеличение в фокусе (TV), 1.00–1.12</label><input name="focusScale" '
                  f'value="{_e(ap.get("focusScale", 1.08))}" inputmode="decimal"{dis}></div>'
                  f'<button type="submit"{dis}>Сохранить</button></div></form>{_problems(problems, "appearance")}</div>')

    artwork = _artwork(body.get("artwork") or {}, base, csrf, version, dis)

    raw = json.dumps(draft, ensure_ascii=False, indent=1)
    advanced = (f'<div class="card" id="json"><details><summary>Документ черновика целиком (JSON)</summary>'
                f'<form method="post" action="{base}/json">{_hidden(csrf, version)}'
                f'<textarea class="json" name="document"{dis}>{_e(raw)}</textarea>'
                f'<div class="row"><button class="ghost" type="submit"{dis}>Сохранить документ</button></div>'
                "</form></details></div>")
    history = _history(body.get("revisions") or [], ch, csrf, can_write=can_write, current=current)
    return page(f"Кинатека · {ch}", STYLE + _nav() + _flash(flash) + head + _preview(body.get("preview"))
                + blocks + collections + artwork + appearance + history + advanced,
                session_label=session_label, csrf=csrf)


VERDICT_WORDS = {"ok": "подходит для общей витрины", "explicit": "откровенная — не показывать на витрине"}


def _mark_form(base: str, csrf: str, version: str, dis: str, cid: str, url: str, verdict: str,
               label: str, cls: str = "ghost") -> str:
    return (f'<form method="post" action="{base}/artwork/mark" style="display:inline;margin:0">'
            f'{_hidden(csrf, version)}<input type="hidden" name="contentId" value="{_e(cid)}">'
            f'<input type="hidden" name="imageUrl" value="{_e(url)}">'
            f'<input type="hidden" name="verdict" value="{_e(verdict)}">'
            f'<button class="{cls}" type="submit"{dis}>{_e(label)}</button></form>')


def _artwork(art: dict, base: str, csrf: str, version: str, dis: str) -> str:
    """Отметки пригодности изображений для общей витрины и очередь на просмотр."""
    risk = ", ".join(art.get("coverRiskGenres") or [])
    queue = "".join(
        f'<tr><td><a href="{_e(q.get("posterUrl"))}" target="_blank" rel="noopener">'
        f'<img class="thumb" alt="" src="{_e(q.get("posterUrl"))}"></a></td>'
        f'<td><b>{_e(q.get("title"))}</b><br><code>{_e(q.get("contentId"))}</code><br>'
        f'<span class="mut">подборка {_e(q.get("collection"))} · жанр {_e(", ".join(q.get("risk") or []))}</span></td>'
        f'<td>{_mark_form(base, csrf, version, dis, q.get("contentId"), q.get("posterUrl"), "ok", "Подходит", "")} '
        f'{_mark_form(base, csrf, version, dis, q.get("contentId"), q.get("posterUrl"), "explicit", "Откровенная")}</td></tr>'
        for q in art.get("queue") or [])
    queue_html = (('<h3>Ждут просмотра</h3><p class="hint">Позиции подборок с жанром из списка риска, чью обложку '
                   'ещё никто не смотрел. До отметки «подходит» они не опубликуются.</p><table>' + queue + "</table>")
                  if queue else "")
    rows = []
    for r in art.get("reviews") or []:
        stale = ("" if r.get("applies") else
                 ' <span class="pill bad">постер в каталоге сменился — отметка не действует</span>')
        rows.append(
            f'<tr><td><img class="thumb" alt="" src="{_e(r.get("imageUrl"))}"></td>'
            f'<td><b>{_e(r.get("title") or "")}</b><br><code>{_e(r.get("contentId"))}</code>{stale}</td>'
            f'<td><span class="pill {"ok" if r.get("verdict") == "ok" else "bad"}">'
            f'{_e(VERDICT_WORDS.get(r.get("verdict"), r.get("verdict")))}</span>'
            f'<br><span class="mut">{_e(r.get("reviewedAt"))} {_e(r.get("note") or "")}</span></td>'
            f'<td><form method="post" action="{base}/artwork/remove" style="margin:0">{_hidden(csrf, version)}'
            f'<input type="hidden" name="contentId" value="{_e(r.get("contentId"))}">'
            f'<input type="hidden" name="imageUrl" value="{_e(r.get("imageUrl"))}">'
            f'<button class="ghost" type="submit"{dis}>Снять отметку</button></form></td></tr>')
    reviews_html = ("<h3>Отметки</h3><table>" + "".join(rows) + "</table>") if rows else (
        '<p class="mut">Отметок нет.</p>')
    add = (f'<form method="post" action="{base}/artwork/mark">{_hidden(csrf, version)}<div class="row">'
           '<div><label>Отметить обложку тайтла: contentId</label><input name="contentId" required></div>'
           '<div><label>Вердикт</label>' + _select("verdict", "explicit", [("explicit", "откровенная"), ("ok", "подходит")], dis) + "</div>"
           '<div><label>Примечание (по желанию)</label><input name="note" maxlength="140"></div>'
           f'<button class="ghost" type="submit"{dis}>Отметить нынешний постер</button></div></form>')
    return ('<div class="card" id="artwork"><h2>Обложки</h2><p class="hint">Общая витрина — баннер, подборки и ряды '
            'главной — не показывает откровенных изображений. Решает отметка по конкретной картинке, а не '
            'возрастная маркировка или жанр произведения: «откровенная» убирает тайтл с витрины при любом жанре, '
            f'а тайтлам с жанром {_e(risk)} нужна отметка «подходит». Поиск и карточка тайтла показывают его '
            'как обычно. Отметка относится к картинке: сменится постер — её нужно поставить заново.</p>'
            + queue_html + reviews_html + add + "</div>")


def collection(body: dict, cid: str, *, flash, session_label: str, csrf: str, can_write: bool,
               query: str = "", found: list[dict] | None = None) -> str:
    ch = body.get("channel", "")
    version = body.get("draftVersion", "")
    draft = body.get("draft") or {}
    c = next((x for x in draft.get("collections") or [] if x.get("id") == cid), None)
    base = f"{BASE}/{_e(ch)}"
    if c is None:
        return page("Подборка", _nav(ch) + f'<div class="flash bad">Подборки {_e(cid)} нет в черновике.</div>',
                    session_label=session_label, csrf=csrf)
    dis = "" if can_write else " disabled"
    pv = next((x for x in (body.get("preview") or {}).get("collections") or [] if x.get("id") == cid), {})
    by_id = {it.get("contentId"): it for it in pv.get("items") or []}
    missing = set(pv.get("missing") or [])
    problems = [p for p in body.get("problems") or [] if f"подборка {cid}" in p.get("where", "")]

    def field(name: str, label: str, wide: bool = False, hint: str = "") -> str:
        value = _e(c.get(name) or "")
        tag = (f'<textarea name="{name}" rows="3"{dis}>{value}</textarea>' if wide
               else f'<input name="{name}" value="{value}"{dis}>')
        return f'<div><label>{_e(label)}{(" — " + _e(hint)) if hint else ""}</label>{tag}</div>'

    meta = ("".join([field("title", "Название"), field("subtitle", "Подзаголовок")])
            + field("description", "Описание: что объединяет и чем это подтверждено", wide=True)
            + '<div class="row">' + field("source", "Источник подборки")
            + field("checkedAt", "Проверено", hint="2026-10-28T10:00:00+03:00")
            + field("validUntil", "Действует до (по желанию)") + "</div>")
    rows = []
    for n, it in enumerate(c.get("items") or [], 1):
        key = _e(it.get("contentId"))
        live = by_id.get(it.get("contentId")) or {}
        flag = ('<span class="pill bad">не покажется: нет в каталоге или обложка не для витрины '
                f'(<a href="{base}#artwork">Обложки</a>)</span>'
                if it.get("contentId") in missing else "")
        rows.append(f'<tr><td class="n"><input name="order_{key}" value="{n}" inputmode="numeric"{dis}></td>'
                    f'<td><img class="thumb" alt="" src="{_e(live.get("posterUrl") or "")}"></td>'
                    f'<td class="t"><b>{_e(live.get("title") or it.get("title") or "")}</b> {_e(live.get("year") or "")}'
                    f'<br><code>{key}</code> {flag}</td>'
                    f'<td class="r"><textarea name="reason_{key}" rows="3" maxlength="140"{dis}>'
                    f'{_e(it.get("reason") or "")}</textarea></td>'
                    f'<td class="s"><input name="source_{key}" value="{_e(it.get("source") or "")}"{dis}>'
                    f'<input name="checkedAt_{key}" value="{_e(it.get("checkedAt") or "")}" title="проверено"{dis}></td>'
                    f'<td><input type="checkbox" name="remove_{key}" value="1"{dis}></td></tr>')
    form = (f'<form method="post" action="{base}/collections/{_e(cid)}">{_hidden(csrf, version)}{meta}'
            '<h3>Состав</h3><p class="hint">Порядок — числами. Причина — коротко и только то, что подтверждает '
            "источник: дата импорта — не премьера, оценка — не популярность.</p>"
            '<table><tr><th>№</th><th></th><th>Тайтл</th><th>Причина</th><th>Источник · проверено</th>'
            "<th>Убрать</th></tr>" + "".join(rows) + "</table>"
            '<label>Добавить позиции — по строке «contentId | причина | источник»</label>'
            f'<textarea name="add" rows="3"{dis}></textarea>'
            f'<div class="row"><button type="submit"{dis}>Сохранить подборку</button></div></form>'
            f'<form method="post" action="{base}/collections/{_e(cid)}/delete">{_hidden(csrf, version)}'
            f'<div class="row"><button class="ghost" type="submit"{dis}>Удалить подборку из черновика</button></div></form>')
    results = ""
    if found is not None:
        lines = "".join(
            f'<tr><td><img class="thumb" alt="" src="{_e(t.get("posterUrl") or "")}"></td>'
            f'<td><b>{_e(t.get("title"))}</b> {_e(t.get("year") or "")}<br><code>{_e(t.get("contentId"))}</code>'
            + (f' <span class="pill bad">обложку нужно посмотреть: жанр {_e(", ".join(t.get("coverRisk")))}</span>'
               if t.get("coverRisk") else "")
            + f'</td><td class="mut">{_e(", ".join(t.get("genres") or []))}</td></tr>'
            for t in found)
        results = ("<table>" + lines + "</table>") if lines else '<p class="mut">Ничего не найдено.</p>'
    search = (f'<div class="card"><h2>Найти тайтл в каталоге</h2><form method="get" action="{base}/collections/{_e(cid)}">'
              f'<div class="row"><div><input name="q" value="{_e(query)}" placeholder="название или contentId"></div>'
              '<button class="ghost" type="submit">Найти</button></div></form>'
              '<p class="hint">Скопируйте contentId в поле «Добавить позиции».</p>' + results + "</div>")
    return page(f"Подборка {cid}", STYLE + _nav(ch) + _flash(flash)
                + f'<div class="card"><h2>Подборка {_e(c.get("title"))} <code>{_e(cid)}</code></h2>'
                + _problems(problems) + form + "</div>" + search,
                session_label=session_label, csrf=csrf)
