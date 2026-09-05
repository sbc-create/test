"""Заявка на витрину: мастер и детерминированный сухой прогон.

Создание витрины до сих пор означало правку `sites/<id>/package.yaml` руками и
запуск конвейера по SSH. Пока это так, самообслуживание существует на бумаге:
пользователь не может ни завести витрину, ни узнать, чего для неё не хватает,
не получив доступ к машине.

Заявка отвечает на три вопроса до того, как что-либо создано: чего не хватает,
что будет затронуто и что произойдёт при откате. Требования берутся из той же
проверки, которая потом будет блокировать сборку, — второй список требований
разошёлся бы с первым и врал бы ровно в тот момент, когда на него полагаются.

Сухой прогон детерминирован. Два вызова на одних данных дают один и тот же
план: иначе «сравните и подтвердите» подтверждает не то, что выполнится.
Поэтому ни отметок времени, ни случайных значений в план не попадает — время
создания заявки берётся из самой заявки, а не из часов в момент показа.
"""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Домен принимается только в виде имени. Адрес со схемой и путём здесь
#: выглядит правдоподобно и ломается позже — на сборке canonical_url.
ДОМЕН = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")
ИДЕНТИФИКАТОР = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
ЦВЕТ = re.compile(r"^#[0-9a-fA-F]{6}$")
ПОЧТА = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
#: Схемы ссылок на хранилище секретов. Значение ключа аналитики в заявке не
#: хранится ни при каких ответах: попав сюда, оно разошлось бы по журналу, по
#: плану и по экрану одновременно.
ССЫЛКА = ("secret://", "vault://", "env:", "ref://")

СРЕДЫ = ("staging", "production")
ФОРМЫ_ХОСТА = ("non_www", "www")
ПРОФИЛИ_SEO = ("catalog_authority", "release_pulse", "editorial_guide")


#: Допустимые значения читаются из схемы пакета — той же, по которой пакет
#: потом проверяется. Свой список в коде мастера означал бы, что оператор
#: вводит значение, которое мастер принял, а проверка отвергла: ровно это и
#: происходило с темой оформления, источником и типами содержимого.
СХЕМА_ПАКЕТА = "schemas/site-package.schema.json"


def _схема(root: Path) -> dict[str, Any]:
    try:
        return json.loads((Path(root) / СХЕМА_ПАКЕТА).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def значения(root: Path, *путь: str) -> tuple[str, ...]:
    """Перечисление или набор ключей по пути в схеме. Пусто — значит не знаем."""
    узел: Any = _схема(root).get("properties") or {}
    for шаг in путь:
        if not isinstance(узел, dict):
            return ()
        узел = узел.get(шаг) if шаг in узел else (узел.get("properties") or {}).get(шаг)
        if узел is None:
            return ()
    if isinstance(узел, dict) and "enum" in узел:
        return tuple(str(v) for v in узел["enum"])
    if isinstance(узел, dict) and "properties" in узел:
        return tuple(sorted(узел["properties"]))
    return ()


class SiteRequestError(Exception):
    """Отказ мастера. Несёт код и поле, чтобы ответ был точным."""

    def __init__(self, code: str, message: str, *, field: str = "", status: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.status = status


@dataclass(frozen=True)
class Шаг:
    id: str
    title: str
    обязательные: tuple[str, ...]
    подсказка: str = ""


ШАГИ: tuple[Шаг, ...] = (
    Шаг("domain", "Домен", ("domain",), "Имя домена без схемы и пути."),
    Шаг("profile", "Профиль", ("environment", "targetRef", "seoProfile"),
        "Среда, площадка выкладки и профиль разделов."),
    Шаг("content", "Источник содержимого", ("contentSource", "contentTypes"),
        "Откуда берутся материалы и какого они рода."),
    Шаг("template", "Шаблон", ("themeRef",), "Оформление принадлежит потоку шаблонов."),
    Шаг("branding", "Оформление", ("brandName", "legalName", "primaryColor"),
        "Название, юридическое лицо и основной цвет."),
    Шаг("seo", "SEO", ("canonicalHostForm",), "Канонический вид адреса."),
    Шаг("analytics", "Аналитика и реклама", (),
        "Только ссылки на хранилище секретов. Значения ключей сюда не вводятся."),
    Шаг("legal", "Правовые требования", ("legalEntity", "contactEmail", "rightsConfirmed"),
        "Кто отвечает за содержимое и подтверждены ли права."),
)

ПО_ИМЕНИ = {ш.id: ш for ш in ШАГИ}


@dataclass
class Заявка:
    request_id: str
    site_id: str
    created_at: str
    created_by: str = ""
    answers: dict[str, dict[str, Any]] = field(default_factory=dict)
    state: str = "DRAFT"
    #: Отпечаток плана, который подтвердили. Хранится, чтобы выкладка шла по
    #: тому плану, который видел человек: изменились ответы — подтверждение
    #: недействительно, и это видно, а не подразумевается.
    approved_plan_hash: str = ""
    approved_by: str = ""
    job_id: str = ""

    @property
    def next_step(self) -> str | None:
        for шаг in ШАГИ:
            if шаг.id not in self.answers:
                return шаг.id
        return None

    @property
    def complete(self) -> bool:
        return self.next_step is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "siteId": self.site_id,
            "createdAt": self.created_at,
            "createdBy": self.created_by,
            "state": self.state,
            "approvedPlanHash": self.approved_plan_hash,
            "approvedBy": self.approved_by,
            "jobId": self.job_id,
            "answers": self.answers,
            "nextStep": self.next_step,
            "complete": self.complete,
            "steps": [
                {
                    "id": ш.id,
                    "title": ш.title,
                    "hint": ш.подсказка,
                    "required": list(ш.обязательные),
                    "done": ш.id in self.answers,
                }
                for ш in ШАГИ
            ],
        }


def _проверить_шаг(
    шаг: Шаг, ответы: dict[str, Any], *, занятые: set[str], root: Path
) -> dict[str, Any]:
    """Разбор ответов одного шага. Все нарушения не копятся: шаг небольшой, и
    первый точный отказ понятнее списка из одного пункта."""
    чистые: dict[str, Any] = {}
    for имя in шаг.обязательные:
        значение = str(ответы.get(имя) or "").strip()
        if not значение:
            raise SiteRequestError("missing_field", f"шаг «{шаг.title}»: нужно поле {имя}", field=имя)

    if шаг.id == "domain":
        домен = str(ответы.get("domain") or "").strip().lower()
        if not ДОМЕН.match(домен):
            raise SiteRequestError(
                "invalid_domain", "domain — имя домена без схемы и пути", field="domain"
            )
        if домен in занятые:
            raise SiteRequestError(
                "domain_taken", f"домен {домен} уже занят другой витриной",
                field="domain", status=409,
            )
        псевдонимы = [
            a.strip().lower() for a in str(ответы.get("aliases") or "").split(",") if a.strip()
        ]
        for a in псевдонимы:
            if not ДОМЕН.match(a):
                raise SiteRequestError("invalid_domain", f"псевдоним {a} не домен", field="aliases")
            if a == домен:
                raise SiteRequestError(
                    "invalid_domain", "основной домен не может быть своим псевдонимом",
                    field="aliases",
                )
            if a in занятые:
                raise SiteRequestError(
                    "domain_taken", f"псевдоним {a} уже занят", field="aliases", status=409
                )
        чистые = {"domain": домен, "aliases": псевдонимы}

    elif шаг.id == "profile":
        среда = str(ответы.get("environment")).strip()
        if среда not in СРЕДЫ:
            raise SiteRequestError(
                "invalid_environment", f"environment — одно из {', '.join(СРЕДЫ)}",
                field="environment",
            )
        профиль = str(ответы.get("seoProfile")).strip()
        if профиль not in ПРОФИЛИ_SEO:
            raise SiteRequestError(
                "invalid_seo_profile", f"seoProfile — одно из {', '.join(ПРОФИЛИ_SEO)}",
                field="seoProfile",
            )
        площадка = str(ответы.get("targetRef")).strip()
        if not ИДЕНТИФИКАТОР.match(площадка):
            raise SiteRequestError("invalid_target", "targetRef — идентификатор", field="targetRef")
        # Разрешение на production полем формы не выдаётся ни при каком ответе.
        # Это решение владельца, и место ему в отдельном подтверждении, а не в
        # галочке рядом с выбором темы.
        чистые = {"environment": среда, "seoProfile": профиль, "targetRef": площадка}

    elif шаг.id == "content":
        допустимые_источники = значения(root, "content_source", "kind")
        источник = str(ответы.get("contentSource")).strip()
        if допустимые_источники and источник not in допустимые_источники:
            raise SiteRequestError(
                "invalid_content_source",
                f"contentSource — одно из {', '.join(допустимые_источники)}",
                field="contentSource",
            )
        допустимые_типы = значения(root, "content_types")
        типы = [t.strip() for t in str(ответы.get("contentTypes") or "").split(",") if t.strip()]
        чужие = [t for t in типы if допустимые_типы and t not in допустимые_типы]
        if not типы or чужие:
            raise SiteRequestError(
                "invalid_content_types",
                f"contentTypes — из набора {', '.join(допустимые_типы)}",
                field="contentTypes",
            )
        чистые = {"contentSource": источник, "contentTypes": типы}

    elif шаг.id == "template":
        допустимые_темы = значения(root, "tenant", "theme")
        тема = str(ответы.get("themeRef")).strip()
        if допустимые_темы and тема not in допустимые_темы:
            raise SiteRequestError(
                "invalid_theme",
                f"themeRef — одно из {', '.join(допустимые_темы)}",
                field="themeRef",
            )
        чистые = {"themeRef": тема}

    elif шаг.id == "branding":
        цвет = str(ответы.get("primaryColor")).strip()
        if not ЦВЕТ.match(цвет):
            raise SiteRequestError(
                "invalid_color", "primaryColor — цвет вида #1f4fd8", field="primaryColor"
            )
        чистые = {
            "brandName": str(ответы.get("brandName")).strip(),
            "legalName": str(ответы.get("legalName")).strip(),
            "primaryColor": цвет.lower(),
        }

    elif шаг.id == "seo":
        форма = str(ответы.get("canonicalHostForm")).strip()
        if форма not in ФОРМЫ_ХОСТА:
            raise SiteRequestError(
                "invalid_host_form", f"canonicalHostForm — одно из {', '.join(ФОРМЫ_ХОСТА)}",
                field="canonicalHostForm",
            )
        чистые = {
            "canonicalHostForm": форма,
            "trailingSlash": bool(str(ответы.get("trailingSlash") or "").strip()),
        }

    elif шаг.id == "analytics":
        for имя in ("analyticsRef", "adsRef"):
            значение = str(ответы.get(имя) or "").strip()
            if значение and not значение.startswith(ССЫЛКА):
                raise SiteRequestError(
                    "value_instead_of_reference",
                    f"{имя} принимает только ссылку на хранилище "
                    f"({', '.join(ССЫЛКА)}), а не само значение",
                    field=имя,
                )
            чистые[имя] = значение

    elif шаг.id == "legal":
        почта = str(ответы.get("contactEmail")).strip()
        if not ПОЧТА.match(почта):
            raise SiteRequestError("invalid_email", "contactEmail — адрес почты", field="contactEmail")
        подтверждены = bool(str(ответы.get("rightsConfirmed") or "").strip())
        if not подтверждены:
            raise SiteRequestError(
                "rights_not_confirmed",
                "права на содержимое обязаны быть подтверждены до создания витрины",
                field="rightsConfirmed",
            )
        чистые = {
            "legalEntity": str(ответы.get("legalEntity")).strip(),
            "contactEmail": почта,
            "rightsConfirmed": True,
        }

    return чистые


class SiteRequestStore:
    """Заявки живут в состоянии службы, а не в дереве витрин.

    Черновик в `sites/` был бы неотличим от настоящего пакета: конвейер увидел
    бы недозаполненную заявку как готовую витрину.
    """

    def __init__(self, root: Path, subdir: str = "var/state/site-requests") -> None:
        self.dir = root / subdir
        self._root = root

    def _путь(self, request_id: str) -> Path:
        if not re.match(r"^[a-z0-9]{8,32}$", request_id):
            raise SiteRequestError("invalid_request", "негодный идентификатор заявки", status=400)
        return self.dir / f"{request_id}.json"

    def занятые_домены(self) -> set[str]:
        занятые: set[str] = set()
        профили = self._root / "config" / "site-profiles"
        for файл in sorted(профили.glob("*.json")) if профили.is_dir() else []:
            try:
                данные = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for домен in данные.get("domains") or []:
                занятые.add(str(домен).lower())
            канон = str(данные.get("canonical_host") or "").lower()
            if канон:
                занятые.add(канон)
        for заявка in self.list():
            # Откачённая заявка домен не держит. Иначе отменённая попытка
            # занимала бы имя навсегда, и повторить её было бы нельзя —
            # включая повтор после исправления ошибки в той же заявке.
            if заявка.state == "ROLLED_BACK":
                continue
            домен = (заявка.answers.get("domain") or {}).get("domain")
            if домен:
                занятые.add(str(домен).lower())
        return занятые

    def create(self, site_id: str, *, actor: str, now: str) -> Заявка:
        if not ИДЕНТИФИКАТОР.match(site_id):
            raise SiteRequestError("invalid_site_id", "siteId — строчные буквы, цифры и дефис",
                                   field="siteId", status=400)
        if (self._root / "config" / "site-profiles" / f"{site_id}.json").exists():
            raise SiteRequestError(
                "site_exists", f"витрина {site_id} уже существует", field="siteId", status=409
            )
        self.dir.mkdir(parents=True, exist_ok=True)
        заявка = Заявка(
            request_id=secrets.token_hex(8), site_id=site_id, created_at=now, created_by=actor
        )
        self._записать(заявка)
        return заявка

    def get(self, request_id: str) -> Заявка:
        путь = self._путь(request_id)
        if not путь.exists():
            raise SiteRequestError("not_found", "заявки нет", status=404)
        данные = json.loads(путь.read_text(encoding="utf-8"))
        return Заявка(
            request_id=данные["requestId"],
            site_id=данные["siteId"],
            created_at=данные["createdAt"],
            created_by=данные.get("createdBy", ""),
            answers=данные.get("answers") or {},
            state=данные.get("state", "DRAFT"),
            approved_plan_hash=данные.get("approvedPlanHash", ""),
            approved_by=данные.get("approvedBy", ""),
            job_id=данные.get("jobId", ""),
        )

    def list(self) -> list[Заявка]:
        if not self.dir.is_dir():
            return []
        итог = []
        for файл in sorted(self.dir.glob("*.json")):
            try:
                данные = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            итог.append(
                Заявка(
                    request_id=данные["requestId"],
                    site_id=данные["siteId"],
                    created_at=данные["createdAt"],
                    created_by=данные.get("createdBy", ""),
                    answers=данные.get("answers") or {},
                    state=данные.get("state", "DRAFT"),
                    approved_plan_hash=данные.get("approvedPlanHash", ""),
                    approved_by=данные.get("approvedBy", ""),
                    job_id=данные.get("jobId", ""),
                )
            )
        return итог

    def answer(self, request_id: str, step: str, ответы: dict[str, Any]) -> Заявка:
        заявка = self.get(request_id)
        шаг = ПО_ИМЕНИ.get(step)
        if шаг is None:
            raise SiteRequestError("unknown_step", f"шага {step} нет", field="step", status=400)
        # Шаги идут по порядку. Заполнение вразнобой давало бы «оформление
        # готово, домена нет» — состояние, из которого план построить нельзя,
        # а мастер выглядит пройденным.
        следующий = заявка.next_step
        порядок = [ш.id for ш in ШАГИ]
        новый = step not in заявка.answers
        if новый and следующий is not None and порядок.index(step) > порядок.index(следующий):
            raise SiteRequestError(
                "step_out_of_order",
                f"сначала шаг «{ПО_ИМЕНИ[следующий].title}» ({следующий})",
                field="step",
                status=409,
            )
        занятые = self.занятые_домены()
        свой = (заявка.answers.get("domain") or {}).get("domain")
        if свой:
            занятые.discard(str(свой).lower())
        заявка.answers[step] = _проверить_шаг(шаг, ответы, занятые=занятые, root=self._root)
        # Ответ изменился — подтверждение прошлого плана к новому не относится.
        # Перенести его значило бы выложить не то, что подтверждали.
        if заявка.state == "APPROVED":
            заявка.state = "DRAFT"
            заявка.approved_plan_hash = ""
            заявка.approved_by = ""
        self._записать(заявка)
        return заявка

    def save(self, заявка: Заявка) -> Заявка:
        """Сохранить заявку целиком. Нужна исполнению: состояние заявки меняется
        не только ответами, но и подтверждением, выкладкой и откатом."""
        self._записать(заявка)
        return заявка

    def _записать(self, заявка: Заявка) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        путь = self.dir / f"{заявка.request_id}.json"
        временный = путь.with_suffix(".json.tmp")
        временный.write_text(
            json.dumps(заявка.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        временный.replace(путь)
