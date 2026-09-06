"""Протокол запуска Control API.

Один и тот же порядок проверок выполняется при обычном старте службы, при
выкладке и при откате. Отдельного облегчённого входа «для теста» здесь нет
намеренно: путь, которым поднимается откат, обязан быть тем же, которым
поднимается рабочая версия, иначе откат проверяет не то, что потом работает.

Проверки делятся на два рода, и различие существеннее, чем кажется:

* **Фатальные** — служба не может делать свою работу вообще: нет профилей,
  включена запись без токенов, каталог состояния недоступен. Такое лучше
  показать отказом запуска, чем поднять службу, которая на каждый запрос
  отвечает ошибкой.
* **Ограничивающие** — не в порядке отдельная витрина. Служба поднимается,
  витрина помечается неуправляемой. Останавливать весь массив из-за одного
  испорченного профиля значит превращать местную поломку в общую — ровно то,
  против чего построена изоляция.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from factory.site_engine.api import compat

# Версии схемы профиля, которые движок умеет читать. Профиль с иной версией —
# это не «немного другой формат», а другой контракт: ворота миграции.
SUPPORTED_PROFILE_SCHEMA = ("1.0",)

FATAL = "fatal"
DEGRADED = "degraded"
OK = "ok"


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""
    facts: dict[str, Any] = field(default_factory=dict)


@dataclass
class StartupReport:
    checks: list[Check] = field(default_factory=list)

    @property
    def fatal(self) -> list[Check]:
        return [c for c in self.checks if c.status == FATAL]

    @property
    def degraded(self) -> list[Check]:
        return [c for c in self.checks if c.status == DEGRADED]

    @property
    def ok(self) -> bool:
        return not self.fatal

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [
                {"name": c.name, "status": c.status, "detail": c.detail, "facts": c.facts}
                for c in self.checks
            ],
            "fatal": len(self.fatal),
            "degraded": len(self.degraded),
        }

    def as_text(self) -> str:
        знак = {OK: "PASS", DEGRADED: "WARN", FATAL: "FAIL"}
        строки = [f"{знак.get(c.status, '?'):4} {c.name}: {c.detail}" for c in self.checks]
        строки.append(f"итог: {'готов' if self.ok else 'ЗАПУСК НЕВОЗМОЖЕН'}, "
                      f"фатальных {len(self.fatal)}, ограничений {len(self.degraded)}")
        return "\n".join(строки)


def _profiles_dir(root: Path) -> Path:
    return root / "config" / "site-profiles"


def check_profiles(root: Path) -> list[Check]:
    """Профили читаются и соответствуют поддерживаемой версии схемы."""
    directory = _profiles_dir(root)
    if not directory.is_dir():
        return [Check("profiles", FATAL, f"нет каталога профилей {directory}")]
    файлы = sorted(directory.glob("*.json"))
    if not файлы:
        return [Check("profiles", FATAL, "профилей витрин нет: обслуживать нечего")]

    нечитаемые: list[str] = []
    чужая_схема: list[str] = []
    for путь in файлы:
        try:
            данные = json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            нечитаемые.append(путь.stem)
            continue
        if not isinstance(данные, dict):
            нечитаемые.append(путь.stem)
            continue
        версия = str(данные.get("schema_version", ""))
        if версия and версия not in SUPPORTED_PROFILE_SCHEMA:
            чужая_схема.append(f"{путь.stem}={версия}")

    проверки = [Check("profiles", OK, f"профилей: {len(файлы)}",
                      {"count": len(файлы)})]
    if нечитаемые:
        проверки.append(Check(
            "profiles.readable", DEGRADED,
            f"не прочитаны: {', '.join(нечитаемые)}; эти витрины не управляются",
            {"unreadable": нечитаемые}))
    if чужая_схема:
        # Ворота миграции: версия схемы профиля вне поддерживаемых означает, что
        # движок прочитает поля не так, как задумывал автор профиля.
        проверки.append(Check(
            "profiles.schema_version", DEGRADED,
            f"версия схемы вне поддерживаемых {SUPPORTED_PROFILE_SCHEMA}: "
            f"{', '.join(чужая_схема)}",
            {"unsupported": чужая_схема}))
    return проверки


def check_config_writable(root: Path) -> list[Check]:
    """Можно ли менять настройки витрин.

    Каталог профилей бывает намеренно закрыт на запись: настройки витрин —
    чувствительная конфигурация, и на боевом хосте ею владеет не та учётная
    запись, под которой работает служба. Это не повод не подниматься: чтение,
    задания и инвалидация кэша не требуют записи. Но знать об этом надо
    заранее, а не в момент, когда оператор нажал «Применить».
    """
    directory = _profiles_dir(root)
    if not directory.is_dir():
        return []
    проба = directory / ".startup-write-probe"
    try:
        проба.write_text("", encoding="utf-8")
        проба.unlink()
    except OSError as exc:
        return [Check("config.writable", DEGRADED,
                      f"профили доступны только для чтения ({exc.strerror}); "
                      "изменение настроек через API будет отклоняться",
                      {"writable": False, "path": str(directory)})]
    return [Check("config.writable", OK, "профили доступны на запись",
                  {"writable": True})]


def check_contract_compatibility(root: Path) -> list[Check]:
    """Совместимость контракта CMS по каждой витрине."""
    directory = _profiles_dir(root)
    if not directory.is_dir():
        return []
    несовместимые: list[str] = []
    ограниченные: list[str] = []
    всего = 0
    for путь in sorted(directory.glob("*.json")):
        всего += 1
        try:
            данные = json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(данные, dict):
            continue
        состояние = compat.evaluate(данные)
        if состояние.state == compat.STATE_INCOMPATIBLE:
            несовместимые.append(путь.stem)
        elif состояние.state == compat.STATE_DEGRADED:
            ограниченные.append(путь.stem)
    проверки = [Check("contract", OK,
                      f"движок {compat.ENGINE_CONTRACT}, витрин {всего}, "
                      f"несовместимых {len(несовместимые)}",
                      {"engine": compat.ENGINE_CONTRACT, "incompatible": несовместимые,
                       "degraded": ограниченные})]
    if несовместимые:
        проверки.append(Check("contract.incompatible", DEGRADED,
                              f"не управляются: {', '.join(несовместимые)}"))
    return проверки


def check_seo_binding_sources(root: Path) -> list[Check]:
    """Есть ли чем отдавать связи из этого корня состояния.

    Проверка существует из-за конкретного случая, а не из осторожности. Код
    берётся из каталога релиза, а настройка и данные — из корня состояния, и
    это разные места. Релиз с маршрутами контракта, выложенный в корень без
    `config/seo-binding-sources.yaml`, поднимается полностью исправным:
    протокол запуска проходит, `/api/v1/ready` отвечает 200, маршрут связей
    отвечает 200 — и отдаёт пустой перечень по всем витринам.

    Выкладка, выглядящая успешной при неработающей возможности, — худший вид
    отказа: о нём узнают не в момент выкладки, а от потребителя и позже.
    Ограничение, а не фатальная ошибка: корень без витрин со связями — законное
    состояние, служба обязана в нём подниматься.
    """
    from factory.site_engine import seo_binding
    from factory.site_engine.api import seo_bindings

    if not seo_bindings.настройка_есть(root):
        # Перечни идентификаторов проверяются и здесь: они от настройки
        # источников не зависят. Ворота, останавливающиеся на первом
        # ограничении, заставляют чинить по одному и выкатывать трижды —
        # каждый раз узнавая о следующем уже после выкладки.
        return [Check("seo-bindings.sources", DEGRADED,
                      f"{seo_bindings.SOURCES_REF} нет: маршруты контракта "
                      f"{seo_binding.SCHEMA_VERSION} ответят пустым перечнем",
                      {"contract": seo_binding.SCHEMA_VERSION,
                       "configured": False})] + _перечни_идентификаторов()

    каталог = seo_bindings.каталог_витрин(root)
    витрины = каталог["sites"]
    отсутствуют: list[str] = []
    for витрина in витрины:
        try:
            описано = seo_bindings.описание(root, витрина["siteId"])
        except seo_bindings.BindingSourceUnknown:
            continue
        for поле in ("catalog", "routes"):
            значение = описано.get(поле)
            if значение and not (root / str(значение)).exists():
                отсутствуют.append(f"{витрина['siteId']}:{поле}")

    проверки = [Check("seo-bindings.sources", OK,
                      f"контракт {seo_binding.SCHEMA_VERSION}, витрин "
                      f"{len(витрины)}, недостающих входов {len(отсутствуют)}",
                      {"contract": seo_binding.SCHEMA_VERSION,
                       "sites": len(витрины), "missing": отсутствуют})]
    if отсутствуют:
        проверки.append(Check("seo-bindings.inputs", DEGRADED,
                              f"нет входных файлов: {', '.join(отсутствуют)}"))

    return проверки + _перечни_идентификаторов()


def _перечни_идентификаторов() -> list[Check]:
    """Перечни, без которых связи собираются, но ничего не значат.

    Оба устроены fail-closed: без настройки они пусты, и это верно —
    подставлять встроенный список значило бы молча раздать права, о которых
    эксплуатация не знает. Но пустой перечень тих: связи собираются, записи
    отдаются, и каждая приходит без внешних идентификаторов и без права
    обещать просмотр. Отказ, о котором никто не сказал, выглядит работой.
    """
    from factory.site_engine import seo_binding

    проверки: list[Check] = []
    if not seo_binding.ID_NAMESPACES:
        проверки.append(Check(
            "seo-bindings.namespaces", DEGRADED,
            f"{seo_binding.ID_NAMESPACES_REF} не прочитан: связи будут "
            "отдаваться без внешних идентификаторов"))
    if not seo_binding.PLAYBACK_AUTHORISED:
        проверки.append(Check(
            "seo-bindings.playback", DEGRADED,
            f"{seo_binding.PLAYBACK_POLICY_REF} не прочитан: ни одна запись "
            "не получит права обещать просмотр"))
    return проверки


def check_site_isolation(root: Path) -> list[Check]:
    """Витрины не делят между собой домены и базы данных.

    Две витрины на одном домене — это не «почти изоляция», а её отсутствие:
    запрос попадёт туда, куда решит прокси, и виноватого потом не найти.
    """
    directory = _profiles_dir(root)
    if not directory.is_dir():
        return []
    домены: dict[str, list[str]] = {}
    for путь in sorted(directory.glob("*.json")):
        try:
            данные = json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(данные, dict):
            continue
        for домен in данные.get("domains") or []:
            домены.setdefault(str(домен).lower(), []).append(путь.stem)
    столкновения = {д: s for д, s in домены.items() if len(s) > 1}
    if столкновения:
        описание = "; ".join(f"{д}: {', '.join(s)}" for д, s in sorted(столкновения.items()))
        return [Check("isolation.domains", FATAL,
                      f"домен занят несколькими витринами — {описание}",
                      {"collisions": столкновения})]
    return [Check("isolation.domains", OK,
                  f"доменов {len(домены)}, пересечений нет", {"domains": len(домены)})]


def check_secrets(env: dict[str, str]) -> list[Check]:
    """Наличие секретов без их раскрытия.

    Проверяется присутствие и разбираемость, но ни одно значение не попадает ни
    в отчёт, ни в журнал: отчёт о запуске читают в том числе там, где не должно
    быть секретов.
    """
    из_среды = str(env.get("SITE_ENGINE_CONTROL_TOKENS", "")).strip()
    запись_включена = str(env.get("SITE_ENGINE_CONTROL_WRITES", "")).strip().lower() in {
        "1", "true", "yes", "on"}
    if not из_среды:
        if запись_включена:
            return [Check("secrets.tokens", FATAL,
                          "запись включена, но токенов нет: служба принимала бы "
                          "изменяющие запросы, отвергая каждый")]
        return [Check("secrets.tokens", OK, "токенов нет, запись выключена")]
    try:
        from factory.site_engine.api.control import principals_from_env

        principals = principals_from_env(env)
    except ValueError as exc:
        return [Check("secrets.tokens", FATAL, f"перечень токенов не разобран: {exc}")]
    области = sorted({s for p in principals.values() for s in p.scopes})
    return [Check("secrets.tokens", OK,
                  f"токенов {len(principals)}, области: {', '.join(области) or 'нет'}",
                  {"tokens": len(principals), "scopes": области})]


def check_state_dirs(root: Path) -> list[Check]:
    """Каталоги состояния существуют и доступны на запись.

    Служба, поднявшаяся без доступа к очереди, отвечает 200 на здоровье и
    ошибкой на каждое задание. Лучше не подняться.
    """
    проверки = []
    for имя, путь in (
        ("queue", root / "queue" / "inbox"),
        ("state", root / "var" / "state"),
        ("audit", root / "var" / "audit"),
        ("locks", root / "var" / "locks"),
    ):
        try:
            путь.mkdir(parents=True, exist_ok=True)
            проба = путь / ".startup-probe"
            проба.write_text("", encoding="utf-8")
            проба.unlink()
        except OSError as exc:
            проверки.append(Check(f"state.{имя}", FATAL, f"{путь} недоступен на запись: {exc}"))
        else:
            проверки.append(Check(f"state.{имя}", OK, str(путь)))
    return проверки


def run(root: Path | str = ".", env: dict[str, str] | None = None) -> StartupReport:
    """Полный протокол. Порядок важен: сначала то, без чего остальное бессмысленно."""
    root = Path(root).resolve()
    env = env if env is not None else dict(os.environ)
    отчёт = StartupReport()
    отчёт.checks.extend(check_state_dirs(root))
    отчёт.checks.extend(check_profiles(root))
    отчёт.checks.extend(check_site_isolation(root))
    отчёт.checks.extend(check_config_writable(root))
    отчёт.checks.extend(check_contract_compatibility(root))
    отчёт.checks.extend(check_seo_binding_sources(root))
    отчёт.checks.extend(check_secrets(env))
    return отчёт
