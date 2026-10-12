#!/usr/bin/env python3
"""www-зеркала: второй сайт в индексе или безобидный лишний ход.

Зачем отдельный инструмент. «www отдаёт 200» само по себе не дефект: если
страница объявляет canonical на основной хост, поисковик знает правильный адрес,
и остаётся лишний ход. Дубль возникает, когда зеркало называет каноническим
СЕБЯ и разрешает индексацию — тогда у одного содержимого два сайта, и вес
делится между ними. Разница существенная, и мера серьёзности здесь ровно та же,
что в `http-redirect-audit.py`.

Поэтому дубль определяется тремя признаками вместе: код 200, canonical на сам
www-хост, индексация не закрыта. Любой один из трёх отсутствует — это не дубль,
и так и печатается.

Отсутствие DNS у `www.<домен>` — НЕ дефект: зеркала не существует, чинить
нечего. Таймаут — «не измерено», а не «исправно»: на перегруженной витрине
первый замер этого инструмента уже один раз дал таймаут и показал три дубля
вместо четырёх.

Ничего не меняет: только читает живые витрины и реестр. Домены берутся ТОЛЬКО
из реестра ячеек — придумывать адреса запрещено.

    python3 automation/local/www-mirror-audit.py
    python3 automation/local/www-mirror-audit.py --timeout 120
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

РЕЕСТР = Path(__file__).resolve().parents[2] / "config" / "site-cells.json"

_КАНОН = re.compile(r"""<link[^>]+rel=["']canonical["'][^>]*>""", re.I)
_ROBOTS = re.compile(r"""<meta[^>]+name=["']robots["'][^>]*>""", re.I)
_HREF = re.compile(r"""href=["']([^"']+)["']""", re.I)
_CONTENT = re.compile(r"""content=["']([^"']+)["']""", re.I)

ДУБЛЬ = "ДУБЛЬ"
ЛИШНИЙ_ХОД = "лишний ход"
ПЕРЕНАПРАВЛЯЕТ = "перенаправляет"
ЗАКРЫТ_ОТ_ИНДЕКСА = "закрыт от индекса"
ЗЕРКАЛА_НЕТ = "зеркала нет"
НЕ_ИЗМЕРЕНО = "не измерено"


class _БезРедиректа(urllib.request.HTTPRedirectHandler):
    """Редирект — это ответ, который надо увидеть, а не пройти насквозь."""

    def redirect_request(self, *арг, **кв):
        return None


#: Служебные имена стендов: домена в сети у них нет и быть не должно.
СТЕНДОВЫЕ = (".localhost", ".localhost.test")


def живые_домены(реестр: Path) -> list[str]:
    """Домены, чьё имя РАЗРЕШАЕТСЯ, а не те, чья ячейка вынута.

    Поле `status` описывает состояние ячейки: `1lordserials1.online` и
    `lordserial33.biz` стоят `not_extracted`, потому что ячейка не вынута, — но
    домены отдают страницы посетителю. Отбор по `status == "live"` пропускал
    обе, и приёмка молчала о двух витринах из семнадцати, выглядя полной.
    """
    д = json.loads(реестр.read_text(encoding="utf-8"))
    ячейки = д.get("cells") or д
    берём: list[str] = []
    for запись in ячейки:
        домен = str(запись.get("domain") or "").strip()
        if not домен or any(домен.endswith(х) for х in СТЕНДОВЫЕ):
            continue
        try:
            socket.gethostbyname(домен)
        except OSError:
            continue
        берём.append(домен)
    return sorted(set(берём))


def _значение(разметка: str, образец: re.Pattern, поле: re.Pattern) -> str:
    м = образец.search(разметка)
    if not м:
        return ""
    з = поле.search(м.group(0))
    return з.group(1) if з else ""


def судить(хост: str, код: int, разметка: str) -> tuple[str, str]:
    """Статус зеркала и довод. Три признака дубля проверяются вместе."""
    if код in (301, 302, 303, 307, 308):
        return ПЕРЕНАПРАВЛЯЕТ, ""
    канон = _значение(разметка, _КАНОН, _HREF)
    режим = _значение(разметка, _ROBOTS, _CONTENT)
    if "noindex" in режим.lower():
        return ЗАКРЫТ_ОТ_ИНДЕКСА, f"robots={режим}"
    # Сравнение по хосту, а не по подстроке всего адреса: canonical
    # `https://example.com/` не должен считаться «своим» для `www.example.com`.
    свой = канон.split("//")[-1].split("/")[0].lower() == хост.lower()
    if код == 200 and свой:
        return ДУБЛЬ, f"canonical={канон or '—'} robots={режим or '—'}"
    if код == 200:
        return ЛИШНИЙ_ХОД, f"canonical={канон or '—'} robots={режим or '—'}"
    return НЕ_ИЗМЕРЕНО, f"код {код}"


def снять(хост: str, предел: float) -> tuple[str, str]:
    try:
        socket.gethostbyname(хост)
    except OSError:
        return ЗЕРКАЛА_НЕТ, "DNS нет — зеркала не существует, чинить нечего"
    контекст = ssl.create_default_context()
    контекст.check_hostname = False
    контекст.verify_mode = ssl.CERT_NONE
    открыть = urllib.request.build_opener(
        _БезРедиректа, urllib.request.HTTPSHandler(context=контекст))
    запрос = urllib.request.Request(f"https://{хост}/",
                                    headers={"User-Agent": "factory-www-audit"})
    try:
        ответ = открыть.open(запрос, timeout=предел)
        return судить(хост, ответ.status,
                      ответ.read(300_000).decode("utf-8", "replace"))
    except urllib.error.HTTPError as сбой:
        куда = сбой.headers.get("Location", "")
        статус, довод = судить(хост, сбой.code, "")
        return статус, (f"→ {куда}" if куда else довод)
    except Exception as сбой:
        # Таймаут и сетевой отказ — факт о замере, а не о витрине. Первый
        # замер 12.10 из-за таймаута насчитал три дубля вместо четырёх.
        return НЕ_ИЗМЕРЕНО, f"{type(сбой).__name__}: {str(сбой)[:70]}"


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--registry", type=Path, default=РЕЕСТР)
    р.add_argument("--timeout", type=float, default=60.0)
    р.add_argument("--domain", default="", help="проверить один домен")
    опции = р.parse_args(аргв)

    домены = живые_домены(опции.registry)
    if опции.domain:
        домены = [д for д in домены if д == опции.domain]
        if not домены:
            print(f"домена {опции.domain} нет среди живых в реестре",
                  file=sys.stderr)
            return 2

    дубли: list[str] = []
    лишние: list[str] = []
    неизмеренные: list[str] = []
    print(f"живых доменов в реестре: {len(домены)}\n")
    for домен in домены:
        хост = f"www.{домен}"
        статус, довод = снять(хост, опции.timeout)
        метка = {ДУБЛЬ: "[!!]", ЛИШНИЙ_ХОД: "[! ]",
                 НЕ_ИЗМЕРЕНО: "[? ]"}.get(статус, "[ок]")
        print(f"   {метка} {хост:34s} {статус:18s} {довод}")
        if статус == ДУБЛЬ:
            дубли.append(хост)
        elif статус == ЛИШНИЙ_ХОД:
            лишние.append(хост)
        elif статус == НЕ_ИЗМЕРЕНО:
            неизмеренные.append(хост)

    print(f"\nдублей (200 + canonical на себя + индексация): {len(дубли)}")
    for х in дубли:
        print(f"   {х}")
    print(f"лишних ходов (200, но canonical на основной хост): {len(лишние)}")
    for х in лишние:
        print(f"   {х}")
    if неизмеренные:
        print(f"НЕ ИЗМЕРЕНО: {len(неизмеренные)} — это факт о замере, а не о "
              "витрине; повторите с большим --timeout")
        for х in неизмеренные:
            print(f"   {х}")

    if неизмеренные:
        return 2
    return 1 if дубли else 0


if __name__ == "__main__":
    raise SystemExit(главное())
