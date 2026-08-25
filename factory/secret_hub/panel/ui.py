"""Русскоязычный интерфейс панели: разметка, стили и клиентский скрипт.

Интерфейс рассчитан на владельца, а не на инженера. Поэтому:

* три карточки — по одной на направление, и ничего кроме;
* цвет статуса читается раньше текста: зелёный — работает, жёлтый — требует
  действия, красный — ошибка;
* слова вместо кодов: «проверено и применено», а не ``verified/applied``;
* технических значений не показывается вообще — ни токена, ни его части.
  Отпечаток подписан «контрольная сумма» и объяснён одной строкой;
* замена уже работающего значения требует подтверждения: перепутанный токен
  на работающем портфеле — это неработающие сайты.

CSP держится строгой: ``script-src 'self'`` без ``unsafe-inline``. Поэтому
скрипт отдаётся отдельным файлом, а не тегом на странице. Стили инлайновые —
для них разрешён ``'unsafe-inline'``, и это не то же самое: стиль не может
отправить токен наружу.

Ни одна строка здесь не подставляет в HTML значение секрета: подставлять
нечего — панель их не получает.
"""
from __future__ import annotations

import html

#: Уникальная метка страницы. По ней live-gate убеждается, что отвечает панель,
#: а не кэш, заглушка или соседний сайт.
MARKER = "secret-hub-panel"

STYLE = """
:root{color-scheme:light}
*{box-sizing:border-box}
body{font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
     margin:0;padding:2rem 1rem 4rem;background:#f6f7f9;color:#1a1d21}
.wrap{max-width:52rem;margin:0 auto}
h1{font-size:1.6rem;margin:0 0 .25rem}
.sub{color:#5b6470;margin:0 0 2rem}
.card{background:#fff;border:1px solid #e2e6ea;border-radius:12px;padding:1.25rem 1.5rem;
      margin-bottom:1.25rem;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.card h2{font-size:1.2rem;margin:0 0 .15rem;display:flex;align-items:center;gap:.6rem}
.card .hint{color:#5b6470;font-size:.9rem;margin:0 0 1rem}
.dot{width:.7rem;height:.7rem;border-radius:50%;display:inline-block;flex:none}
.ok .dot{background:#1f9d55}.warn .dot{background:#d9a406}.bad .dot{background:#c62828}
.state{font-size:.95rem;margin:0 0 1rem}
.state b{font-weight:600}
.meta{display:grid;grid-template-columns:auto 1fr;gap:.3rem 1rem;font-size:.9rem;
      color:#41474e;margin:0 0 1rem}
.meta dt{color:#6b737c}.meta dd{margin:0;font-variant-numeric:tabular-nums}
label{display:block;font-weight:600;margin:.9rem 0 .3rem;font-size:.95rem}
input{width:100%;padding:.6rem .7rem;font:inherit;border:1px solid #c6ccd2;border-radius:8px;
      background:#fff}
input:focus{outline:2px solid #2f6fd0;outline-offset:1px;border-color:#2f6fd0}
.row{display:flex;gap:.6rem;flex-wrap:wrap;margin-top:1.1rem}
button{padding:.6rem 1.1rem;font:inherit;font-weight:600;border-radius:8px;border:1px solid transparent;
       cursor:pointer;background:#2f6fd0;color:#fff}
button.ghost{background:#fff;color:#2f6fd0;border-color:#c6d4ea}
button:disabled{opacity:.55;cursor:progress}
.msg{margin-top:1rem;padding:.7rem .9rem;border-radius:8px;font-size:.94rem;display:none}
.msg.show{display:block}
.msg.good{background:#e8f5ec;color:#14532d}
.msg.bad{background:#fdecec;color:#7f1d1d}
.msg.busy{background:#fff8e1;color:#6b4e00}
.consumers{font-size:.88rem;color:#5b6470;margin:.8rem 0 0;padding-left:1.1rem}
.consumers li{margin:.15rem 0}
.gate{max-width:30rem;margin:4rem auto;text-align:center}
.gate .card{text-align:left}
.codes{background:#111;color:#e8e8e8;border-radius:8px;padding:1rem;font-family:ui-monospace,
       SFMono-Regular,Menlo,monospace;font-size:1rem;line-height:2;letter-spacing:.04em}
.warnbox{background:#fff8e1;border:1px solid #f0d98c;border-radius:8px;padding:.9rem 1rem;
         font-size:.93rem;margin:1rem 0}
footer{color:#8a929b;font-size:.85rem;text-align:center;margin-top:2.5rem}
"""

SCRIPT = r"""
'use strict';
// Клиент панели. Токены здесь только проходят из поля в POST-тело и никогда
// не сохраняются: ни в localStorage, ни в переменной, переживающей отправку.
// После успешного сохранения поля очищаются.

function b64urlToBytes(s) {
  const pad = '='.repeat((4 - (s.length % 4)) % 4);
  const bin = atob((s + pad).replace(/-/g, '+').replace(/_/g, '/'));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
function bytesToB64url(buf) {
  const bytes = new Uint8Array(buf);
  let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function csrf() {
  const el = document.querySelector('meta[name="csrf"]');
  return el ? el.content : '';
}
async function post(path, body) {
  const res = await fetch(BASE + path, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()},
    body: JSON.stringify(body || {})
  });
  let data = {};
  try { data = await res.json(); } catch (e) { data = {}; }
  if (!res.ok) throw new Error(data.error || ('Ошибка ' + res.status));
  return data;
}
function say(el, kind, text) {
  el.className = 'msg show ' + kind;
  el.textContent = text;
}

// --- вход по passkey ------------------------------------------------------
async function login(btn, out) {
  btn.disabled = true;
  try {
    say(out, 'busy', 'Подтвердите вход на устройстве…');
    const begin = await post('/api/login/begin', {});
    const pk = begin.publicKey;
    pk.challenge = b64urlToBytes(pk.challenge);
    pk.allowCredentials = (pk.allowCredentials || []).map(function (c) {
      return {type: c.type, id: b64urlToBytes(c.id)};
    });
    const cred = await navigator.credentials.get({publicKey: pk});
    await post('/api/login/finish', {
      challenge_id: begin.challenge_id,
      credential: {
        id: cred.id,
        rawId: bytesToB64url(cred.rawId),
        type: cred.type,
        response: {
          clientDataJSON: bytesToB64url(cred.response.clientDataJSON),
          authenticatorData: bytesToB64url(cred.response.authenticatorData),
          signature: bytesToB64url(cred.response.signature),
          userHandle: cred.response.userHandle ? bytesToB64url(cred.response.userHandle) : null
        }
      }
    });
    location.reload();
  } catch (e) {
    say(out, 'bad', e.message || 'Вход не выполнен.');
    btn.disabled = false;
  }
}

// --- регистрация passkey --------------------------------------------------
async function register(btn, out, payload) {
  btn.disabled = true;
  try {
    say(out, 'busy', 'Создайте ключ на устройстве…');
    const begin = await post('/api/register/begin', payload);
    const pk = begin.publicKey;
    pk.challenge = b64urlToBytes(pk.challenge);
    pk.user.id = b64urlToBytes(pk.user.id);
    pk.excludeCredentials = (pk.excludeCredentials || []).map(function (c) {
      return {type: c.type, id: b64urlToBytes(c.id)};
    });
    const cred = await navigator.credentials.create({publicKey: pk});
    const done = await post('/api/register/finish', {
      challenge_id: begin.challenge_id,
      credential: {
        id: cred.id,
        rawId: bytesToB64url(cred.rawId),
        type: cred.type,
        response: {
          clientDataJSON: bytesToB64url(cred.response.clientDataJSON),
          attestationObject: bytesToB64url(cred.response.attestationObject)
        }
      }
    });
    if (done.recovery_codes) {
      showRecovery(done.recovery_codes);
    } else {
      location.reload();
    }
  } catch (e) {
    say(out, 'bad', e.message || 'Ключ не создан.');
    btn.disabled = false;
  }
}

function showRecovery(codes) {
  const box = document.getElementById('recovery-box');
  const list = document.getElementById('recovery-codes');
  list.textContent = codes.join('\n');
  box.style.display = 'block';
  document.getElementById('gate-forms').style.display = 'none';
}

// --- сохранение credentials ----------------------------------------------
function newRequestId() {
  const a = new Uint8Array(16);
  crypto.getRandomValues(a);
  return bytesToB64url(a);
}

async function saveCard(card) {
  const portfolio = card.dataset.portfolio;
  const token = card.querySelector('.f-token');
  const publisher = card.querySelector('.f-publisher');
  const out = card.querySelector('.msg');
  const buttons = card.querySelectorAll('button');
  const configured = card.dataset.configured === 'yes';

  if (!token.value.trim() || !publisher.value.trim()) {
    say(out, 'bad', 'Заполните оба поля.');
    return;
  }
  if (configured && !confirm(
      'У направления «' + portfolio + '» уже есть работающие credentials.\n\n' +
      'Заменить их на новые? Сайты направления будут перезапущены.')) {
    return;
  }

  buttons.forEach(function (b) { b.disabled = true; });
  // Идентификатор запроса переживает повтор: двойной клик или обновление
  // страницы не создадут вторую версию секрета.
  if (!card.dataset.requestId) card.dataset.requestId = newRequestId();
  try {
    say(out, 'busy', 'Проверяем токен у провайдера…');
    const res = await post('/api/portfolio/save', {
      portfolio: portfolio,
      api_token: token.value,
      publisher_id: publisher.value,
      request_id: card.dataset.requestId,
      apply: true
    });
    // Поля очищаются сразу и в любом исходе, где значение уже ушло на сервер.
    token.value = '';
    publisher.value = '';
    delete card.dataset.requestId;
    if (res.ok) {
      say(out, 'good', res.message || 'Проверено и применено.');
      setTimeout(function () { location.reload(); }, 1200);
    } else {
      say(out, 'bad', res.message || 'Не сохранено.');
      buttons.forEach(function (b) { b.disabled = false; });
    }
  } catch (e) {
    token.value = '';
    publisher.value = '';
    delete card.dataset.requestId;
    say(out, 'bad', e.message || 'Не сохранено.');
    buttons.forEach(function (b) { b.disabled = false; });
  }
}

async function applyCard(card) {
  const portfolio = card.dataset.portfolio;
  const out = card.querySelector('.msg');
  const buttons = card.querySelectorAll('button');
  buttons.forEach(function (b) { b.disabled = true; });
  try {
    say(out, 'busy', 'Применяем к сайтам направления…');
    const res = await post('/api/portfolio/apply', {portfolio: portfolio});
    say(out, res.ok ? 'good' : 'bad', res.message || (res.ok ? 'Применено.' : 'Не применено.'));
    if (res.ok) setTimeout(function () { location.reload(); }, 1200);
    else buttons.forEach(function (b) { b.disabled = false; });
  } catch (e) {
    say(out, 'bad', e.message || 'Не применено.');
    buttons.forEach(function (b) { b.disabled = false; });
  }
}

function replaceCard(card) {
  card.querySelector('.form-area').style.display = 'block';
  card.querySelector('.f-token').focus();
}

document.addEventListener('DOMContentLoaded', function () {
  const savedBtn = document.getElementById('btn-codes-saved');
  if (savedBtn) savedBtn.addEventListener('click', function () { location.reload(); });
  const loginBtn = document.getElementById('btn-login');
  if (loginBtn) {
    loginBtn.addEventListener('click', function () {
      login(loginBtn, document.getElementById('gate-msg'));
    });
  }
  const enrollBtn = document.getElementById('btn-enroll');
  if (enrollBtn) {
    enrollBtn.addEventListener('click', function () {
      const code = document.getElementById('enroll-code').value.trim();
      if (!code) { say(document.getElementById('gate-msg'), 'bad', 'Введите код.'); return; }
      register(enrollBtn, document.getElementById('gate-msg'), {enrollment_code: code});
    });
  }
  const recoverBtn = document.getElementById('btn-recover');
  if (recoverBtn) {
    recoverBtn.addEventListener('click', function () {
      const code = document.getElementById('recover-code').value.trim();
      if (!code) { say(document.getElementById('gate-msg'), 'bad', 'Введите код.'); return; }
      register(recoverBtn, document.getElementById('gate-msg'), {recovery_code: code});
    });
  }
  document.querySelectorAll('.card[data-portfolio]').forEach(function (card) {
    const save = card.querySelector('.btn-save');
    const repl = card.querySelector('.btn-replace');
    const appl = card.querySelector('.btn-apply');
    if (save) save.addEventListener('click', function () { saveCard(card); });
    if (repl) repl.addEventListener('click', function () { replaceCard(card); });
    if (appl) appl.addEventListener('click', function () { applyCard(card); });
  });
});
"""


def _dot_class(row: dict) -> tuple[str, str]:
    """Цвет и словами — что сейчас с направлением."""
    if row.get("status") == "BLOCKED_TARGET":
        if row.get("configured"):
            return "warn", "Сохранено, применять пока некуда"
        return "warn", "Ожидает инфраструктуру"
    if not row.get("configured"):
        return "bad", "Не настроено"
    if not row.get("verified"):
        return "warn", "Сохранено, но не проверено"
    if row.get("applied_count") and row.get("applied_count") == row.get("consumer_count"):
        return "ok", "Проверено и применено"
    return "warn", "Проверено, но применено не везде"


def _fmt_date(value: str | None) -> str:
    if not value:
        return "—"
    return value.replace("T", " ").replace("Z", " UTC")


def card(row: dict, path: str) -> str:
    kind, words = _dot_class(row)
    configured = "yes" if row.get("configured") else "no"
    blocked = row.get("status") == "BLOCKED_TARGET"

    consumers = row.get("consumers") or []
    if consumers:
        items = "".join(
            f"<li>{html.escape(c.get('title') or c.get('consumer', ''))}"
            f"{' — цель недоступна' if not c.get('target_ok') else ''}</li>"
            for c in consumers
        )
        consumer_block = f'<ul class="consumers">{items}</ul>'
    else:
        consumer_block = ('<ul class="consumers"><li>Сайты этого направления ещё '
                          'не переданы</li></ul>')

    apply_button = ""
    if row.get("configured") and not blocked:
        apply_button = '<button type="button" class="ghost btn-apply">Применить к сайтам</button>'

    replace_button = ""
    form_display = "block"
    if row.get("configured"):
        replace_button = '<button type="button" class="ghost btn-replace">Заменить credentials</button>'
        form_display = "none"

    return f"""
<section class="card {kind}" data-portfolio="{html.escape(row['portfolio'])}"
         data-configured="{configured}">
  <h2><span class="dot"></span>{html.escape(row.get('title') or row['portfolio'])}</h2>
  <p class="hint">{html.escape(row.get('subtitle', ''))}</p>
  <p class="state"><b>{html.escape(words)}</b></p>
  <dl class="meta">
    <dt>Обновлено</dt><dd>{html.escape(_fmt_date(row.get('updated_at')))}</dd>
    <dt>Контрольная сумма</dt><dd>{html.escape(row.get('fingerprint') or '—')}</dd>
    <dt>Версия</dt><dd>{html.escape(str(row.get('version') or '—'))}</dd>
  </dl>
  <p class="hint">Контрольная сумма — короткий отпечаток значения. По ней видно,
  что credentials сменились, но восстановить их из неё нельзя.</p>
  {consumer_block}
  <div class="form-area" style="display:{form_display}">
    <label for="t-{html.escape(row['portfolio'])}">CDNVideoHub API Token</label>
    <input id="t-{html.escape(row['portfolio'])}" class="f-token" type="password"
           autocomplete="off" spellcheck="false" placeholder="вставьте токен">
    <label for="p-{html.escape(row['portfolio'])}">CDNVideoHub Publisher ID</label>
    <input id="p-{html.escape(row['portfolio'])}" class="f-publisher" type="text"
           autocomplete="off" spellcheck="false" placeholder="вставьте Publisher ID">
    <div class="row">
      <button type="button" class="btn-save">Проверить и сохранить</button>
    </div>
  </div>
  <div class="row">{replace_button}{apply_button}</div>
  <div class="msg"></div>
</section>"""


def page(rows: list[dict], csrf_token: str, path: str) -> str:
    cards = "".join(card(row, path) for row in rows)
    return f"""<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta name="robots" content="noindex, nofollow">
<meta name="csrf" content="{html.escape(csrf_token)}">
<title>Secret Hub — credentials направлений</title>
<style>{STYLE}</style>
</head><body>
<!-- {MARKER} -->
<div class="wrap">
<h1>Credentials направлений</h1>
<p class="sub">Здесь хранится по одному набору CDNVideoHub на направление.
Сохранённые значения показать нельзя — их можно только заменить.</p>
{cards}
<footer>Значения зашифрованы и применяются сервером. Панель их не хранит и не показывает.</footer>
</div>
<script src="{html.escape(path)}/app.js"></script>
</body></html>"""


def gate(csrf_token: str, path: str, *, enrollment_open: bool, has_passkey: bool) -> str:
    """Страница входа: passkey, первичная регистрация или восстановление."""
    blocks = []
    if has_passkey:
        blocks.append("""
  <div class="card">
    <h2>Вход</h2>
    <p class="hint">Подтвердите вход ключом устройства — Touch ID, Face ID или
    ключом безопасности.</p>
    <div class="row"><button type="button" id="btn-login">Войти</button></div>
  </div>""")
    if enrollment_open:
        blocks.append("""
  <div class="card">
    <h2>Первый вход</h2>
    <p class="hint">Введите код регистрации из консоли установки и создайте ключ
    на этом устройстве.</p>
    <label for="enroll-code">Код регистрации</label>
    <input id="enroll-code" type="text" autocomplete="off" spellcheck="false"
           placeholder="ABCDE-FGHJK-LMNPQ-RSTUV">
    <div class="row"><button type="button" id="btn-enroll">Создать ключ</button></div>
  </div>""")
    if has_passkey:
        blocks.append("""
  <div class="card">
    <h2>Нет доступа к устройству</h2>
    <p class="hint">Введите один из кодов восстановления, чтобы добавить ключ
    на другом устройстве. Каждый код работает один раз.</p>
    <label for="recover-code">Код восстановления</label>
    <input id="recover-code" type="text" autocomplete="off" spellcheck="false"
           placeholder="ABCDE-FGHJK-LMNPQ">
    <div class="row"><button type="button" class="ghost" id="btn-recover">Добавить ключ</button></div>
  </div>""")
    if not blocks:
        blocks.append("""
  <div class="card">
    <h2>Панель не настроена</h2>
    <p class="hint">Ни одного ключа не зарегистрировано, и код регистрации не
    выдан. Запустите установку на сервере, чтобы получить код.</p>
  </div>""")

    return f"""<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta name="robots" content="noindex, nofollow">
<meta name="csrf" content="{html.escape(csrf_token)}">
<title>Secret Hub — вход</title>
<style>{STYLE}</style>
</head><body>
<!-- {MARKER} -->
<div class="wrap gate">
<h1>Secret Hub</h1>
<p class="sub">Вход только по ключу устройства. Пароля здесь нет.</p>
<div id="gate-forms">{''.join(blocks)}</div>
<div id="recovery-box" class="card" style="display:none">
  <h2>Коды восстановления</h2>
  <div class="warnbox">Сохраните эти коды сейчас — они показываются один раз.
  Каждый код работает однократно и позволяет добавить ключ, если устройство
  недоступно.</div>
  <pre class="codes" id="recovery-codes"></pre>
  <div class="row"><button type="button" id="btn-codes-saved">Я сохранил коды</button></div>
</div>
<div id="gate-msg" class="msg"></div>
</div>
<script src="{html.escape(path)}/app.js"></script>
</body></html>"""
