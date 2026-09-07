"""Единая запись сайта: всё, что известно о витрине, и откуда это известно.

Центр управления собирается вокруг одной мысли: **у каждого показателя есть
источник и время**. Показатель без источника нельзя ни проверить, ни объяснить,
а показатель без времени через сутки неотличим от свежего.

Отсюда устройство записи. Значение не лежит голым числом — оно приходит вместе
с состоянием, источником и отметкой времени. Шесть состояний, и каждое написано
на конкретный способ соврать:

`CONNECTED`      — источник отвечает, значение получено.
`NOT_CONNECTED`  — источник не подключён. Не «ноль посетителей», а «мы не
                   спрашивали»: ноль здесь означал бы, что сайт никто не открыл.
`NO_DATA`        — источник подключён и ответил, что данных нет.
`STALE`          — значение получено, но давно; порог объявляется, а не
                   подразумевается.
`ACCESS_BLOCKED` — доступ закрыт правами. Отличается от `ERROR` тем, что чинится
                   решением владельца, а не исправлением кода.
`ERROR`          — источник ответил отказом. Причина называется.

Ядро не ходит в сеть и ничего не измеряет само. Измерения складывает сборщик в
`var/state/fleet-observations/<site>.json`; здесь они только читаются и
сопоставляются с объявленным. Такое разделение нужно, чтобы экран флота
открывался за миллисекунды и не зависел от того, отвечает ли сейчас чужой
счётчик.

Секретов в записи нет и быть не может. Идентификаторы — счётчика, плеера,
партнёрские — это не секреты, и они показываются; значения ключей не читаются
даже для проверки существования: проверяется наличие ссылки на хранилище.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

ВЕРСИЯ = "fleet-registry/1.0.0"

#: Файл с описанием источников. Настройка, а не код: ядру не положено знать
#: имена конкретных витрин и способов их обслуживания.
ИСТОЧНИКИ = "config/fleet-sources.yaml"

#: Куда сборщик кладёт измерения.
НАБЛЮДЕНИЯ = "var/state/fleet-observations"

#: После какого возраста измерение считается несвежим, если источник не сказал
#: иначе. Двенадцать часов: обновление каталога ходит каждые десять минут, и
#: значение старше половины суток означает, что сборщик молчит, а не что данные
#: не менялись.
ПРОСРОЧКА_СЕК = 12 * 3600


class State(str, Enum):
    CONNECTED = "CONNECTED"
    NOT_CONNECTED = "NOT_CONNECTED"
    NO_DATA = "NO_DATA"
    STALE = "STALE"
    ACCESS_BLOCKED = "ACCESS_BLOCKED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Наблюдение:
    """Значение вместе с тем, откуда и когда оно взято."""

    value: Any = None
    state: State = State.NOT_CONNECTED
    source: str = ""
    observed_at: str = ""
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "state": self.state.value,
            "source": self.source,
            "observedAt": self.observed_at,
            "reason": self.reason,
        }


def известно(value: Any, source: str, observed_at: str = "") -> Наблюдение:
    """Значение из объявленного источника — конфигурации или манифеста."""
    if value is None or value == "":
        return Наблюдение(None, State.NO_DATA, source, observed_at,
                          "источник прочитан, значения в нём нет")
    return Наблюдение(value, State.CONNECTED, source, observed_at)


def не_подключено(source: str, reason: str = "") -> Наблюдение:
    return Наблюдение(None, State.NOT_CONNECTED, source, "",
                      reason or "источник не подключён")


def отказ(source: str, reason: str) -> Наблюдение:
    return Наблюдение(None, State.ERROR, source, "", reason)


def закрыто(source: str, reason: str) -> Наблюдение:
    return Наблюдение(None, State.ACCESS_BLOCKED, source, "", reason)


@dataclass
class SiteRecord:
    site_id: str
    fields: dict[str, Наблюдение] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "siteId": self.site_id,
            "registryVersion": ВЕРСИЯ,
            "fields": {и: н.as_dict() for и, н in self.fields.items()},
        }

    def значение(self, имя: str) -> Any:
        н = self.fields.get(имя)
        return н.value if н else None


def _читать_json(путь: Path) -> tuple[dict | None, str]:
    try:
        return json.loads(путь.read_text(encoding="utf-8")), ""
    except FileNotFoundError:
        return None, f"файла нет: {путь.name}"
    except (OSError, ValueError) as ошибка:
        return None, f"{путь.name} не читается: {ошибка}"


def _читать_yaml(путь: Path) -> tuple[dict | None, str]:
    import yaml

    try:
        return yaml.safe_load(путь.read_text(encoding="utf-8")) or {}, ""
    except FileNotFoundError:
        return None, f"файла нет: {путь.name}"
    except (OSError, yaml.YAMLError) as ошибка:
        return None, f"{путь.name} не читается: {ошибка}"


def настройка(root: Path | str) -> dict[str, Any]:
    данные, беда = _читать_yaml(Path(root) / ИСТОЧНИКИ)
    return данные if данные is not None else {"error": беда}


def _возраст(отметка: str) -> float | None:
    """Сколько секунд назад сделано измерение. None — отметка непонятна."""
    if not отметка:
        return None
    try:
        разобрано = time.strptime(отметка.replace("Z", "").split(".")[0], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    return max(0.0, time.time() - time.mktime(разобрано) + time.timezone)


def _из_наблюдений(данные: dict, имя: str, *, просрочка: float) -> Наблюдение:
    сырое = (данные.get(имя) or {}) if isinstance(данные, dict) else {}
    if not isinstance(сырое, dict) or "state" not in сырое:
        return не_подключено(f"observations:{имя}")
    состояние = str(сырое.get("state") or "")
    try:
        разобранное = State(состояние)
    except ValueError:
        return отказ(f"observations:{имя}", f"неизвестное состояние {состояние!r}")
    отметка = str(сырое.get("observedAt") or "")
    возраст = _возраст(отметка)
    if разобранное is State.CONNECTED and возраст is not None and возраст > просрочка:
        часов = возраст / 3600
        return Наблюдение(сырое.get("value"), State.STALE,
                          str(сырое.get("source") or f"observations:{имя}"), отметка,
                          f"измерению {часов:.1f} ч, порог {просрочка / 3600:.0f} ч")
    return Наблюдение(сырое.get("value"), разобранное,
                      str(сырое.get("source") or f"observations:{имя}"), отметка,
                      str(сырое.get("reason") or ""))


# --- сборка записи ----------------------------------------------------------

#: Ссылки на секреты показываются как факт наличия, а не значением. Поле,
#: оканчивающееся на `_secret_ref`, — это адрес в хранилище; читать по нему
#: нельзя и не нужно: центр управления показывает, настроен ли доступ, а не сам
#: доступ.
СЕКРЕТНЫЙ_ХВОСТ = "_secret_ref"


def _профиль(root: Path, site_id: str) -> tuple[dict | None, str, str]:
    путь = Path(root) / "config" / "site-profiles" / f"{site_id}.json"
    данные, беда = _читать_json(путь)
    return данные, f"site-profile:{site_id}", беда


def _пакет(root: Path, site_id: str) -> tuple[dict | None, str, str]:
    путь = Path(root) / "sites" / site_id / "package.yaml"
    данные, беда = _читать_yaml(путь)
    return данные, f"site-package:{site_id}", беда


def _манифест_релиза(root: Path, site_id: str, настройки: dict) -> tuple[dict | None, str, str]:
    корень_рантайма = str((настройки.get("runtime") or {}).get("root") or "")
    if not корень_рантайма:
        return None, "release-manifest", "корень рантайма не объявлен в настройке"
    рантайм = Path(корень_рантайма) / site_id
    ссылка = рантайм / "current"
    имя = str((настройки.get("runtime") or {}).get("manifest") or "release-manifest.json")
    if not рантайм.exists():
        # Витрина не развёрнута в этом рантайме — это не отказ, а факт. Отказ
        # означал бы «что-то сломалось» и увёл бы внимание туда, где всё в
        # порядке: сайт просто ещё не выкладывался.
        return None, f"runtime:{site_id}", "НЕ_РАЗВЁРНУТА"
    try:
        цель = ссылка.resolve(strict=True)
    except OSError as ошибка:
        return None, f"release-manifest:{site_id}", f"текущий релиз недоступен: {ошибка}"
    данные, беда = _читать_json(цель / имя)
    return данные, f"release-manifest:{цель.name}", беда


def _наблюдения(root: Path, site_id: str) -> dict:
    данные, _ = _читать_json(Path(root) / НАБЛЮДЕНИЯ / f"{site_id}.json")
    return данные or {}


def _идентификаторы(пакет: dict) -> dict[str, Наблюдение]:
    """Идентификаторы витрины: счётчики, плеер, партнёры.

    Показываются, потому что это не секреты: по номеру счётчика ничего нельзя
    сделать, а без него нельзя понять, куда уходит статистика. Ссылки на
    секреты рядом показываются одним признаком «настроено», без значения.
    """
    из: dict[str, Наблюдение] = {}
    аналитика = пакет.get("analytics_profile") or пакет.get("analytics") or {}
    if isinstance(аналитика, dict):
        for имя in ("counter_id", "metrika_counter_id", "ga_measurement_id"):
            if имя in аналитика:
                из[f"analytics.{имя}"] = известно(аналитика.get(имя), "site-package:analytics")
    плеер = пакет.get("vk_video") or пакет.get("player") or {}
    if isinstance(плеер, dict):
        for имя in ("player_id", "publisher_id", "adapter"):
            if имя in плеер:
                из[f"player.{имя}"] = известно(плеер.get(имя), "site-package:player")
    реклама = пакет.get("advertising") or {}
    if isinstance(реклама, dict):
        for имя in ("provider", "partner_id"):
            if имя in реклама:
                из[f"advertising.{имя}"] = известно(реклама.get(имя), "site-package:advertising")
    return из


def _ссылки_на_секреты(пакет: dict) -> Наблюдение:
    найдено: list[str] = []

    def обойти(узел, префикс=""):
        if isinstance(узел, dict):
            for ключ, значение in узел.items():
                путь = f"{префикс}.{ключ}" if префикс else str(ключ)
                if str(ключ).endswith(СЕКРЕТНЫЙ_ХВОСТ) and значение:
                    найдено.append(путь)
                else:
                    обойти(значение, путь)
        elif isinstance(узел, list):
            for н, значение in enumerate(узел):
                обойти(значение, f"{префикс}[{н}]")

    обойти(пакет)
    if not найдено:
        return не_подключено("site-package:secrets", "ссылок на секреты в пакете нет")
    # Значения не читаются: показывается, что доступ настроен, а не сам доступ.
    return известно(sorted(найдено), "site-package:secrets")


def site_record(root: Path | str, site_id: str, *, настройки: dict | None = None) -> SiteRecord:
    """Единая запись сайта. Ничего не измеряет — только читает и сопоставляет."""
    корень = Path(root)
    настройки = настройки if настройки is not None else настройка(корень)
    просрочка = float((настройки.get("staleness") or {}).get("seconds") or ПРОСРОЧКА_СЕК)

    запись = SiteRecord(site_id=site_id)
    профиль, источник_профиля, беда_профиля = _профиль(корень, site_id)
    пакет, источник_пакета, беда_пакета = _пакет(корень, site_id)
    манифест, источник_манифеста, беда_манифеста = _манифест_релиза(корень, site_id, настройки)
    наблюдения = _наблюдения(корень, site_id)

    if профиль is None:
        запись.fields["profile"] = отказ(источник_профиля, беда_профиля)
        профиль = {}
    if пакет is None:
        запись.fields["package"] = отказ(источник_пакета, беда_пакета)
        пакет = {}

    запись.fields["tenantId"] = известно(site_id, источник_профиля)
    запись.fields["name"] = известно(
        (профиль.get("brand") or {}).get("name") or пакет.get("brand", {}).get("name"),
        источник_профиля)
    домены = list(профиль.get("domains") or [])
    if пакет.get("domain") and пакет["domain"] not in домены:
        домены.append(пакет["domain"])
    запись.fields["domains"] = известно(sorted(домены) or None, источник_профиля)
    запись.fields["environment"] = известно(пакет.get("environment"), источник_пакета)
    запись.fields["productionAuthorized"] = известно(
        пакет.get("production_authorized"), источник_пакета)
    запись.fields["templateFamily"] = известно(пакет.get("theme_ref"), источник_пакета)
    запись.fields["contentSource"] = известно(
        (пакет.get("content_source") or {}).get("kind"), источник_пакета)
    запись.fields["contentPackageRef"] = известно(
        пакет.get("content_package_ref"), источник_пакета)
    запись.fields["seoIndexingEnabled"] = известно(
        пакет.get("seo_indexing_enabled"), источник_пакета)
    from factory.site_engine.fleet_accounts import ПРИЗНАК as ПРИЗНАК_РЕГИСТРАЦИИ

    запись.fields["publicRegistration"] = известно(
        bool(профиль.get(ПРИЗНАК_РЕГИСТРАЦИИ)), источник_профиля)
    запись.fields["adminAdapter"] = известно(
        пакет.get("cms_contract") or профиль.get("cms_contract"), источник_пакета)

    if манифест is None:
        не_развёрнута = беда_манифеста == "НЕ_РАЗВЁРНУТА"
        for имя in ("currentRelease", "templateDigest", "rendererRevision",
                    "toolingRevision", "contentSnapshotId", "contentCount",
                    "rollbackTarget"):
            запись.fields[имя] = (
                не_подключено(источник_манифеста, "витрина не развёрнута")
                if не_развёрнута else отказ(источник_манифеста, беда_манифеста))
        запись.fields["deployment"] = известно(
            "NOT_DEPLOYED" if не_развёрнута else "UNKNOWN", источник_манифеста)
    else:
        запись.fields["currentRelease"] = известно(
            источник_манифеста.split(":", 1)[-1], источник_манифеста,
            str(манифест.get("created_at") or ""))
        для_полей = {
            "templateDigest": "template_digest",
            "rendererRevision": "renderer_revision",
            "toolingRevision": "tooling_revision",
            "contentSnapshotId": "content_snapshot_id",
            "contentCount": "content_count",
            "rollbackTarget": "rollback_target",
            "releaseReason": "release_reason",
        }
        for наружу, внутри in для_полей.items():
            запись.fields[наружу] = известно(манифест.get(внутри), источник_манифеста,
                                             str(манифест.get("created_at") or ""))
        запись.fields["deployment"] = известно("DEPLOYED", источник_манифеста)

    # Есть ли у выложенного релиза серверный поиск. Проверяется по самому
    # релизу, а не по объявлению: витрина могла быть собрана шаблоном, который
    # поиска не умеет, и объявление говорило бы одно, а страница отвечала бы
    # другое.
    запись.fields["serverSearch"] = _указатель_поиска(корень, site_id, настройки)

    запись.fields.update(_идентификаторы(пакет))
    запись.fields["secretRefs"] = _ссылки_на_секреты(пакет)

    # Измеренное: здоровье, свежесть, посещаемость, индексация. Каждое поле
    # приходит из сборщика вместе со своим состоянием.
    for имя in ("health", "freshnessSeconds", "lastSuccessfulRefresh", "visitors",
                "visits", "pageviews", "playerStarts", "playableShare", "errors4xx",
                "errors5xx", "emptySearchQueries", "indexedPages", "sitemapState",
                "robotsState", "canonicalState", "seoVisibility", "iks",
                "coreWebVitals", "analyticsConnector"):
        запись.fields[имя] = _из_наблюдений(наблюдения, имя, просрочка=просрочка)

    запись.fields["lastSyncAt"] = известно(
        str(наблюдения.get("collectedAt") or ""), "observations")
    return запись


def _витрины(root: Path) -> list[str]:
    каталог = Path(root) / "config" / "site-profiles"
    if not каталог.is_dir():
        return []
    return sorted(п.stem for п in каталог.glob("*.json"))


def fleet(root: Path | str) -> dict[str, Any]:
    """Весь флот одной выборкой: строка на витрину плюс сводка по состояниям."""
    корень = Path(root)
    настройки = настройка(корень)
    записи = [site_record(корень, с, настройки=настройки) for с in _витрины(корень)]
    сводка: dict[str, int] = {}
    for запись in записи:
        for наблюдение in запись.fields.values():
            сводка[наблюдение.state.value] = сводка.get(наблюдение.state.value, 0) + 1
    return {
        "registryVersion": ВЕРСИЯ,
        "sites": [з.as_dict() for з in записи],
        "total": len(записи),
        "stateCounts": сводка,
        "configError": настройки.get("error", ""),
    }


def _указатель_поиска(root: Path, site_id: str, настройки: dict) -> Наблюдение:
    """Указатель поиска выложенного релиза: есть, сколько записей, какого размера.

    Читается заголовок файла, а не весь файл: указатель весит десятки мегабайт,
    и разбирать его целиком ради одного числа значило бы делать экран флота
    зависимым от размера каталога.
    """
    корень_рантайма = str((настройки.get("runtime") or {}).get("root") or "")
    if not корень_рантайма:
        return не_подключено("release:search-index", "корень рантайма не объявлен")
    путь = Path(корень_рантайма) / site_id / "current" / "search-index.json"
    try:
        размер = путь.stat().st_size
    except OSError:
        return не_подключено(
            "release:search-index",
            "в выложенном релизе серверного поиска нет")
    try:
        with open(путь, encoding="utf-8") as ф:
            начало = ф.read(400)
    except OSError as ошибка:
        return отказ("release:search-index", f"указатель не читается: {ошибка}")
    записей = None
    метка = '"size":'
    если_есть = начало.find(метка)
    if если_есть >= 0:
        хвост = начало[если_есть + len(метка):].strip()
        число = ""
        for символ in хвост:
            if символ.isdigit():
                число += символ
            else:
                break
        записей = int(число) if число else None
    return известно(
        {"records": записей, "megabytes": round(размер / 1e6, 1)},
        "release:search-index")
