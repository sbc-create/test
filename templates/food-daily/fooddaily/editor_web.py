"""Редактор preview: источник, черновик, проверка, diff, версии, журнал, откат.

Доступ — Basic Auth (scrypt-хеш в файле вне репозитория, путь
FOOD_DAILY_EDITOR_SECRET) только на петле. Пишущие действия — POST с
CSRF-токеном. Редактор работает с собственной БД food-daily; публичные
страницы её не читают — после изменений снимок пересобирается.
"""

from __future__ import annotations

import html
import json
import urllib.parse

from . import editorial
from .pipeline import open_store
from .quality import publish_blockers
from .views import Site

STYLE = "/static/css/editor.css"


def _page(app, title: str, body: str) -> str:
    return (
        f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="robots" content="noindex, nofollow">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)} — редактор</title>'
        f'<link rel="stylesheet" href="{app.asset("css/editor.css")}"></head><body><header><a href="/redaktor/">'
        f'Редактор food-daily</a> · <a href="/">сайт</a></header><main>{body}</main></body></html>'
    )


def handle(h, app, method: str, u: urllib.parse.SplitResult):
    user = app.editor_auth(h.headers.get("Authorization"))
    if not user:
        return h._send(
            401,
            "Требуется вход редактора",
            {
                "WWW-Authenticate": 'Basic realm="food-daily editor"',
                "Content-Type": "text/plain; charset=utf-8",
            },
        )
    st = open_store()
    parts = [p for p in u.path.split("/") if p][1:]
    if method == "POST":
        n = int(h.headers.get("Content-Length") or 0)
        form = {k: v[0] for k, v in urllib.parse.parse_qs(h.rfile.read(min(n, 65536)).decode()).items()}
        if form.get("csrf") != app.csrf(user) or not parts:
            return h._send(403, "CSRF-токен не совпал", {"Content-Type": "text/plain; charset=utf-8"})
        cid, action = parts[0], form.get("action")
        try:
            if action == "publish":
                res = editorial.publish_preview(st, cid, actor=f"editor:{user}")
                msg = "опубликовано в preview" if res["published"] else "заблокировано: " + "; ".join(res["blockers"])
            elif action == "unpublish":
                st.set_publish(cid, "hidden", actor=f"editor:{user}")
                msg = "снято с preview"
            elif action == "rollback":
                msg = f"откат: новая версия v{st.rollback(cid, int(form['to']), actor=f'editor:{user}')}"
            elif action == "review":
                editorial.review(
                    st,
                    cid,
                    form["status"],
                    reviewer=form["reviewer"].strip(),
                    version=int(form["version"]),
                    note=form.get("note", ""),
                )
                msg = "решение редактора записано"
            else:
                msg = "неизвестное действие"
            editorial.snapshot(st)
            app.site = Site()
            app.env.globals["site"] = app.site
        except Exception as e:  # отказ показывается редактору, а не прячется
            msg = f"отказ: {e}"
        return h._send(303, "", {"Location": f"/redaktor/{cid}/?msg={urllib.parse.quote(msg)}"})

    if not parts:
        rows = st.db.execute(
            "SELECT c.*, (SELECT count(*) FROM versions v WHERE v.content_id=c.content_id) nv "
            "FROM content c ORDER BY c.created_at"
        ).fetchall()
        trs = "".join(
            f"<tr><td><a href='/redaktor/{r['content_id']}/'>{html.escape(r['slug'])}</a></td><td>v{r['current_version']}"
            f" / {r['nv']}</td><td>{r['review_status']}</td><td>{r['cooking_status']}</td><td>{r['publish_status']}</td></tr>"
            for r in rows
        )
        jobs = dict(st.db.execute("SELECT status, count(*) FROM jobs GROUP BY 1").fetchall())
        body = (
            f"<h1>Материалы ({len(rows)})</h1><p>Задания: {html.escape(json.dumps(jobs, ensure_ascii=False))}</p>"
            '<div class="tw" tabindex="0" role="region" aria-label="Таблица материалов">'
            "<table><tr><th>slug</th><th>версия</th><th>проверка</th><th>кухня</th><th>публикация</th></tr>"
            f"{trs}</table></div>"
        )
        return h._send(200, _page(app, "Материалы", body))
    cid = parts[0]
    row = st.current(cid)
    if not row:
        return h._send(404, _page(app, "Нет материала", "<p>Материал не найден.</p>"))
    q = urllib.parse.parse_qs(u.query)
    ver = st.version(cid)
    payload = json.loads(ver["payload_json"])
    versions = st.versions(cid)
    a, b = (int(q.get("a", [0])[0] or 0), int(q.get("b", [0])[0] or 0))
    diff_html = ""
    if a and b:
        diff_html = (
            f'<h2>Diff v{a} → v{b}</h2><pre tabindex="0" aria-label="Diff v{a} → v{b}">'
            f"{html.escape(editorial.diff(st, cid, a, b)) or '(нет различий)'}</pre>"
        )
    csrf = app.csrf(user)
    vrows = "".join(
        f"<li>v{v['recipe_version']} · {v['created_at']} · {html.escape(v['created_by'])} · "
        f"{html.escape(v['reason'])} · {html.escape(json.loads(v['producer_json']).get('mode', ''))}"
        f"<form method=post><input type=hidden name=csrf value={csrf}><input type=hidden name=action value=rollback>"
        f"<input type=hidden name=to value={v['recipe_version']}><button>откатить к v{v['recipe_version']}</button>"
        f"</form></li>"
        for v in versions
    )
    audit = "".join(
        f"<li>{e['at']} · {html.escape(e['actor'])} · {html.escape(e['action'])} · "
        f"<code>{html.escape(e['detail_json'][:200])}</code></li>"
        for e in st.audit_for(cid)[-30:]
    )
    blockers = publish_blockers(payload)
    msg = q.get("msg", [""])[0]
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in payload["draft"].get("editor_notes") or [])
    body = (
        (f"<p class=msg>{html.escape(msg)}</p>" if msg else "")
        + f"""
<h1>{html.escape(payload['draft']['title'])}</h1>
<p>Статусы: проверка <b>{row['review_status']}</b> ({html.escape(row['reviewer'] or '—')}), кухня <b>{row['cooking_status']}</b>,
публикация <b>{row['publish_status']}</b>, версия v{row['current_version']}.</p>
<p>Источник: <a href="{html.escape(payload['source']['url'])}" rel="nofollow noopener">{html.escape(payload['source']['url'])}</a>
· получено {payload['source']['fetched_at']} · хеш {payload['source']['content_hash'][:12]} · парсер {payload['source']['parser_version']}</p>
<p>Задание: {html.escape(payload.get('job_id', ''))} · исполнитель: {html.escape(json.loads(ver['producer_json']).get('mode', ''))}</p>
<h2>Замечания для редактора</h2><ul>{notes or '<li>нет</li>'}</ul>
<h2>Ворота публикации</h2><ul>{''.join(f'<li>{html.escape(x)}</li>' for x in blockers) or '<li>препятствий нет</li>'}</ul>
<div class=actions>
<form method=post><input type=hidden name=csrf value={csrf}><input type=hidden name=action value=publish><button>В preview</button></form>
<form method=post><input type=hidden name=csrf value={csrf}><input type=hidden name=action value=unpublish><button>Снять</button></form>
<form method=post><input type=hidden name=csrf value={csrf}><input type=hidden name=action value=review>
<input type=hidden name=version value={row['current_version']}>
<label>Редактор <input name=reviewer placeholder="имя редактора" required></label>
<label>Решение <select name=status><option value=editor_approved>одобрить</option>
<option value=editor_rejected>отклонить</option></select></label>
<label>Комментарий <input name=note placeholder="комментарий"></label><button>Записать проверку</button></form>
</div>
<p><a href="/recept/{row['slug']}/">Открыть страницу в preview</a></p>
<h2>Версии</h2><ol>{vrows}</ol>
<form class=diff><input type=hidden name=x value=1>Сравнить:
<label>с версии <input name=a size=3 inputmode=numeric value={max(1, row['current_version'] - 1)}></label> →
<label>по версию <input name=b size=3 inputmode=numeric value={row['current_version']}></label>
<button>diff</button></form>{diff_html}
<h2>Черновик (v{row['current_version']})</h2><pre tabindex="0" aria-label="Черновик v{row['current_version']}">{html.escape(json.dumps(payload['draft'], ensure_ascii=False, indent=1))}</pre>
<h2>Журнал</h2><ul>{audit}</ul>"""
    )
    return h._send(200, _page(app, payload["draft"]["title"], body))
