"""Контракт подключения Yummy к фабрике: сторона потребителя.

Что это и чего это не заменяет
------------------------------

Приложение Yummy живёт в отдельном репозитории `sbc-create/yummyani` и в эту
фабрику не перенесено — так объявлено в `inventory/portfolios.yaml`, и менять
это решение полоса шаблонов не вправе. Здесь описано ровно то, что нужно
фабрике **от приложения**, чтобы витрину можно было собрать, показать и
выложить теми же командами, что и остальные.

Ни одной строки приложения сюда не копируется, и ни один его файл отсюда не
правится. Контракт — это перечень требований и проверка их выполнения, а не
подмена чужого кода.

Почему контракт нужен именно сейчас
-----------------------------------

Пока его нет, Yummy остаётся нулём по всем измерениям готовности, и ноль этот
ничего не сообщает: неизвестно, чего не хватает, кому это принадлежит и что
изменится, когда препятствие снимут. Контракт превращает «неизвестно» в
перечень с владельцами.

Что установлено чтением приложения
----------------------------------

* витрина выбирается переменной `SITE_PROFILE`, значение обязано быть из
  `SITE_PROFILE_IDS`; неизвестное значение — фатальная ошибка, пустое в
  production — тоже. Это верное устройство: неверный профиль отдал бы
  канонические адреса одной витрины под доменом другой;
* сборка, проверка типов, линтер и тесты объявлены сценариями `package.json`:
  `build`, `typecheck`, `lint`, `test`, `verify`;
* хранилище — Prisma, и клиент требует генерации (`db:generate`) до сборки;
* домены подтверждены кодом: `yummyani.me`, `yummyani.site`, `yummyani.org`,
  `yummyani.biz`.

Чего не хватает и кому это принадлежит — в `missing_inputs()`.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

#: Версия контракта, под которую написано потребление.
CONTRACT_VERSION = "yummy-app/1.0.0"

#: Канонический путь рабочей копии приложения. Читается только на чтение:
#: ветка там принадлежит другому потоку, и полоса шаблонов её не трогает.
APP_REPO = Path("/srv/sites/yummyani-staging/repo")

#: Домены направления. Подтверждены кодом приложения, а не памятью: замена
#: `yummyani.*` на `yummyanime.*` производилась бы без единого основания.
DOMAINS = ("yummyani.me", "yummyani.site", "yummyani.org", "yummyani.biz")

#: Сценарии, без которых витрину нельзя ни собрать, ни проверить.
REQUIRED_SCRIPTS = ("build", "typecheck", "lint", "test", "db:generate")

#: Переменная, выбирающая витрину. Обязательна в production.
PROFILE_ENV = "SITE_PROFILE"


@dataclass(frozen=True)
class Requirement:
    """Одно требование контракта и его состояние."""

    key: str
    what: str
    owner: str
    satisfied: bool
    detail: str = ""


@dataclass(frozen=True)
class Assessment:
    """Состояние подключения. Отдельно — исследование, контракт и препятствия."""

    requirements: tuple[Requirement, ...] = field(default_factory=tuple)

    @property
    def satisfied(self) -> tuple[Requirement, ...]:
        return tuple(r for r in self.requirements if r.satisfied)

    @property
    def blocked(self) -> tuple[Requirement, ...]:
        return tuple(r for r in self.requirements if not r.satisfied)

    def as_dict(self) -> dict:
        return {
            "contract": CONTRACT_VERSION,
            "app_repo": str(APP_REPO),
            "domains": list(DOMAINS),
            "requirements": [
                {"key": r.key, "what": r.what, "owner": r.owner,
                 "satisfied": r.satisfied, "detail": r.detail}
                for r in self.requirements
            ],
            "satisfied": len(self.satisfied),
            "blocked": len(self.blocked),
        }


def _package_json() -> dict:
    path = APP_REPO / "package.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — нечитаемый манифест это тоже состояние
        return {}


def _watcher_declaration_is_current() -> tuple[bool, str]:
    """Совпадает ли декларация наблюдателя с его реализацией.

    Это и есть причина закрытых ворот сборки, названная в
    `TEMPLATE_TO_CORE-007`: реализация экспортирует две константы версий и
    принимает объекты в `source_types`, а декларация о них не знает. Проверка
    здесь чтением, а не сборкой: сборка чужого репозитория из этой полосы не
    запускается.
    """
    declaration = APP_REPO / "scripts" / "episode-watcher.d.mts"
    implementation = APP_REPO / "scripts" / "episode-watcher.mjs"
    if not declaration.is_file() or not implementation.is_file():
        return False, "файлов наблюдателя нет"
    text = declaration.read_text(encoding="utf-8")
    source = implementation.read_text(encoding="utf-8")
    missing = [
        name for name in ("PLAYBACK_FINGERPRINT_VERSION", "VOICES_FINGERPRINT_VERSION")
        if f"export const {name}" in source and name not in text
    ]
    narrow = bool(re.search(r"source_types\??:\s*string\[\]", text))
    if missing or narrow:
        parts = []
        if missing:
            parts.append("не объявлены: " + ", ".join(missing))
        if narrow:
            parts.append("source_types сужен до string[]")
        return False, "; ".join(parts)
    return True, "декларация совпадает с реализацией"


def assess() -> Assessment:
    """Состояние подключения — из фактов, а не из памяти."""
    package = _package_json()
    scripts = set((package.get("scripts") or {}).keys())
    profiles = APP_REPO / "src" / "site-profiles" / "index.ts"
    watcher_ok, watcher_detail = _watcher_declaration_is_current()
    node_modules = (APP_REPO / "node_modules").is_dir()

    return Assessment(requirements=(
        Requirement(
            "app_present", "рабочая копия приложения доступна на чтение", "CORE",
            APP_REPO.is_dir(), str(APP_REPO)),
        Requirement(
            "scripts", "объявлены сценарии сборки, типов, линтера и тестов", "CORE",
            set(REQUIRED_SCRIPTS) <= scripts,
            "нет: " + ", ".join(sorted(set(REQUIRED_SCRIPTS) - scripts))
            if not set(REQUIRED_SCRIPTS) <= scripts else ", ".join(sorted(REQUIRED_SCRIPTS))),
        Requirement(
            "profile_contract", f"витрина выбирается переменной {PROFILE_ENV}", "CORE",
            profiles.is_file() and PROFILE_ENV in profiles.read_text(encoding="utf-8"),
            str(profiles.relative_to(APP_REPO)) if profiles.is_file() else "профилей нет"),
        Requirement(
            "build_gate", "декларация наблюдателя совпадает с реализацией", "CORE",
            watcher_ok, watcher_detail),
        Requirement(
            "dependencies", "зависимости установлены и клиент хранилища сгенерирован",
            "CORE / OPS", node_modules,
            "node_modules на месте" if node_modules else "node_modules нет"),
        Requirement(
            "working_branch", "названа ветка, в которой полоса шаблонов вправе работать",
            "CORE", False,
            "рабочая копия занята активной веткой другого потока"),
        Requirement(
            "domains", "боевые домены закреплены за витринами владельцем", "владелец",
            False, "домены известны из кода, но привязка витрин не объявлена"),
        Requirement(
            "package", "пакет витрины заведён в фабрике", "TEMPLATES после снятия выше",
            False, "создание пакета требует домена, прав и секретов — их выдаёт владелец"),
    ))


def missing_inputs() -> list[dict]:
    """Чего не хватает, в форме запроса недостающих входов.

    Форма та же, что у `factory/input_request.py`: поле, зачем оно, в каком
    виде, куда положить и что оно блокирует. Пример намеренно без секрета —
    значение секрета не попадает ни в запрос, ни в отчёт.
    """
    return [
        {
            "field": "yummy.working_branch",
            "why": ("Рабочая копия занята активной веткой другого потока. Две полосы в "
                    "одной ветке стирают правки друг друга молча."),
            "format": "имя ветки в репозитории sbc-create/yummyani",
            "example_without_secret": "claude/templates-yummy-integration-01",
            "where_to_put": "coordination/v1/status/core.json → ownership",
            "blocks": "любую работу полосы шаблонов в приложении Yummy",
        },
        {
            "field": "yummy.build_gate",
            "why": ("Декларация наблюдателя отстала от реализации, и проверка типов "
                    "останавливает сборку. Слой наблюдателя полосе шаблонов не "
                    "принадлежит."),
            "format": "правка scripts/episode-watcher.d.mts",
            "example_without_secret": ("export const PLAYBACK_FINGERPRINT_VERSION: number; "
                                       "source_types?: (string | {code: string; label: string})[]"),
            "where_to_put": "репозиторий приложения",
            "blocks": "сборку, а значит и предпросмотр витрины",
        },
        {
            "field": "yummy.domain_binding",
            "why": ("Домены известны из кода, но какая витрина живёт на каком домене — "
                    "решение владельца. Догадка здесь означала бы канонические адреса "
                    "одной витрины под доменом другой."),
            "format": "соответствие SITE_PROFILE → домен",
            "example_without_secret": "site → yummyani.me, org → yummyani.org",
            "where_to_put": "sites/<siteId>/package.yaml и inventory/portfolios.yaml",
            "blocks": "создание пакета витрины и любую приёмку",
        },
    ]


def profile_ids() -> list[str]:
    """Идентификаторы витрин приложения. Читаются, а не перечисляются здесь.

    Берётся объявление `SITE_PROFILES`, а не любые ключи файла: первая
    редакция искала пары «имя: {» по всему тексту и возвращала `editorial`,
    `jsonLd` и `openGraph` — вложенные поля описания витрины, а не витрины.
    Список, собранный неверно, хуже отсутствующего: по нему нельзя ни собрать,
    ни проверить.
    """
    path = APP_REPO / "src" / "site-profiles" / "profiles.ts"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    block = re.search(r"export const SITE_PROFILES[^{]*\{(.*?)\n\};", text, re.S)
    if not block:
        return []
    return sorted(set(re.findall(r"^\s+(\w+):", block.group(1), re.M)))


def environment_for(profile: str) -> dict:
    """Переменные окружения для сборки одной витрины.

    Секретов здесь нет и быть не может: `DATABASE_URL` и токены живут в области
    секретов и передаются окружением процесса, а не этим словарём. Здесь только
    то, что определяет **какую** витрину собирают.
    """
    if profile and profile not in profile_ids() and profile_ids():
        raise ValueError(f"неизвестная витрина Yummy: {profile!r}")
    return {PROFILE_ENV: profile, "APP_ENV": os.environ.get("APP_ENV", "staging")}


__all__ = [
    "APP_REPO", "Assessment", "CONTRACT_VERSION", "DOMAINS", "PROFILE_ENV",
    "REQUIRED_SCRIPTS", "Requirement", "assess", "environment_for",
    "missing_inputs", "profile_ids",
]
