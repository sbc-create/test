"""Единственный источник истины о том, какие домены открыты для индексации.

До этого модуля решение жило в трёх независимых местах: в коде посредника, в
непрослеживаемом файле профиля на хосте и в compose-файле ветки, которой нет в
`main`. Совпадали они случайно, и обычный deploy закрывал живую витрину.

Здесь решение одно, и — что важнее — оно не заводит в репозитории новых полей.
Всё нужное уже было:

* **перечень обслуживаемых доменов** — ``config/FLEET-REGISTRY.json``;
* **решение по сайту** — ``seo_profile.indexing_enabled`` в его профиле;
* **собственный домен** — ``seo_profile.canonical_host`` там же.

Добавлено ровно одно поле: ``seo_profile.indexing_reason``. Решение без
основания нельзя проверить на обзоре, а открытие домена — это то изменение,
которое обязано быть объяснено.

Первая редакция модуля требовала своих полей (``canonical_domain``,
``environment``, ``profile_family``, ``profile_version``) и своего каталога
профилей. Это было ошибкой дважды: схема ``site-profile.schema.json`` запрещает
лишние поля верхнего уровня — то есть ворота схемы падали, — и собственный
``canonical_domain`` рядом с существующим ``canonical_host`` создавал ровно ту
вторую запись истины, ради устранения которой всё и затевалось.

Правила, которые модуль обязан удержать, и причина каждого.

1. **Неизвестный хост закрыт.** Разрешение выдаётся поимённо. Умолчание
   «наверное, можно» однажды открыло бы домен, которого никто не проверял.
2. **Сайт флота без профиля закрыт.** Не ошибка сборки, а явное решение с
   основанием «профиля нет». Если такой домен сейчас открыт, разницу поймают
   ворота релиза и потребуют её назвать.
3. **Семейство не открывает.** Ни ``site_type``, ни любое групповое значение
   не может открыть домен: иначе добавление сайта в семейство молча открывало
   бы его.
4. **Окружение не подменяет решение.** Переменная среды может только сузить
   разрешение. Открыть то, что закрыто профилем, она не может — ровно этот
   путь и привёл к тому, что глобальный флаг открывал всё семейство сразу.
5. **Wildcard запрещён.** Маска в имени домена означает разрешение для того,
   чего ещё нет.
6. **Дубликат блокирует сборку.** Два профиля на один домен — два разных
   решения, и молча выбирать из них нельзя.
7. **Production — это флот.** Профиль, которого нет в реестре флота, в
   production-политику не попадает: так демонстрационный ``demo-books`` не
   может повлиять на боевые домены.
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

#: Реестр обслуживаемых сайтов — перечень доменов production.
FLEET_REGISTRY = Path("config") / "FLEET-REGISTRY.json"

#: Поля профиля, без которых решение не прочитать. Все они есть в схеме
#: ``schemas/site-engine/site-profile.schema.json`` и существовали до этого
#: модуля.
REQUIRED_FIELDS = ("schema_version", "site_id", "site_type", "domains", "seo_profile")

#: ``indexing_enabled`` — само решение, ``canonical_host`` — собственный домен
#: сайта, ``indexing_reason`` — основание решения.
REQUIRED_SEO_FIELDS = ("indexing_enabled", "canonical_host", "indexing_reason")

ALLOWED_ENVIRONMENTS = ("production", "demo")

_WILDCARD = re.compile(r"[*?]")
_DOMAIN_OK = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")

#: Основание для сайта флота, у которого профиля нет. Решения об открытии не
#: принимали — значит его нет, и это записывается явно.
NO_PROFILE_REASON = "профиля сайта нет: решения об открытии не принимали"


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


def load_fleet(path: Path) -> dict[str, str]:
    """Прочитать реестр флота: ``site_id`` → домен.

    Реестр — перечень того, что вообще обслуживается. Без него нельзя отличить
    «домена нет в политике, потому что решения нет» от «домена нет, потому что
    про него забыли».
    """
    if not path.is_file():
        raise PolicyError(f"реестр флота не найден: {path}")
    текст = path.read_text(encoding="utf-8")
    if not текст.strip():
        raise PolicyError(f"{path.name}: реестр флота пуст")
    try:
        данные = json.loads(текст)
    except ValueError as ошибка:
        raise PolicyError(f"{path.name}: реестр не разбирается — {ошибка}") from ошибка
    записи = данные.get("fleet")
    if not isinstance(записи, list) or not записи:
        raise PolicyError(f"{path.name}: в реестре нет списка fleet")
    флот: dict[str, str] = {}
    for запись in записи:
        site_id = запись.get("site_id")
        домен = normalize_domain(str(запись.get("domain") or ""))
        if not site_id or not домен:
            raise PolicyError(f"{path.name}: запись без site_id или domain: {запись!r}")
        if not _DOMAIN_OK.match(домен):
            raise PolicyError(f"{path.name}: домен {домен!r} не похож на имя хоста")
        if site_id in флот:
            raise PolicyError(f"{path.name}: сайт {site_id} объявлен дважды")
        флот[site_id] = домен
    return флот


def _validate(profile: dict, path: Path) -> None:
    for поле in REQUIRED_FIELDS:
        if поле not in profile or profile[поле] in (None, ""):
            raise PolicyError(f"{path.name}: нет обязательного поля {поле}")
    seo = profile.get("seo_profile")
    if not isinstance(seo, dict):
        raise PolicyError(f"{path.name}: нет блока seo_profile")
    for поле in REQUIRED_SEO_FIELDS:
        if поле not in seo or seo[поле] in (None, ""):
            if поле == "indexing_enabled" and seo.get(поле) is False:
                continue  # False — полноценное решение, а не пустое поле
            raise PolicyError(f"{path.name}: нет обязательного поля seo_profile.{поле}")
    if not isinstance(seo["indexing_enabled"], bool):
        raise PolicyError(
            f"{path.name}: seo_profile.indexing_enabled="
            f"{seo['indexing_enabled']!r}, допустимо только true или false"
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


def load_profiles(directory: Path) -> list[dict]:
    """Прочитать все профили каталога. Повреждённый файл останавливает всё."""
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
        профили.append(профиль)
    if not профили:
        raise PolicyError(f"в {directory} нет ни одного профиля")
    return профили


def _decision_from_profile(
    профиль: dict, *, environment: str, домен: str, фактический_домен: str
) -> DomainDecision:
    seo = профиль["seo_profile"]
    return DomainDecision(
        domain=домен,
        site_id=профиль["site_id"],
        expected=OPEN if seo["indexing_enabled"] else CLOSED,
        reason=seo["indexing_reason"],
        environment=environment,
        family=профиль["site_type"],
        profile_version=str(профиль["schema_version"]),
        canonical_domain=фактический_домен,
        aliases=(f"www.{домен}",),
    )


def compile_policy(
    directory: Path,
    *,
    environment: str = "production",
    fleet_path: Path | None = None,
    expected_domains: set[str] | None = None,
) -> IndexingPolicy:
    """Собрать политику. Любое сомнение — исключение, а не тихое умолчание.

    ``directory`` — каталог профилей сайтов. ``fleet_path`` — реестр флота;
    по умолчанию ``config/FLEET-REGISTRY.json`` рядом с каталогом профилей.

    Для ``environment="production"`` перечень доменов задаёт реестр флота:
    профиль, которого в реестре нет, в боевую политику не попадает (правило 7),
    а сайт реестра без профиля получает явное закрытое решение (правило 2).
    """
    if environment not in ALLOWED_ENVIRONMENTS:
        raise PolicyError(
            f"environment={environment!r}, допустимо только {ALLOWED_ENVIRONMENTS}"
        )
    если_рядом = directory.parent / FLEET_REGISTRY.name
    флот = load_fleet(fleet_path if fleet_path is not None else если_рядом)

    policy = IndexingPolicy(source_environment=environment)
    видели: dict[str, str] = {}
    профили = {p["site_id"]: p for p in load_profiles(directory)}

    # Production — это ровно флот (правило 7). Всё остальное окружение видит
    # только те профили, которых во флоте нет: так демонстрационный сайт не
    # может повлиять на боевые домены, а боевой — утечь в демонстрацию.
    участники = sorted(флот) if environment == "production" else sorted(set(профили) - set(флот))

    for site_id in участники:
        профиль = профили.get(site_id)
        if профиль is None:
            # Правило 2: сайт обслуживается, решения о нём не принимали.
            домен = флот[site_id]
            policy.decisions[домен] = DomainDecision(
                domain=домен,
                site_id=site_id,
                expected=CLOSED,
                reason=NO_PROFILE_REASON,
                environment=environment,
                family="",
                profile_version="",
                canonical_domain=домен,
                aliases=(f"www.{домен}",),
            )
            видели[домен] = site_id
            continue

        seo = профиль["seo_profile"]
        canonical = normalize_domain(seo["canonical_host"])
        домены = [normalize_domain(d) for d in профиль["domains"]]
        if canonical not in домены:
            raise PolicyError(
                f"{site_id}: canonical_host={canonical} отсутствует в domains={домены}"
            )
        if site_id in флот and флот[site_id] not in домены:
            raise PolicyError(
                f"{site_id}: реестр флота обслуживает {флот[site_id]}, "
                f"а профиль знает только {домены}"
            )
        for домен in домены:
            if домен in видели:
                raise PolicyError(
                    f"домен {домен} объявлен дважды: {видели[домен]} и {site_id}. "
                    "Два профиля — два решения, выбирать из них молча нельзя"
                )
            видели[домен] = site_id
            policy.decisions[домен] = _decision_from_profile(
                профиль, environment=environment, домен=домен, фактический_домен=canonical
            )

    if expected_domains:
        нет_решения = {normalize_domain(d) for d in expected_domains} - set(policy.decisions)
        if нет_решения:
            raise PolicyError(
                "обслуживаемые домены без решения: "
                + ", ".join(sorted(нет_решения))
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
