"""Публикация формы на уже работающем домене и живая проверка результата.

Форма живёт по одному адресу — ``https://<домен>/__factory-secrets`` — и только
пока идёт сессия. Снаружи это обычный HTTPS с настоящим сертификатом домена;
внутри машины nginx проксирует на петлевой порт, где слушает форма.

Как это устроено и почему именно так:

* **отдельный location, а не отдельный vhost.** Второй `server` с тем же
  `server_name` nginx примет с предупреждением и молча проигнорирует — работал
  бы первый. Location в существующем блоке предсказуем.

* **include одной строкой, с маркерами.** В боевой vhost добавляется ровно одна
  строка `include …/secret-hub.d/*.conf;`, обрамлённая маркерами. Всё остальное
  меняется внутри подключаемого файла, а не в конфигурации сайта. Файл vhost
  копируется в бэкап до правки и восстанавливается при откате.

* **два состояния подключаемого файла.** Простаивая, он отдаёт `404` — не
  «ничего», а именно 404: без location запрос ушёл бы в `location /`, где
  сейчас стоит Basic Auth, и вместо 404 браузер получил бы 401. Требование
  «после закрытия отвечать 404» иначе не выполняется.

* **`auth_basic off` в location формы.** На стенде yummyani Basic Auth включён в
  `location /`. Соседний location его не наследует, но полагаться на это
  правило вместо явной директивы — значит зависеть от того, что пароль никогда
  не переедет в `server`-блок.

* **`access_log off` и `error_log off`** — в журнале не должно быть ни адреса,
  ни тела, ни заголовков этой сессии.

Живая проверка (:func:`verify_live`) выполняется на настоящем установленном
nginx до того, как оператору покажут адрес и код. Локальный тест или временный
nginx доказательством не считаются, поэтому проверка ходит по публичному имени.
"""
from __future__ import annotations

import contextlib
import re
import shutil
import ssl
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

#: Публичный путь формы. Единственный, по которому она когда-либо доступна.
DEFAULT_PATH = "/__factory-secrets"

#: Куда кладётся подключаемый файл. Отдельный каталог, чтобы `include *.conf`
#: не подхватил ничего постороннего.
SNIPPET_DIR = Path("/etc/nginx/snippets/secret-hub.d")
SNIPPET = SNIPPET_DIR / "enroll.conf"

#: Маркеры включения в боевом vhost. По ним же оно и снимается.
BEGIN = "# >>> secret-hub enroll include (управляется автоматически) >>>"
END = "# <<< secret-hub enroll include <<<"

BACKUP_DIR = Path("/var/lib/site-factory-secret-hub/nginx-backups")

IDLE_SNIPPET = f"""# Состояние: форма не запущена.
#
# Именно 404, а не отсутствие location: без него запрос ушёл бы в `location /`,
# где на этом стенде стоит Basic Auth, и вместо 404 браузер получил бы 401.
location ^~ {DEFAULT_PATH} {{
    access_log off;
    log_not_found off;
    auth_basic off;
    add_header X-Robots-Tag "noindex, nofollow" always;
    return 404;
}}
"""

ACTIVE_SNIPPET = """# Состояние: идёт сессия ввода. Файл будет перезаписан по её завершении.
location ^~ {path} {{
    # Ни строки в журнал: здесь проходит одноразовый код и тело формы.
    access_log off;
    log_not_found off;

    # Явно, а не по наследованию: на этом стенде Basic Auth включён в
    # `location /`, и форма обязана отвечать без WWW-Authenticate.
    auth_basic off;

    add_header X-Robots-Tag "noindex, nofollow" always;
    add_header Cache-Control "no-store" always;
    add_header Referrer-Policy "no-referrer" always;

    # 8 KiB — тот же предел, что проверяет сама форма. Здесь он отсекает
    # переросшее тело до того, как оно дойдёт до процесса.
    client_max_body_size 8k;
    client_body_buffer_size 8k;

    proxy_pass http://127.0.0.1:{port};
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Connection "";
    proxy_connect_timeout 5s;
    proxy_read_timeout 60s;
}}
"""


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""

    def as_dict(self) -> dict:
        return {"check": self.name, "ok": self.ok, "detail": self.detail}


@dataclass
class LiveVerification:
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append(Check(name, ok, detail))

    def as_dict(self) -> dict:
        return {"ok": self.ok, "checks": [c.as_dict() for c in self.checks]}

    def failures(self) -> list[str]:
        return [f"{c.name}: {c.detail}" for c in self.checks if not c.ok]


class PublishError(RuntimeError):
    """nginx отказался принять конфигурацию или её не удалось применить."""


def _run(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True, timeout=timeout,
                          check=False)


def nginx_test() -> tuple[bool, str]:
    proc = _run("nginx", "-t")
    return proc.returncode == 0, (proc.stderr or proc.stdout).strip()


def nginx_reload() -> tuple[bool, str]:
    proc = _run("systemctl", "reload", "nginx")
    if proc.returncode == 0:
        return True, ""
    fallback = _run("nginx", "-s", "reload")
    return fallback.returncode == 0, (fallback.stderr or proc.stderr).strip()


def _write(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.chmod(mode)
    tmp.replace(path)


def backup_vhost(vhost: Path) -> Path:
    """Копия боевого vhost до правки. Без неё откат — это переписывание по памяти."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.chmod(0o700)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = BACKUP_DIR / f"{vhost.name}.{stamp}"
    shutil.copy2(vhost, target)
    target.chmod(0o600)
    return target


def include_present(text: str) -> bool:
    return BEGIN in text


def _apex_server_span(text: str, server_name: str) -> tuple[int, int]:
    """Границы `server`-блока, обслуживающего ровно этот домен по HTTPS.

    Разбор простой, но не наивный: блоки ищутся по балансу фигурных скобок, а из
    подходящих выбирается тот, у которого `server_name` — ровно запрошенное имя
    и есть `listen 443`. Блок с `www.` и блок редиректа с :80 не подходят: в
    первом форма оказалась бы за 308-редиректом, во втором — на HTTP.
    """
    for match in re.finditer(r"\bserver\s*\{", text):
        start = match.end() - 1
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    block = text[start:index + 1]
                    names = re.search(r"\bserver_name\s+([^;]+);", block)
                    if not names:
                        break
                    listed = names.group(1).split()
                    if listed == [server_name] and re.search(r"\blisten\s+443\b", block):
                        return start, index + 1
                    break
    raise PublishError(
        f"В конфигурации не найден HTTPS server-блок ровно для «{server_name}». "
        "Правка вслепую в такой ситуации опаснее отказа."
    )


def ensure_include(vhost: Path, server_name: str) -> dict:
    """Идемпотентно добавляет include в боевой vhost. Возвращает, что сделано."""
    text = vhost.read_text(encoding="utf-8")
    if include_present(text):
        return {"changed": False, "backup": None,
                "detail": "include уже присутствует"}

    backup = backup_vhost(vhost)
    start, end = _apex_server_span(text, server_name)
    block = text[start:end]
    insertion = (
        f"\n    {BEGIN}\n"
        f"    include {SNIPPET_DIR}/*.conf;\n"
        f"    {END}\n"
    )
    # Вставка перед закрывающей скобкой блока: location'ы внутри `server`
    # равноправны, порядок между ними значения не имеет, а `^~` берёт
    # приоритет над префиксным `location /` независимо от места в файле.
    patched_block = block[:-1].rstrip() + "\n" + insertion + "}"
    updated = text[:start] + patched_block + text[end:]
    _write(vhost, updated)

    ok, detail = nginx_test()
    if not ok:
        shutil.copy2(backup, vhost)
        raise PublishError(f"nginx отверг конфигурацию с include, изменения откачены: {detail}")
    return {"changed": True, "backup": str(backup), "detail": "include добавлен"}


def remove_include(vhost: Path) -> dict:
    """Снимает include из боевого vhost. Используется при полном демонтаже."""
    text = vhost.read_text(encoding="utf-8")
    if not include_present(text):
        return {"changed": False, "detail": "include отсутствует"}
    backup = backup_vhost(vhost)
    pattern = re.compile(
        rf"\n?[ \t]*{re.escape(BEGIN)}.*?{re.escape(END)}[ \t]*\n?", re.S)
    _write(vhost, pattern.sub("\n", text))
    ok, detail = nginx_test()
    if not ok:
        shutil.copy2(backup, vhost)
        raise PublishError(f"nginx отверг конфигурацию без include, откачено: {detail}")
    return {"changed": True, "backup": str(backup), "detail": "include снят"}


def set_idle() -> None:
    """Форма не запущена: адрес отвечает 404."""
    _write(SNIPPET, IDLE_SNIPPET)


def set_active(port: int, path: str = DEFAULT_PATH) -> None:
    """Форма запущена: адрес проксируется на петлевой порт."""
    _write(SNIPPET, ACTIVE_SNIPPET.format(port=int(port), path=path))


def activate(vhost: Path, server_name: str, port: int, path: str = DEFAULT_PATH) -> dict:
    """Полный путь публикации: include, активный снимок, проверка, перезагрузка."""
    result = ensure_include(vhost, server_name)
    previous = SNIPPET.read_text(encoding="utf-8") if SNIPPET.exists() else None
    set_active(port, path)
    ok, detail = nginx_test()
    if not ok:
        # Возврат к прежнему состоянию до перезагрузки: работающий сайт не
        # должен пострадать от того, что мы не смогли опубликовать форму.
        if previous is None:
            set_idle()
        else:
            _write(SNIPPET, previous)
        raise PublishError(f"nginx отверг конфигурацию формы: {detail}")
    reloaded, reload_detail = nginx_reload()
    if not reloaded:
        set_idle()
        nginx_reload()
        raise PublishError(f"nginx не перезагрузился: {reload_detail}")
    result["active"] = True
    return result


def deactivate() -> dict:
    """Снимает форму: адрес снова отвечает 404. Include остаётся на месте."""
    set_idle()
    ok, detail = nginx_test()
    if not ok:
        raise PublishError(f"nginx отверг конфигурацию простоя: {detail}")
    reloaded, reload_detail = nginx_reload()
    return {"idle": True, "reloaded": reloaded, "detail": reload_detail}


# --- живая проверка -------------------------------------------------------
def _fetch(url: str, *, timeout: int = 15) -> tuple[int | None, dict, str, str]:
    """GET по публичному имени. Возвращает статус, заголовки, тело и причину сбоя."""
    request = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "secret-hub-verify"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(65536).decode("utf-8", "replace")
            return response.status, dict(response.headers), body, ""
    except urllib.error.HTTPError as exc:
        body = ""
        with contextlib.suppress(Exception):
            body = exc.read(65536).decode("utf-8", "replace")
        return exc.code, dict(exc.headers or {}), body, ""
    except urllib.error.URLError as exc:
        return None, {}, "", f"{exc.__class__.__name__}: {exc.reason}"
    except TimeoutError:
        return None, {}, "", "таймаут"


def certificate_subject(server_name: str, *, timeout: int = 15) -> tuple[bool, str]:
    """Сертификат, который домен фактически отдаёт, принадлежит этому домену.

    Проверяется штатной валидацией: соединение с ``check_hostname=True`` просто
    не установится, если имя не совпадает. Читать поля вручную и сравнивать
    строки было бы менее строго, чем то, что уже умеет ssl.
    """
    import socket

    context = ssl.create_default_context()
    try:
        with (socket.create_connection((server_name, 443), timeout=timeout) as raw,
              context.wrap_socket(raw, server_hostname=server_name) as tls):
            cert = tls.getpeercert()
    except ssl.SSLCertVerificationError as exc:
        return False, f"сертификат не проходит проверку для {server_name}: {exc.verify_message}"
    except (OSError, TimeoutError) as exc:
        return False, f"соединение с {server_name}:443 не установлено ({exc.__class__.__name__})"
    names = {value for key, value in cert.get("subject", ((),))[0] if key == "commonName"}
    for kind, value in cert.get("subjectAltName", ()):
        if kind == "DNS":
            names.add(value)
    return True, f"валиден для {server_name} (SAN: {', '.join(sorted(names)) or '—'})"


def verify_live(server_name: str, marker: str, *, path: str = DEFAULT_PATH,
                main_path: str = "/") -> LiveVerification:
    """Проверка на настоящем установленном nginx, до показа адреса и кода.

    Пять требований задания, каждое отдельной строкой отчёта. Ни одно из них не
    выводится из другого: «конфигурация применена» не означает «endpoint
    отвечает», а «endpoint отвечает» не означает «основной сайт жив».
    """
    result = LiveVerification()
    base = f"https://{server_name}"

    # 1. Сертификат домена. Идёт первым: если TLS не тот, остальные проверки
    #    измеряли бы не то, что увидит оператор.
    cert_ok, cert_detail = certificate_subject(server_name)
    result.add("сертификат соответствует домену", cert_ok, cert_detail)

    # 2. Endpoint отвечает 200 и не требует пароля.
    status, headers, body, error = _fetch(base + path)
    if error:
        result.add("endpoint отвечает 200", False, error)
        result.add("endpoint не требует Basic Auth", False, "ответ не получен")
        result.add("в HTML присутствует marker Secret Hub", False, "ответ не получен")
    else:
        result.add("endpoint отвечает 200", status == 200, f"HTTP {status}")
        challenge = headers.get("WWW-Authenticate")
        result.add("endpoint не требует Basic Auth", not challenge,
                   f"WWW-Authenticate: {challenge}" if challenge else "заголовка нет")
        result.add("в HTML присутствует marker Secret Hub", marker in body,
                   "marker найден" if marker in body
                   else "marker не найден: отвечает не форма этой сессии")

    # 3. Основной сайт продолжает отвечать. 401 здесь — штатный ответ стенда с
    #    Basic Auth и означает, что сайт жив; неответ означает, что мы его
    #    сломали.
    main_status, _, _, main_error = _fetch(base + main_path)
    result.add("основной сайт продолжает отвечать", main_error == "" and main_status is not None,
               main_error or f"HTTP {main_status}")

    # 4. access_log выключен именно для endpoint'а.
    snippet_text = SNIPPET.read_text(encoding="utf-8") if SNIPPET.exists() else ""
    result.add("access_log для endpoint выключен", "access_log off;" in snippet_text,
               "директива на месте" if "access_log off;" in snippet_text
               else f"в {SNIPPET} нет access_log off")

    # 5. Secret Hub не добавил Basic Auth.
    result.add("Secret Hub не ставит Basic Auth",
               "auth_basic_user_file" not in snippet_text,
               "в конфигурации формы пароля нет")
    return result


def verify_gone(server_name: str, *, path: str = DEFAULT_PATH) -> LiveVerification:
    """После закрытия сессии адрес обязан отвечать 404, а не 401 и не 200."""
    result = LiveVerification()
    status, headers, _, error = _fetch(f"https://{server_name}{path}")
    if error:
        result.add("endpoint исчез (404)", False, error)
        return result
    result.add("endpoint исчез (404)", status == 404, f"HTTP {status}")
    challenge = headers.get("WWW-Authenticate")
    result.add("после закрытия нет запроса пароля", not challenge,
               f"WWW-Authenticate: {challenge}" if challenge else "заголовка нет")
    return result
