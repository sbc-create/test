"""Офлайн-проверка конфигурации nginx: разбор и совместимость с 1.18.

Это не замена `nginx -t`, и выдавать её за него нельзя. Настоящую проверку
делает сам nginx на целевом хосте, и сценарий применения запускает её до того,
как что-нибудь перезагрузит. Здесь решается другая задача: поймать ошибку
раньше, чем конфигурация уедет на сервер, и — главное — поймать то, чего
`nginx -t` на новой версии не поймает вовсе.

Последнее и есть причина существования модуля. `nginx -t` на 1.27 молча примет
`http2 on;`, а на целевом 1.18 это неизвестная директива и отказ запуска.
Проверка «свежим бинарником» такую разницу пропускает по построению, поэтому
директивы сверяются с версией, в которой они появились.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

TARGET = (1, 18, 0)

#: Директивы, появившиеся после 1.18. Использовать их в этой конфигурации
#: нельзя: на целевой версии nginx откажется стартовать.
INTRODUCED_AFTER_1_18 = {
    "http2": (1, 25, 1),
    "http3": (1, 25, 0),
    "quic": (1, 25, 0),
    "ssl_reject_handshake": (1, 19, 4),
    "ssl_conf_command": (1, 19, 4),
    "proxy_ssl_conf_command": (1, 19, 4),
    "keepalive_time": (1, 19, 10),
    "proxy_cache_path_min_free": (1, 19, 1),
    "grpc_ssl_conf_command": (1, 19, 4),
    "listen_quic": (1, 25, 0),
    "proxy_protocol_tlv": (1, 23, 2),
    "mp4_start_key_frame": (1, 21, 4),
}

#: Директивы, которые обязаны нести `always`, иначе не попадут на ответы с
#: кодом ошибки — а именно они и отдаются, пока стенд закрыт паролем.
HEADER_DIRECTIVE = "add_header"

#: Простейший словарь известных директив уровня server/location, которые мы
#: используем. Незнакомая директива — повод остановиться и посмотреть, а не
#: молча пропустить: опечатка в имени выглядит точно так же.
KNOWN = {
    "server", "listen", "server_name", "location", "return", "root", "index",
    "add_header", "auth_basic", "auth_basic_user_file", "proxy_pass",
    "proxy_http_version", "proxy_set_header", "proxy_read_timeout",
    "ssl_certificate", "ssl_certificate_key", "ssl_trusted_certificate",
    "ssl_protocols", "ssl_ciphers", "ssl_prefer_server_ciphers",
    "ssl_session_cache", "ssl_session_timeout", "ssl_session_tickets",
    "default_type", "access_log", "error_log", "client_max_body_size",
}


@dataclass
class Result:
    problems: list = field(default_factory=list)
    directives: set = field(default_factory=set)
    servers: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems

    def fail(self, message: str) -> None:
        self.problems.append(message)


def _strip_comments(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] if "#" in line else line
                     for line in text.split("\n"))


def _balanced(text: str) -> bool:
    depth = 0
    in_string = None
    for index, char in enumerate(text):
        if in_string:
            if char == in_string and text[index - 1] != "\\":
                in_string = None
            continue
        if char in "\"'":
            in_string = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def check(text: str, *, expect_tls: bool) -> Result:
    """Разбирает конфигурацию и проверяет то, что можно проверить без nginx."""
    result = Result()
    body = _strip_comments(text)

    if not _balanced(body):
        result.fail("фигурные скобки не сбалансированы")
        return result

    for statement in re.finditer(r"^\s*([a-z_][a-z0-9_]*)\b([^;{}]*)", body, re.M):
        name, tail = statement.group(1), statement.group(2)
        result.directives.add(name)
        if name in INTRODUCED_AFTER_1_18:
            version = ".".join(str(part) for part in INTRODUCED_AFTER_1_18[name])
            result.fail(
                f"директива «{name}» появилась в nginx {version}: "
                f"на целевой {'.'.join(str(p) for p in TARGET)} это отказ запуска"
            )
        if name == "server" and tail.strip() == "":
            result.servers += 1
        if name == HEADER_DIRECTIVE and "always" not in tail:
            result.fail(
                f"add_header без always: {tail.strip()[:60]} — заголовок не "
                "попадёт на 401, 404 и 5xx"
            )
        if name not in KNOWN and name not in INTRODUCED_AFTER_1_18:
            result.fail(f"незнакомая директива «{name}»: опечатка выглядит так же")

    # `http2` как параметр listen — правильная форма для 1.18. Отдельной
    # директивой она встречается только в 1.25+, и это уже поймано выше.
    for listen in re.findall(r"^\s*listen\s+([^;]+);", body, re.M):
        if "ssl" in listen and not expect_tls:
            result.fail(f"listen {listen.strip()}: TLS в фазе без сертификата")
        if "http2" in listen and "ssl" not in listen:
            result.fail(f"listen {listen.strip()}: http2 без ssl")

    if expect_tls:
        if "ssl_certificate" not in result.directives:
            result.fail("фаза с TLS, но сертификат не задан")
        if "ssl_protocols" not in result.directives:
            result.fail("ssl_protocols не задан: набор протоколов остался бы умолчанием")
    elif "ssl_certificate" in result.directives:
        result.fail("сертификат задан в фазе, где его ещё не существует")

    if "server_name" not in result.directives:
        result.fail("ни одного server_name: конфигурация ничего не обслуживает")
    return result


def check_bundle(parts: dict, *, expect_tls: bool) -> dict:
    """Проверяет набор файлов конфигурации разом."""
    out = {}
    for name, text in sorted(parts.items()):
        result = check(text, expect_tls=expect_tls)
        out[name] = {"ok": result.ok, "problems": result.problems,
                     "directives": sorted(result.directives)}
    return out
