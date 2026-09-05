"""Страницы учётной записи зрителя.

Отдельный модуль и отдельный префикс адресов: разметка операторской панели не
должна попадать на публичную страницу даже случайно. Панель помечена
`noindex` и рассчитана на своего человека; публичные страницы видит кто угодно.

Включается флагом профиля витрины и не включается, пока доставка писем не
готова к production: регистрация без подтверждения адреса и без восстановления
пароля — это учётная запись, которую нельзя ни подтвердить, ни вернуть.
"""
from __future__ import annotations

from html import escape as _e
from typing import Any

ACCOUNT_COOKIE = "sfaccount"
CSRF_FIELD = "_csrf"

STYLE = """
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  background:#f6f8fa;color:#1f2328}
header{padding:1rem 1.25rem;border-bottom:1px solid #d0d7de;background:#fff;
  display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
header h1{font-size:1.1rem;margin:0}
header a{color:inherit}
main{max-width:44rem;margin:0 auto;padding:1.25rem}
.card{background:#fff;border:1px solid #d0d7de;border-radius:10px;
  padding:1.1rem;margin-bottom:1rem}
.card h2{margin:.1rem 0 .8rem;font-size:1.15rem}
label{display:block;margin:.6rem 0 .2rem;font-weight:600;font-size:.92rem}
input,select{width:100%;max-width:100%;padding:.5rem .6rem;border-radius:6px;
  border:1px solid #d0d7de;font:inherit;background:#fff;color:inherit}
button{margin-top:.9rem;padding:.5rem 1rem;border-radius:6px;border:1px solid #1f883d;
  background:#1f883d;color:#fff;font:inherit;cursor:pointer}
button.ghost{background:transparent;color:inherit;border-color:#d0d7de}
.msg{padding:.7rem .9rem;border-radius:8px;margin-bottom:1rem;
  border:1px solid #d0d7de;background:#fff}
.msg.ok{border-color:#4ac26b;background:#dafbe1}
.msg.bad{border-color:#e5534b;background:#ffebe9}
.mut{color:#59636e;font-size:.9rem}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:.45rem .5rem;border-bottom:1px solid #eaeef2}
.scroll-x{overflow-x:auto}
/* Длинный адрес обязан переноситься. Без этого адрес вида
   viewer-chromium1788613456789@example.test в <b> раздвигал страницу на 390px
   и утягивал за собой таблицу сессий: поймано измерением конкретного
   переполняющего элемента, а не догадкой про таблицу. */
code,b,td,th,p{overflow-wrap:anywhere}
:focus-visible{outline:2px solid #0969da;outline-offset:2px}
@media (prefers-color-scheme:dark){
  body{background:#0d1117;color:#e6edf3}
  header,.card,input,select,.msg{background:#161b22;border-color:#30363d}
  .msg.ok{background:#12261e;border-color:#2ea043}
  .msg.bad{background:#2d1214;border-color:#f85149}
  .mut{color:#8b949e} th,td{border-bottom-color:#21262d}
}
"""


def page(title: str, body: str, *, вошёл: bool = False, csrf: str = "") -> str:
    nav = ('<a href="/account">Профиль</a>'
           '<form method="post" action="/account/logout" style="margin:0">'
           f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
           '<button class="ghost" type="submit">Выйти</button></form>'
           if вошёл else '<a href="/account/login">Вход</a>'
                         '<a href="/account/register">Регистрация</a>')
    return (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        f"<title>{_e(title)}</title><style>{STYLE}</style></head><body>"
        f'<header><h1>Учётная запись</h1>{nav}</header><main>{body}</main>'
        "</body></html>")


def _msg(сообщение: dict | None) -> str:
    if not сообщение:
        return ""
    вид = _e(str(сообщение.get("kind", "")))
    return f'<div class="msg {вид}">{_e(str(сообщение.get("text", "")))}</div>'


def register(*, csrf: str, сообщение: dict | None = None,
             consent_version: str = "") -> str:
    return page("Регистрация", _msg(сообщение)
                + '<div class="card"><h2>Регистрация</h2>'
                '<form method="post" action="/account/register">'
                f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
                '<label for="em">Адрес</label>'
                '<input id="em" name="email" type="email" autocomplete="email" required>'
                '<label for="nm">Как к вам обращаться</label>'
                '<input id="nm" name="displayName" autocomplete="nickname">'
                '<label for="pw">Пароль (не короче 12 символов)</label>'
                '<input id="pw" name="password" type="password" minlength="12" '
                'autocomplete="new-password" required>'
                '<label for="cs" style="display:flex;gap:.5rem;align-items:center">'
                '<input id="cs" name="consent" type="checkbox" value="1" required '
                'style="width:auto">'
                f'<span>Согласен с правилами ({_e(consent_version)})</span></label>'
                '<button type="submit">Зарегистрироваться</button></form>'
                '<p class="mut">На указанный адрес придёт ссылка подтверждения. '
                "Она одноразовая и действует сутки.</p></div>", csrf=csrf)


def login(*, csrf: str, сообщение: dict | None = None) -> str:
    return page("Вход", _msg(сообщение)
                + '<div class="card"><h2>Вход</h2>'
                '<form method="post" action="/account/login">'
                f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
                '<label for="em">Адрес</label>'
                '<input id="em" name="email" type="email" autocomplete="username" required>'
                '<label for="pw">Пароль</label>'
                '<input id="pw" name="password" type="password" '
                'autocomplete="current-password" required>'
                '<button type="submit">Войти</button></form>'
                '<p class="mut"><a href="/account/forgot">Забыли пароль?</a> · '
                '<a href="/account/resend">Не пришло подтверждение?</a></p></div>',
                csrf=csrf)


def simple_form(*, title: str, heading: str, action: str, csrf: str,
                поля: str, кнопка: str, сообщение: dict | None = None,
                подсказка: str = "") -> str:
    return page(title, _msg(сообщение)
                + f'<div class="card"><h2>{_e(heading)}</h2>'
                f'<form method="post" action="{_e(action)}">'
                f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
                f'{поля}<button type="submit">{_e(кнопка)}</button></form>'
                + (f'<p class="mut">{_e(подсказка)}</p>' if подсказка else "")
                + "</div>", csrf=csrf)


def profile(запись: dict, сессии: list, *, csrf: str,
            сообщение: dict | None = None) -> str:
    строки = "".join(
        f'<tr><td class="mut">{_e(s.get("createdAt", ""))}</td>'
        f'<td class="mut">{_e(s.get("userAgent", ""))}</td>'
        f'<td><form method="post" action="/account/sessions/revoke">'
        f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
        f'<input type="hidden" name="sessionId" value="{_e(s.get("sessionId", ""))}">'
        '<button class="ghost" type="submit">Завершить</button></form></td></tr>'
        for s in сессии)
    return page(
        "Профиль",
        _msg(сообщение)
        + '<div class="card"><h2>Профиль</h2>'
        f'<p>Адрес: <b>{_e(запись.get("email", ""))}</b></p>'
        f'<p class="mut">Согласие: {_e(запись.get("consentVersion", ""))} '
        f'от {_e(запись.get("consentAt", ""))}</p>'
        '<form method="post" action="/account/profile">'
        f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
        '<label for="nm">Как к вам обращаться</label>'
        f'<input id="nm" name="displayName" value="{_e(запись.get("displayName", ""))}">'
        '<button type="submit">Сохранить</button></form></div>'
        + '<div class="card"><h2>Смена пароля</h2>'
        '<form method="post" action="/account/password">'
        f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
        '<label for="cur">Текущий пароль</label>'
        '<input id="cur" name="current" type="password" autocomplete="current-password" required>'
        '<label for="new">Новый пароль</label>'
        '<input id="new" name="new" type="password" minlength="12" '
        'autocomplete="new-password" required>'
        '<button type="submit">Сменить</button></form>'
        '<p class="mut">Смена пароля завершает все сессии, включая текущую.</p></div>'
        + '<div class="card"><h2>Устройства и сессии</h2><div class="scroll-x">'
        "<table><thead><tr><th>Начата</th><th>Клиент</th><th></th></tr></thead>"
        f"<tbody>{строки or chr(60) + 'tr' + chr(62) + chr(60)}</tbody></table></div>"
        '<form method="post" action="/account/sessions/revoke-all">'
        f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
        '<button class="ghost" type="submit">Завершить все сессии</button></form></div>'
        + '<div class="card"><h2>Данные и удаление</h2>'
        '<form method="post" action="/account/export">'
        f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
        '<button class="ghost" type="submit">Показать мои данные</button></form>'
        '<form method="post" action="/account/delete">'
        f'<input type="hidden" name="{CSRF_FIELD}" value="{_e(csrf)}">'
        '<label for="cf">Введите УДАЛИТЬ для подтверждения</label>'
        '<input id="cf" name="confirm" required>'
        '<button class="ghost" type="submit">Удалить учётную запись</button></form>'
        '<p class="mut">Удаление стирает профиль и завершает все сессии. '
        "Адрес освобождается.</p></div>",
        вошёл=True, csrf=csrf)


def export_view(данные: dict[str, Any], *, csrf: str) -> str:
    import json

    return page("Мои данные",
                '<div class="card"><h2>Мои данные</h2>'
                '<p class="mut">Хэш пароля и одноразовые ссылки в выгрузку не '
                "входят.</p><pre class=\"scroll-x\"><code>"
                + _e(json.dumps(данные, ensure_ascii=False, indent=1))
                + '</code></pre><p><a href="/account">← Назад</a></p></div>',
                вошёл=True, csrf=csrf)


def disabled() -> str:
    """Регистрация выключена. Причина называется, а не прячется."""
    return page("Регистрация недоступна",
                '<div class="card"><h2>Регистрация недоступна</h2>'
                '<p>На этой витрине учётные записи пока не включены.</p>'
                '<p class="mut">Регистрация не включается, пока не готова '
                "доставка писем: без подтверждения адреса и восстановления "
                "пароля учётную запись нельзя ни подтвердить, ни вернуть.</p>"
                "</div>")
