"""Сверка фактического портфеля с объявленным.

Источник истины — inventory, но проверяется он production'ом, а не наоборот.
Домен, отвечающий в сети и отсутствующий в реестре, — это не «мелочь в
документации»: он либо чей-то забытый сайт, либо наш, за которым никто не
следит. И то и другое надо назвать.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
from typing import Any

#: Роли записей. Перечень закрыт: «прочее» превращает классификацию в свалку.
РОЛИ = ("MANAGED_PRODUCTION", "ONBOARDING", "REDIRECT_ONLY",
        "REFERENCE_SOURCE", "RETIRED", "UNKNOWN")

#: Семейства шаблонов и сегменты, которые они обслуживают.
СЕГМЕНТ_СЕМЕЙСТВА = {"lords": "FILMS_SERIES", "zona": "FILMS_SERIES",
                     "yummy": "ANIME", "animedia": "ANIME"}


def _хосты_allowlist(корень: pathlib.Path) -> list[str]:
    текст = (корень / "inventory/network-allowlist.yaml").read_text(encoding="utf-8")
    return re.findall(r"^\s+host:\s*(\S+)", текст, re.M)


def _reference(корень: pathlib.Path) -> set[str]:
    п = корень / "inventory/reference-sources.yaml"
    if not п.exists():
        return set()
    текст = п.read_text(encoding="utf-8")
    # Источники объявлены адресом (`url:`), а не хостом: реестр описывает,
    # что именно разрешено смотреть, а не куда разрешено ходить.
    из = set()
    for кусок in текст.split("- ref:"):
        if "read_only: true" not in кусок:
            continue
        for адрес in re.findall(r"^\s+url:\s*(\S+)", кусок, re.M):
            из.add(адрес.split("//", 1)[-1].split("/", 1)[0])
    return из


def _реестр_аналитики(корень: pathlib.Path) -> dict[str, dict]:
    """Домены с заведённым счётчиком. Счётчик — признак управляемой витрины:
    его заводят тогда, когда за сайт кто-то отвечает."""
    п = корень / "config/analytics.json"
    if not п.exists():
        return {}
    д = json.loads(п.read_text(encoding="utf-8"))
    return {с["domain"]: с for с in д.get("properties", [])}


def _профили(корень: pathlib.Path) -> dict[str, dict]:
    из = {}
    каталог = корень / "config/site-profiles"
    if not каталог.exists():
        return из
    for f in sorted(каталог.glob("*.json")):
        д = json.loads(f.read_text(encoding="utf-8"))
        for домен in д.get("domains", []):
            из[домен] = д
    return из


def _ответ(домен: str) -> dict[str, Any]:
    r = subprocess.run(
        ["curl", "-sSI", "-m", "20", f"https://{домен}/"],
        capture_output=True, text=True)
    коды = re.findall(r"HTTP/[\d.]+ (\d+)", r.stdout)
    место = re.findall(r"(?im)^location:\s*(\S+)", r.stdout)
    семейство = ""
    if коды and коды[-1] == "200":
        тело = subprocess.run(["curl", "-sSL", "-m", 25 and "25",
                               f"https://{домен}/"], capture_output=True, text=True).stdout
        м = re.search(r'data-template-family="([^"]*)"', тело)
        семейство = м.group(1) if м else ""
    return {"http": int(коды[-1]) if коды else 0,
            "redirect_to": место[0] if место else "",
            "template_family": семейство}


def свести(корень: pathlib.Path, домены: list[str]) -> dict[str, Any]:
    allow = set(_хосты_allowlist(корень))
    reference = _reference(корень)
    профили = _профили(корень)
    аналитика = _реестр_аналитики(корень)
    записи: dict[str, dict[str, Any]] = {}
    for д in sorted(set(домены) | allow | reference):
        if д.endswith(("yandex.net", "yandex.ru", "yandex.com")) or "api" in д:
            continue          # служебные адреса, не витрины
        ф = _ответ(д)
        профиль = профили.get(д)
        if д in reference:
            роль = "REFERENCE_SOURCE"
        elif ф["redirect_to"]:
            роль = "REDIRECT_ONLY"
        elif профиль is not None or д in аналитика:
            # Профиль в git либо запись в реестре аналитики со счётчиком.
            # Профиль Zona ведёт соседняя сессия и он ещё не закоммичен, но
            # счётчик у витрины заведён и работает — витрина управляемая.
            роль = "MANAGED_PRODUCTION"
        elif ф["http"] == 200 and д in allow:
            # Отвечает, объявлен в allowlist, но профиля нет: витрина в работе
            # у другого потока. Менять её нельзя, потерять из виду — тоже.
            роль = "ONBOARDING"
        elif ф["http"] == 200:
            роль = "UNKNOWN"
        else:
            роль = "RETIRED" if ф["http"] in (0, 410) else "UNKNOWN"
        записи[д] = {
            "domain": д, "role": роль, "http": ф["http"],
            "redirect_to": ф["redirect_to"],
            "template_family": ф["template_family"],
            "segment": СЕГМЕНТ_СЕМЕЙСТВА.get(ф["template_family"], "UNKNOWN"),
            "in_allowlist": д in allow,
            "has_profile": профиль is not None,
            "site_id": ((профиль or {}).get("site_id")
                        or (аналитика.get(д) or {}).get("site_id") or ""),
            "metrika_counter": (аналитика.get(д) or {}).get("counter_id"),
            "mutations_allowed": роль == "MANAGED_PRODUCTION",
        }
    return записи


def разница(сегодня: dict[str, dict], вчера: dict[str, dict] | None) -> dict[str, Any]:
    вчера = вчера or {}
    добавлены = sorted(set(сегодня) - set(вчера))
    удалены = sorted(set(вчера) - set(сегодня))
    изменения = []
    for д in sorted(set(сегодня) & set(вчера)):
        for поле in ("role", "http", "redirect_to", "template_family"):
            if сегодня[д].get(поле) != вчера[д].get(поле):
                изменения.append({"domain": д, "field": поле,
                                  "was": вчера[д].get(поле),
                                  "now": сегодня[д].get(поле)})
    # Поля читаются мягко: вчерашний снимок мог быть собран прежней версией
    # цикла, и сравнение обязано это пережить. Падающее сравнение не покажет
    # ни одного расхождения — оно покажет ошибку.
    в_проде_без_реестра = sorted(
        д for д, з in сегодня.items()
        if з.get("http") in (200, 301, 302) and not з.get("in_allowlist"))
    в_реестре_без_прода = sorted(
        д for д, з in сегодня.items()
        if з.get("in_allowlist") and з.get("http") == 0)
    return {"added": добавлены, "removed": удалены, "changed": изменения,
            "in_production_not_in_inventory": в_проде_без_реестра,
            "in_inventory_not_in_production": в_реестре_без_прода,
            "redirect_targets": sorted(
                {з.get("redirect_to") for з in сегодня.values()
                 if з.get("redirect_to")})}
