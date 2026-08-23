"""Разметка, которую аналитика добавляет в страницу.

Два элемента и ни одного больше: подключение клиента событий и мета-тег
подтверждения прав Вебмастера. Инлайнового JavaScript здесь нет намеренно —
конфигурация передаётся через `data-*` атрибуты внешнего скрипта, поэтому CSP
не приходится выбирать между работающей аналитикой и работающим плеером.
"""
from __future__ import annotations

import html
import re

#: Маркер подтверждения — это код от Яндекса, а не произвольная строка.
#: Всё, что не похоже на код, в HTML не попадает: чужой текст в head опаснее,
#: чем отсутствующий мета-тег.
MARKER_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")

ANALYTICS_SCRIPT_URL = "/assets/analytics.js"


def analytics_script_tag(
    *,
    counter_id: int | None,
    allowed_hosts: list[str],
    environment: str,
    enabled: bool,
    script_url: str = ANALYTICS_SCRIPT_URL,
) -> str:
    """Тег подключения клиента событий.

    Возвращает пустую строку, если сбор невозможен в принципе: нет счётчика,
    аналитика выключена, окружение не production или список разрешённых
    hostname пуст. Пустая строка означает, что в странице нет ни тега Метрики,
    ни клиента — а не «есть, но молчит».
    """
    if not enabled or not counter_id or environment != "production" or not allowed_hosts:
        return ""
    hosts = ",".join(html.escape(h.strip().lower(), quote=True) for h in allowed_hosts if h.strip())
    if not hosts:
        return ""
    return (
        f'<script src="{html.escape(script_url, quote=True)}" '
        'data-analytics-provider="yandex" '
        f'data-counter-id="{int(counter_id)}" '
        f'data-allowed-hosts="{hosts}" '
        f'data-environment="{html.escape(environment, quote=True)}" '
        'data-analytics-enabled="true" defer></script>'
    )


def verification_meta(marker: str | None) -> str:
    """Мета-тег подтверждения прав. Формат — дословно из документации Вебмастера.

    Тег постоянный: Яндекс перепроверяет права, и релиз, потерявший маркер,
    теряет и подтверждение. Поэтому маркер живёт в реестре и печатается при
    каждой сборке, а не вставляется руками один раз.
    """
    if not marker or not MARKER_RE.match(marker):
        return ""
    return f'<meta name="yandex-verification" content="{html.escape(marker, quote=True)}" />'


def verification_html_file(marker: str | None) -> tuple[str, str] | None:
    """`(имя файла, содержимое)` для способа HTML_FILE. Формат из документации."""
    if not marker or not MARKER_RE.match(marker):
        return None
    body = (
        "<html>\n"
        "    <head>\n"
        '        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">\n'
        "    </head>\n"
        f"    <body>Verification: {html.escape(marker)}</body>\n"
        "</html>\n"
    )
    return f"yandex_{marker}.html", body
