"""Единственный источник истины о том, какие домены открыты для индексации.

До этого модуля решение жило в трёх независимых местах: в коде посредника, в
непрослеживаемом файле профиля на хосте и в compose-файле ветки, которой нет в
`main`. Совпадали они случайно, и обычный deploy закрывал живую витрину.

Здесь решение одно: версионируемый профиль сайта. Всё остальное —
``X-Robots-Tag``, мета-тег, ``robots.txt``, доступность карты сайта, ворота
релиза и сверка дрейфа — производится из него, а не принимается заново.

Правила, которые модуль обязан удержать, и причина каждого.

1. **Неизвестный хост закрыт.** Разрешение выдаётся поимённо. Умолчание
   «наверное, можно» однажды открыло бы домен, которого никто не проверял.
2. **Новый домен закрыт.** Профиль создаётся со значением ``closed``; открытие —
   отдельное изменение именно его профиля.
3. **Семейство не открывает.** Ни ``profile_family``, ни любое групповое
   значение не может открыть домен: иначе добавление сайта в семейство молча
   открывало бы его.
4. **Окружение не подменяет решение.** Переменная среды может только сузить
   разрешение. Открыть то, что закрыто профилем, она не может — ровно этот
   путь и привёл к тому, что глобальный флаг открывал всё семейство сразу.
5. **Wildcard запрещён.** Маска в имени домена означает разрешение для того,
   чего ещё нет.
6. **Дубликат блокирует сборку.** Два профиля на один домен — два разных
   решения, и молча выбирать из них нельзя.
7. **Окружения не смешиваются.** Production не читает staging и demo.
8. **Домен нормализуется до сравнения.** Регистр, завершающая точка и
   ``www`` — это тот же домен; расхождение в написании не должно создавать
   второй, никем не решённый.
"""

from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

OPEN = "open"
CLOSED = "closed"

#: Поля, без которых профиль не является решением.
REQUIRED_FIELDS = (
    "schema_version",
    "site_id",
    "canonical_domain",
    "environment",
    "profile_family",
    "profile_version",
)
REQUIRED_SEO_FIELDS = ("indexing_expected", "indexing_reason")

ALLOWED_EXPECTED = (OPEN, CLOSED)
ALLOWED_ENVIRONMENTS = ("production", "staging", "demo")

_WILDCARD = re.compile(r"[*?]")
_DOMAIN_OK = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


class PolicyError(RuntimeError):
    """Политику нельзя собрать. Deploy обязан остановиться до любых изменений."""


def normalize_domain(value: str) -> str:
    """Привести домен к одному написанию.

    Регистр, завершающая точка и ``www`` — это тот же сайт. Без нормализации
    ``WWW.Yummyani.Site.`` стал бы четвёртым доменом, про который никто не
    принимал решения, и попал бы под правило «неизвестный закрыт» — то есть
    закрыл бы живую витрину на ровном месте.
    """
    домен = (value or "").strip().lower().rstrip(".")
    if домен.startswith("www."):
        домен = домен[4:]
    with contextlib.suppress(UnicodeError, UnicodeDecodeError):
        домен = домен.encode("idna").decode("ascii")
    return домен


@dataclass(frozen=True)
class DomainDecision:
    domain: str
    site_id: str
    expected: str
    reason: str
    environment: str
    family: str
    profile_version: str
    canonical_domain: str
    aliases: tuple[str, ...] = ()

    @property
    def open(self) -> bool:
        return self.expected == OPEN


@dataclass
class IndexingPolicy:
    """Скомпилированная политика: решение по каждому известному домену."""

    decisions: dict[str, DomainDecision] = field(default_factory=dict)
    source_environment: str = "production"

    def decide(self, host: str) -> DomainDecision | None:
        """Решение по хосту запроса. ``None`` означает «домен неизвестен»."""
        return self.decisions.get(normalize_domain(host))

    def is_open(self, host: str) -> bool:
        """Открыт ли домен. Неизвестный хост закрыт — это и есть правило 1."""
        решение = self.decide(host)
        return bool(решение and решение.open)

    @property
    def open_domains(self) -> tuple[str, ...]:
        return tuple(sorted(d for d, r in self.decisions.items() if r.open))

    @property
    def closed_domains(self) -> tuple[str, ...]:
        return tuple(sorted(d for d, r in self.decisions.items() if not r.open))

    def matrix(self) -> dict:
        return {
            "open": list(self.open_domains),
            "closed": list(self.closed_domains),
            "open_count": len(self.open_domains),
            "closed_count": len(self.closed_domains),
        }


def _validate(profile: dict, path: Path) -> None:
    for поле in REQUIRED_FIELDS:
        if поле not in profile or profile[поле] in (None, ""):
            raise PolicyError(f"{path.name}: нет обязательного поля {поле}")
    seo = profile.get("seo_profile")
    if not isinstance(seo, dict):
        raise PolicyError(f"{path.name}: нет блока seo_profile")
    for поле in REQUIRED_SEO_FIELDS:
        if поле not in seo or seo[поле] in (None, ""):
            raise PolicyError(f"{path.name}: нет обязательного поля seo_profile.{поле}")
    if seo["indexing_expected"] not in ALLOWED_EXPECTED:
        raise PolicyError(
            f"{path.name}: indexing_expected={seo['indexing_expected']!r}, "
            f"допустимо только {ALLOWED_EXPECTED}"
        )
    if profile["environment"] not in ALLOWED_ENVIRONMENTS:
        raise PolicyError(
            f"{path.name}: environment={profile['environment']!r}, "
            f"допустимо только {ALLOWED_ENVIRONMENTS}"
        )
    домены = profile.get("domains")
    if not isinstance(домены, list) or not домены:
        raise PolicyError(f"{path.name}: список domains пуст")
    for домен in домены:
        if _WILDCARD.search(str(домен)):
            raise PolicyError(
                f"{path.name}: маска в домене {домен!r}. Разрешение выдаётся "
                "поимённо: маска открыла бы то, чего ещё нет"
            )
        if not _DOMAIN_OK.match(normalize_domain(str(домен))):
            raise PolicyError(f"{path.name}: домен {домен!r} не похож на имя хоста")


def load_profiles(directory: Path, *, environment: str = "production") -> list[dict]:
    """Прочитать профили нужного окружения. Повреждённый файл останавливает всё."""
    if not directory.is_dir():
        raise PolicyError(f"каталог профилей не найден: {directory}")
    профили = []
    for путь in sorted(directory.glob("*.json")):
        текст = путь.read_text(encoding="utf-8")
        if not текст.strip():
            raise PolicyError(f"{путь.name}: профиль пуст")
        try:
            профиль = json.loads(текст)
        except ValueError as ошибка:
            raise PolicyError(f"{путь.name}: профиль не разбирается — {ошибка}") from ошибка
        _validate(профиль, путь)
        if профиль["environment"] != environment:
            # Правило 7: production не читает staging и demo. Профиль не
            # ошибочен — он просто не про это окружение.
            continue
        профили.append(профиль)
    if not профили:
        raise PolicyError(
            f"в {directory} нет ни одного профиля окружения {environment!r}"
        )
    return профили


def compile_policy(
    directory: Path,
    *,
    environment: str = "production",
    expected_domains: set[str] | None = None,
) -> IndexingPolicy:
    """Собрать политику. Любое сомнение — исключение, а не тихое умолчание.

    ``expected_domains`` — инвентарь доменов, которые обслуживает production.
    Известный домен без профиля останавливает сборку: это правило 1 из задания,
    и сработать оно обязано до того, как что-нибудь изменится.
    """
    policy = IndexingPolicy(source_environment=environment)
    видели: dict[str, str] = {}

    for профиль in load_profiles(directory, environment=environment):
        site_id = профиль["site_id"]
        canonical = normalize_domain(профиль["canonical_domain"])
        seo = профиль["seo_profile"]
        домены = [normalize_domain(d) for d in профиль["domains"]]
        if canonical not in домены:
            raise PolicyError(
                f"{site_id}: canonical_domain={canonical} отсутствует в domains={домены}"
            )
        for домен in домены:
            if домен in видели:
                raise PolicyError(
                    f"домен {домен} объявлен дважды: {видели[домен]} и {site_id}. "
                    "Два профиля — два решения, выбирать из них молча нельзя"
                )
            видели[домен] = site_id
            policy.decisions[домен] = DomainDecision(
                domain=домен,
                site_id=site_id,
                expected=seo["indexing_expected"],
                reason=seo["indexing_reason"],
                environment=профиль["environment"],
                family=профиль["profile_family"],
                profile_version=str(профиль["profile_version"]),
                canonical_domain=canonical,
                aliases=(f"www.{домен}",),
            )

    if expected_domains:
        нет_профиля = {normalize_domain(d) for d in expected_domains} - set(policy.decisions)
        if нет_профиля:
            raise PolicyError(
                "известные production-домены без профиля: "
                + ", ".join(sorted(нет_профиля))
                + ". Deploy остановлен до изменений"
            )
    return policy


def apply_environment_override(
    policy: IndexingPolicy, *, closes: set[str] | None = None
) -> IndexingPolicy:
    """Окружение может только сузить разрешение.

    Открыть закрытое профилем окружение не может: именно так глобальный флаг
    однажды открыл бы всё семейство общего рендерера. Сузить — может: аварийное
    закрытие не должно ждать правки файла.
    """
    if not closes:
        return policy
    сужено = IndexingPolicy(source_environment=policy.source_environment)
    for домен, решение in policy.decisions.items():
        if домен in {normalize_domain(d) for d in closes} and решение.open:
            решение = DomainDecision(
                **{**решение.__dict__, "expected": CLOSED,
                   "reason": f"закрыто окружением поверх профиля: {решение.reason}"}
            )
        сужено.decisions[домен] = решение
    return сужено
