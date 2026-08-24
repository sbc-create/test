"""Публичный fixture-staging направления Lords: конфигурация трёх сайтов.

Модуль порождает всё, что нужно управляющему серверу, из двух источников —
реестра направления и пакетов сайтов. Второго списка доменов, портов и каталогов
не существует: разойтись нечему.

Что здесь важно и почему именно так.

**Заглушка не притворяется production.** Каталог синтетический, поэтому доступ
закрыт Basic Auth, ответ несёт `X-Robots-Tag: noindex, nofollow`, `robots.txt`
закрывает сайт целиком, а sitemap не получает ни одного адреса. Ни один из этих
четырёх барьеров не заменяет остальные: пароль защищает от людей, заголовок — от
роботов, robots.txt — от вежливых роботов, пустой sitemap — от нас самих.

**Две фазы, а не одна.** Пока сертификата нет, конфигурация с `ssl_certificate`
не проходит `nginx -t`, и попытка применить её сразу оставила бы сервер со
сломанным конфигом. Поэтому фаза 1 поднимает только HTTP и отдаёт ACME-challenge,
а фаза 2 включает HTTPS — после того, как сертификаты выпущены.

**Неизвестный Host получает 421.** Не 404 и не первый попавшийся сайт: сервер
честно сообщает, что этим именем он не занимается. Для HTTPS это требует
собственного сертификата у default-сервера — `ssl_reject_handshake` появился
только в nginx 1.19.4, а целевая версия 1.18.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from factory.paths import PATHS

REGISTRY = "config/directions/lords.json"

#: Куда кладётся всё, что переносится на сервер.
ARTIFACT_DIR = ("lords", "staging")

#: Каталог конфигурации Lords на сервере. Ничего вне него скрипт не трогает.
NGINX_DIR = "/etc/nginx/lords"
RUNTIME_ROOT = "/srv/lords"
ACME_ROOT = "/var/www/lords-acme"
HTPASSWD = f"{NGINX_DIR}/.htpasswd"
CREDENTIALS_FILE = "/root/lords-staging-credentials"
DEFAULT_CERT = f"{NGINX_DIR}/default-self-signed"

#: Минимальная версия nginx, на которой обязана работать конфигурация.
TARGET_NGINX = "1.18.0"


@dataclass(frozen=True)
class StagingSite:
    site_id: str
    profile: str
    apex: str
    www: str
    port: int
    runtime_root: str

    @property
    def unit(self) -> str:
        # `site_id` уже начинается с «lords-», второй префикс дал бы
        # lords-lords-01.service.
        return f"{self.site_id}.service"

    @property
    def conf(self) -> str:
        return f"{NGINX_DIR}/{self.site_id}.conf"

    @property
    def data_dir(self) -> str:
        return f"{self.runtime_root}/data"

    @property
    def releases_dir(self) -> str:
        return f"{self.runtime_root}/releases"

    @property
    def current(self) -> str:
        return f"{self.runtime_root}/current"


def load_registry(root: Path | None = None) -> dict:
    base = Path(root) if root else PATHS.root
    return json.loads((base / REGISTRY).read_text(encoding="utf-8"))


def sites(root: Path | None = None) -> list[StagingSite]:
    """Три сайта направления. Реестр и пакет обязаны совпадать.

    Расхождение между реестром и manifest не сглаживается: два источника, тихо
    разошедшихся в домене, — это выкат чужого сайта на чужое имя.
    """
    base = Path(root) if root else PATHS.root
    out = []
    for entry in load_registry(base)["domains"]:
        site_id = entry["site_id"]
        package = yaml.safe_load(
            (base / "sites" / site_id / "package.yaml").read_text(encoding="utf-8"))
        if package.get("domain") != entry["apex"]:
            raise ValueError(
                f"{site_id}: домен в реестре ({entry['apex']}) и в пакете "
                f"({package.get('domain')}) не совпадают"
            )
        if package.get("canonical_url") != f"https://{entry['apex']}/":
            raise ValueError(f"{site_id}: canonical_url не соответствует домену реестра")
        if (package.get("tenant") or {}).get("seo_profile") != entry["profile"]:
            raise ValueError(f"{site_id}: профиль в реестре и в пакете не совпадают")
        if package.get("seo_indexing_enabled"):
            raise ValueError(f"{site_id}: индексация включена — стенд так не публикуется")
        out.append(StagingSite(
            site_id=site_id,
            profile=entry["profile"],
            apex=entry["apex"],
            www=entry["www"],
            port=int(entry["staging_port"]),
            runtime_root=entry["runtime_root"],
        ))

    ports = [s.port for s in out]
    roots = [s.runtime_root for s in out]
    hosts = [s.apex for s in out] + [s.www for s in out]
    for name, values in (("порт", ports), ("каталог", roots), ("имя", hosts)):
        if len(set(values)) != len(values):
            raise ValueError(f"{name} повторяется между сайтами: {values}")
    return out


# ---------------------------------------------------------------------------
# Nginx
# ---------------------------------------------------------------------------
#: Общие заголовки. `always` обязателен: без него заголовок не попадёт на 401,
#: 404 и 5xx, а именно эти ответы отдаются чаще всего, пока стенд под паролем.
COMMON_HEADERS = """
    add_header X-Robots-Tag "noindex, nofollow" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
"""

#: TLS. Набор подобран под nginx 1.18 и OpenSSL 1.1.1: TLS 1.3 доступен,
#: `ssl_conf_command` (1.19.4+) не используется, `http2` задаётся параметром
#: `listen`, а не отдельной директивой (она появилась только в 1.25.1).
TLS_BLOCK = """
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;
    ssl_session_cache shared:LordsSSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
"""


def _proxy_block(site: StagingSite) -> str:
    return f"""
    location / {{
        auth_basic "Lords staging";
        auth_basic_user_file {HTPASSWD};

        proxy_pass http://127.0.0.1:{site.port};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }}

    # Пробы рантайма без пароля: мониторинг не носит учётные данные.
    # Наружу они ничего не рассказывают, кроме готовности процесса.
    location = /healthz {{
        proxy_pass http://127.0.0.1:{site.port}/healthz;
        access_log off;
    }}
    location = /readyz {{
        proxy_pass http://127.0.0.1:{site.port}/readyz;
        access_log off;
    }}
"""


def nginx_phase1(site: StagingSite) -> str:
    """Фаза 1: только HTTP. Отдаёт ACME-challenge, всё остальное — заглушка.

    Сертификата ещё нет, поэтому HTTPS-блока здесь тоже нет: конфигурация с
    `ssl_certificate` на несуществующий файл не проходит `nginx -t`, и сервер
    остался бы со сломанным конфигом.
    """
    return f"""# {site.site_id} → {site.apex} (фаза 1: выпуск сертификата)
# Сгенерировано фабрикой из {REGISTRY}. Править вручную не нужно.
server {{
    listen 80;
    listen [::]:80;
    server_name {site.apex} {site.www};
{COMMON_HEADERS}
    location ^~ /.well-known/acme-challenge/ {{
        root {ACME_ROOT};
        default_type "text/plain";
        auth_basic off;
    }}

    location / {{
        return 503 "Lords staging: сертификат ещё не выпущен.\\n";
        default_type "text/plain; charset=utf-8";
    }}
}}
"""


def nginx_phase2(site: StagingSite) -> str:
    """Фаза 2: HTTPS, www → apex через 308, Basic Auth, noindex."""
    cert = f"/etc/letsencrypt/live/{site.apex}"
    return f"""# {site.site_id} → {site.apex} (профиль {site.profile}, порт {site.port})
# Сгенерировано фабрикой из {REGISTRY}. Править вручную не нужно.

# HTTP: только ACME-challenge и перевод на HTTPS.
server {{
    listen 80;
    listen [::]:80;
    server_name {site.apex} {site.www};
{COMMON_HEADERS}
    location ^~ /.well-known/acme-challenge/ {{
        root {ACME_ROOT};
        default_type "text/plain";
        auth_basic off;
    }}

    location / {{
        return 308 https://$host$request_uri;
    }}
}}

# www → apex. Отдельный сервер, а не `if` внутри общего: условие внутри
# location в nginx ведёт себя не так, как ожидает большинство читающих.
server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {site.www};

    ssl_certificate {cert}/fullchain.pem;
    ssl_certificate_key {cert}/privkey.pem;
    ssl_trusted_certificate {cert}/chain.pem;
{TLS_BLOCK}{COMMON_HEADERS}
    # 308, а не 301: метод запроса обязан сохраниться.
    return 308 https://{site.apex}$request_uri;
}}

# Сам сайт.
server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {site.apex};

    ssl_certificate {cert}/fullchain.pem;
    ssl_certificate_key {cert}/privkey.pem;
    ssl_trusted_certificate {cert}/chain.pem;
{TLS_BLOCK}{COMMON_HEADERS}
    client_max_body_size 1m;

    access_log /var/log/nginx/{site.site_id}.access.log;
    error_log  /var/log/nginx/{site.site_id}.error.log;
{_proxy_block(site)}}}
"""


def nginx_default_server(phase: int) -> str:
    """Сервер по умолчанию: неизвестный Host получает 421.

    421 (Misdirected Request) — это «я не обслуживаю это имя», и именно так надо
    отвечать на чужой Host. 404 сказал бы «такой страницы нет», то есть признал
    бы имя своим; отдавать вместо этого первый попавшийся сайт значило бы
    развесить его по всем именам, которые указывают на этот адрес.
    """
    https = "" if phase == 1 else f"""
server {{
    listen 443 ssl http2 default_server;
    listen [::]:443 ssl http2 default_server;
    server_name _;

    # Собственный самоподписанный сертификат нужен потому, что
    # `ssl_reject_handshake` появился только в nginx 1.19.4, а цель — 1.18.
    ssl_certificate {DEFAULT_CERT}.crt;
    ssl_certificate_key {DEFAULT_CERT}.key;
{TLS_BLOCK}{COMMON_HEADERS}
    return 421 "Этот сервер не обслуживает запрошенное имя.\\n";
    default_type "text/plain; charset=utf-8";
}}
"""
    return f"""# Сервер по умолчанию направления Lords. Сгенерировано фабрикой.
server {{
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
{COMMON_HEADERS}
    location ^~ /.well-known/acme-challenge/ {{
        root {ACME_ROOT};
        default_type "text/plain";
    }}

    location / {{
        return 421 "Этот сервер не обслуживает запрошенное имя.\\n";
        default_type "text/plain; charset=utf-8";
    }}
}}
{https}"""


# ---------------------------------------------------------------------------
# systemd
# ---------------------------------------------------------------------------
#: Строка LoadCredential живого режима.
#:
#: Publisher ID приходит именно так, а не через Environment=: значения из
#: Environment= видны в `systemctl show` и в /proc/<pid>/environ, а каталог
#: credentials доступен только процессу юнита и живёт в tmpfs.
#:
#: API-токен сюда сознательно не загружается. Этот процесс обслуживает публичный
#: трафик, а токен нужен только сборке каталога: выдавать его публичной службе
#: значило бы расширять поверхность утечки без единой причины.
LIVE_CREDENTIALS = (
    "LoadCredential=cdnvideohub-publisher-id:"
    "/etc/site-factory/secrets/cdnvideohub/lords/publisher-id\n"
)


def systemd_unit(site: StagingSite, *, live: bool = False) -> str:
    """Юнит одного сайта. Слушает только петлевой интерфейс.

    Наружу сайт выходит исключительно через nginx: там пароль, TLS и заголовки.
    Процесс, доступный снаружи напрямую, обошёл бы всё это разом.

    `live` добавляет LoadCredential. Строка появляется только вместе с живым
    режимом намеренно: systemd не умеет необязательный LoadCredential и не
    запускает юнит, если файла нет. Безусловная строка сломала бы работающий
    fixture-стенд, у которого секретов нет и быть не должно.
    """
    credentials = LIVE_CREDENTIALS if live else ""
    return f"""[Unit]
Description=Lords staging {site.site_id} ({site.apex}, профиль {site.profile})
Documentation=file://{site.runtime_root}/current/README.md
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=lords
Group=lords
WorkingDirectory={site.current}
Environment=LORDS_HOST=127.0.0.1
Environment=LORDS_PORT={site.port}
Environment=PYTHONDONTWRITEBYTECODE=1
{credentials}ExecStart=/usr/bin/python3 {site.current}/serve.py
Restart=on-failure
RestartSec=2

# Права по минимуму: рантайм раздаёт заранее собранные файлы и больше ничего.
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6
RestrictNamespaces=true
LockPersonality=true
MemoryDenyWriteExecute=true
ReadWritePaths={site.data_dir}

[Install]
WantedBy=multi-user.target
"""


# ---------------------------------------------------------------------------
# Сборка всего, что переносится на сервер
# ---------------------------------------------------------------------------
def build_staging(output: Path | None = None, root: Path | None = None) -> dict:
    """Готовит конфигурацию трёх сайтов и проверяет её офлайн.

    Возвращает сводку. Ничего не применяет: применение — дело сценария на
    самом хосте, и оно требует root.
    """
    from factory.lords import bundle as bundle_mod
    from factory.lords import nginx_check

    base = Path(root) if root else PATHS.root
    directory = Path(output) if output else PATHS.artifact_dir(*ARTIFACT_DIR)
    (directory / "nginx" / "phase1").mkdir(parents=True, exist_ok=True)
    (directory / "nginx" / "phase2").mkdir(parents=True, exist_ok=True)
    (directory / "systemd").mkdir(parents=True, exist_ok=True)

    entries = sites(base)
    phase1 = {f"{s.site_id}.conf": nginx_phase1(s) for s in entries}
    phase1["00-default.conf"] = nginx_default_server(1)
    phase2 = {f"{s.site_id}.conf": nginx_phase2(s) for s in entries}
    phase2["00-default.conf"] = nginx_default_server(2)

    for name, text in phase1.items():
        (directory / "nginx" / "phase1" / name).write_text(text, encoding="utf-8")
    for name, text in phase2.items():
        (directory / "nginx" / "phase2" / name).write_text(text, encoding="utf-8")
    for site in entries:
        (directory / "systemd" / site.unit).write_text(systemd_unit(site), encoding="utf-8")

    checks = {
        "phase1": nginx_check.check_bundle(phase1, expect_tls=False),
        "phase2": nginx_check.check_bundle(phase2, expect_tls=True),
    }
    problems = [
        f"{phase}/{name}: {problem}"
        for phase, files in checks.items()
        for name, outcome in files.items()
        for problem in outcome["problems"]
    ]
    if problems:
        raise ValueError("конфигурация nginx не прошла офлайн-проверку: " + "; ".join(problems))

    bundles = {}
    for site in entries:
        built = bundle_mod.build_bundle(site.site_id)
        bundles[site.site_id] = {
            "archive": built["archive"],
            "release": built["release"],
            "sha256": built["sha256"],
            "digest": built["digest"],
        }

    summary = {
        "target": "lords-staging-control-01",
        "origin_ipv4": load_registry(base)["origin_ipv4"],
        "nginx_target_version": TARGET_NGINX,
        "offline_check": "пройдена; настоящий nginx -t выполняет сценарий на хосте",
        "sites": [
            {
                "site_id": s.site_id, "profile": s.profile, "apex": s.apex, "www": s.www,
                "port": s.port, "runtime_root": s.runtime_root, "unit": s.unit,
                "url": f"https://{s.apex}/", "indexing": "disabled",
                "basic_auth": "required", "release": bundles[s.site_id]["release"],
                "archive_sha256": bundles[s.site_id]["sha256"],
            }
            for s in entries
        ],
        "paths": {
            "nginx_dir": NGINX_DIR, "runtime_root": RUNTIME_ROOT,
            "acme_root": ACME_ROOT, "htpasswd": HTPASSWD,
            "credentials_file": CREDENTIALS_FILE,
        },
        "not_touched": [
            "конфигурация, контейнеры, базы и бэкапы YummyAnime",
            "порты вне диапазона 9101-9103",
            f"всё вне {NGINX_DIR}, {RUNTIME_ROOT}, {ACME_ROOT} и /etc/letsencrypt",
        ],
    }
    (directory / "staging.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    (directory / "nginx-check.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return summary
