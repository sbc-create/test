"""Заведение сайта по этапам, с продолжением с места сбоя.

Этапы идут по порядку и записываются на диск после каждого:

    domain_validated → template_reserved → repo_ready → release_ready
      → server_staged → data_verified → sync_verified → seo_verified → live

Зачем состояние на диске. Заведение сайта — длинная цепочка, часть которой
обращается наружу. Прогон, оборванный на пятом шаге, обязан продолжиться с
пятого: повтор с первого либо расходует второй шаблон, либо заводит второй
проект, либо делает второй платный заказ. Именно поэтому повтор здесь дешёвый и
безопасный, а не запрещённый.

Чего этот модуль не делает намеренно: не переключает DNS, не выпускает
сертификаты и не публикует сайт. Проверка готовности и выполнение — разные
вещи, и смешать их значит переключить домен из репетиции.

Догадки по доменному имени запрещены. `animedia.space` не означает ни семейства,
ни профиля содержимого, ни сервера: их называет заказ.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.cell import ledger, registry, templates

SCHEMA_VERSION = "1.0"

#: Этапы заведения сайта. Порядок обязателен, и `repo_created` стоит до
#: `release_ready` не случайно: пока у сайта нет своего репозитория, собирать
#: и публиковать нечего — а собрать из монорепозитория означает выпустить
#: сайт, который потом нечем ни изменить, ни откатить.
STAGES = (
    "domain_validated",
    "site_id_assigned",
    "template_reserved",
    "repo_created",
    "repo_pushed",
    "ci_verified",
    "release_ready",
    "server_staged",
    "data_verified",
    "sync_verified",
    "seo_verified",
    "deployed",
    "publicly_accepted",
)

#: Этапы, которые нельзя объявить пройденными без доказательства извне:
#: у каждого из них есть внешний наблюдаемый признак (ответ GitHub, вывод CI,
#: код публичной страницы). Отметка без признака — это отчёт о непроверенном.
STAGES_REQUIRING_EVIDENCE = (
    "repo_created", "repo_pushed", "ci_verified", "deployed", "publicly_accepted",
)

PENDING = "pending"
DONE = "done"
FAILED = "failed"
BLOCKED = "blocked"
SKIPPED_NOT_RUN = "not_run"


class OnboardingError(RuntimeError):
    pass


class StageBlocked(OnboardingError):
    """Этап не может быть выполнен без входных данных или доступа."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Stage:
    name: str
    status: str = PENDING
    detail: dict[str, Any] = field(default_factory=dict)
    at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status,
                "detail": self.detail, "at": self.at}


@dataclass
class Order:
    """Заказ на новый сайт. Всё, чего в нём нет, — отсутствующий вход."""

    order_id: str
    site_id: str
    domain: str
    #: Семейство и профиль содержимого называет заказ. Вывести их из имени
    #: домена нельзя: это была бы догадка, оформленная как факт.
    family: str
    content_profile: str
    deploy_target: str
    modules: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    publisher_id_ref: str | None = None
    publisher_id: str | None = None

    def missing(self) -> list[str]:
        gaps = [name for name in
                ("order_id", "site_id", "domain", "family", "content_profile",
                 "deploy_target")
                if not getattr(self, name)]
        return gaps


@dataclass
class Progress:
    order_id: str
    site_id: str
    domain: str
    stages: list[Stage]
    created_at: str
    updated_at: str

    @property
    def by_name(self) -> dict[str, Stage]:
        return {s.name: s for s in self.stages}

    @property
    def next_stage(self) -> str | None:
        for stage in self.stages:
            if stage.status != DONE:
                return stage.name
        return None

    @property
    def complete(self) -> bool:
        return all(s.status == DONE for s in self.stages)

    def summary(self) -> dict[str, Any]:
        """Честная сводка: сделанное, несделанное и почему.

        Частичный провал не превращается в «готово» — ровно затем сводка и
        считается по фактическим статусам, а не по последнему этапу.
        """
        return {
            "order_id": self.order_id,
            "site_id": self.site_id,
            "domain": self.domain,
            "complete": self.complete,
            "next_stage": self.next_stage,
            "done": [s.name for s in self.stages if s.status == DONE],
            "failed": [s.name for s in self.stages if s.status == FAILED],
            "blocked": [s.name for s in self.stages if s.status == BLOCKED],
            "pending": [s.name for s in self.stages if s.status == PENDING],
            "updated_at": self.updated_at,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "order_id": self.order_id,
            "site_id": self.site_id,
            "domain": self.domain,
            "stages": [s.to_dict() for s in self.stages],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Progress:
        return cls(
            order_id=raw["order_id"], site_id=raw["site_id"], domain=raw["domain"],
            stages=[Stage(name=s["name"], status=s["status"],
                          detail=s.get("detail") or {}, at=s.get("at"))
                    for s in raw["stages"]],
            created_at=raw["created_at"], updated_at=raw["updated_at"],
        )


def progress_path(root: Path, order_id: str) -> Path:
    return root / f"{order_id}.json"


def start(order: Order, *, root: Path) -> Progress:
    """Начать или продолжить заказ. Повтор ничего не расходует."""
    gaps = order.missing()
    if gaps:
        raise StageBlocked(
            f"в заказе нет обязательных полей {gaps}; пустое поле — не повод "
            "подставить значение по умолчанию"
        )
    path = progress_path(root, order.order_id)
    existing = ledger.read(path, default=None)
    if existing is not None:
        return Progress.from_dict(existing)
    now = utc_now()
    progress = Progress(order_id=order.order_id, site_id=order.site_id,
                        domain=order.domain,
                        stages=[Stage(name=n) for n in STAGES],
                        created_at=now, updated_at=now)
    ledger.write(path, progress.to_dict())
    return progress


def record(progress: Progress, stage: str, status: str, detail: dict[str, Any],
           *, root: Path) -> Progress:
    if stage not in STAGES:
        raise OnboardingError(f"неизвестный этап: {stage}")
    found = progress.by_name[stage]
    found.status = status
    found.detail = detail
    found.at = utc_now()
    progress.updated_at = found.at
    ledger.write(progress_path(root, progress.order_id), progress.to_dict())
    return progress


@dataclass(frozen=True)
class DomainCheck:
    """Что именно проверено про домен.

    Разделено намеренно: наличие NS не означает ни правильной A/AAAA, ни
    готового HTTPS, а объединённый ответ «домен в порядке» скрывал бы ровно то
    место, где он не в порядке.
    """

    domain: str
    ns_present: bool
    address_matches_target: bool | None
    https_ready: bool | None
    observed: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None

    @property
    def ready_for_cutover(self) -> bool:
        return bool(self.ns_present and self.address_matches_target and self.https_ready)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "ns_present": self.ns_present,
            "address_matches_target": self.address_matches_target,
            "https_ready": self.https_ready,
            "ready_for_cutover": self.ready_for_cutover,
            "observed": dict(self.observed),
            "reason": self.reason,
        }


def validate_domain(order: Order, *,
                    probe: Callable[[str], dict[str, Any]] | None = None) -> DomainCheck:
    """Проверка домена без единой мутации.

    Непроверяемое здесь называется `None`, а не `False`: «не смотрели» и
    «смотрели, не работает» — разные вещи, и вторая блокирует выкат, а первая
    требует доступа.
    """
    if probe is None:
        return DomainCheck(
            domain=order.domain, ns_present=False, address_matches_target=None,
            https_ready=None,
            reason="проба DNS не передана: в изолированной среде выход наружу закрыт",
        )
    observed = probe(order.domain)
    return DomainCheck(
        domain=order.domain,
        ns_present=bool(observed.get("ns")),
        address_matches_target=observed.get("address_matches_target"),
        https_ready=observed.get("https_ready"),
        observed=observed,
    )


def run(order: Order, *, root: Path, steps: dict[str, Callable[[Order], dict[str, Any]]],
        dry_run: bool = False) -> Progress:
    """Пройти этапы по порядку, продолжая с первого незавершённого.

    `steps` задаёт исполнителей. Этап без исполнителя честно помечается
    `not_run` и останавливает продвижение: пропустить его и объявить сайт
    готовым нельзя.
    """
    progress = start(order, root=root)
    if dry_run:
        # Сухой прогон проверяет вход и показывает план, не обращаясь наружу и
        # ничего не расходуя.
        plan = [s.name for s in progress.stages if s.status != DONE]
        return record(progress, progress.next_stage or STAGES[-1], progress.by_name[
            progress.next_stage or STAGES[-1]].status,
            {"dry_run": True, "would_run": plan}, root=root)

    for stage in STAGES:
        current = progress.by_name[stage]
        if current.status == DONE:
            continue
        runner = steps.get(stage)
        if runner is None:
            record(progress, stage, SKIPPED_NOT_RUN,
                   {"reason": "исполнитель этапа не передан"}, root=root)
            break
        try:
            detail = runner(order)
        except StageBlocked as exc:
            record(progress, stage, BLOCKED, {"reason": str(exc)}, root=root)
            break
        except Exception as exc:
            record(progress, stage, FAILED,
                   {"reason": f"{type(exc).__name__}: {exc}"}, root=root)
            break
        record(progress, stage, DONE, detail, root=root)
    return progress


def reserve_template_step(order: Order, *, pool_path: Path | None = None) -> dict[str, Any]:
    """Этап резервирования. Повтор заказа шаблон не расходует."""
    reservation = templates.reserve(
        order_id=order.order_id, site_id=order.site_id, domain=order.domain,
        family=order.family, path=pool_path)
    return {"template_id": reservation.template_id, "status": reservation.status}


def register_cell_step(order: Order, *, repo_path: str, pins: dict[str, Any],
                       template_id: str, registry_path: Path | None = None,
                       publisher: dict[str, Any] | None = None) -> dict[str, Any]:
    cell = registry.Cell(
        site_id=order.site_id, domain=order.domain, aliases=order.aliases,
        repo={"kind": "local", "path": repo_path, "remote": None},
        template={"template_id": template_id, "order_id": order.order_id},
        pins=pins,
        deploy_target={"ref": order.deploy_target, "server": None},
        publisher=publisher or ({"provider": "cdnvideohub",
                                 "publisher_id_ref": order.publisher_id_ref}
                                if order.publisher_id_ref else {}),
        data={"database": "data/site.sqlite3", "media": "data/media"},
        status="staged",
    )
    registry.register(cell, path=registry_path, replace=True)
    return {"site_id": cell.site_id, "repo": repo_path, "template_id": template_id}


#: Пространство, в котором владелец разрешил заводить репозитории сайтов.
#: Расширять его по своей инициативе нельзя: чужое пространство — чужие права.
REPO_NAMESPACE = "sbc-create"


def repo_name_for(site_id: str, domain: str) -> str:
    """Имя репозитория сайта. Выводится из домена, а не придумывается.

    Устойчивость важнее красоты: имя должно получаться одинаковым при каждом
    повторе заказа, иначе повторный запуск заведёт второй проект на тот же сайт.
    """
    основа = domain.strip().lower().replace(".", "-")
    return f"site-{основа}"


def create_repo_step(order: Order, *, namespace: str = REPO_NAMESPACE,
                     runner: Callable[[list[str]], tuple[int, str]] | None = None,
                     ) -> dict[str, Any]:
    """Создать приватный репозиторий сайта — ровно один на сайт.

    Идемпотентность здесь не украшение. Повторный запуск onboarding — штатное
    событие: прогон обрывается на пятом шаге, и повтор обязан продолжить, а не
    завести второй проект. Поэтому сначала спрашиваем, существует ли репозиторий,
    и только потом создаём.

    Создание, которое не удалось, обязано остаться провалом этапа: следующий шаг
    (`release_ready`) без записанного remote не пройдёт, и сайт не будет выпущен
    из монорепозитория.
    """
    import subprocess

    имя = repo_name_for(order.site_id, order.domain)
    полное = f"{namespace}/{имя}"

    def выполнить(cmd: list[str]) -> tuple[int, str]:
        if runner is not None:
            return runner(cmd)
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    # 1. Уже существует? Тогда ничего не создаём и возвращаем его же.
    код, вывод = выполнить(["gh", "api", f"repos/{полное}", "--jq", ".full_name,.private"])
    if код == 0:
        строки = [s for s in вывод.strip().splitlines() if s]
        приватный = strings_last_is_true(строки)
        if not приватный:
            raise StageBlocked(
                f"{полное} существует, но он не приватный. Публичный репозиторий "
                "сайта здесь не принимается: сделайте его приватным вручную."
            )
        return {"repository": полное, "created": False, "reused": True,
                "url": f"https://github.com/{полное}", "private": True}

    # 2. Нет — создаём приватным.
    код, вывод = выполнить([
        "gh", "repo", "create", полное, "--private",
        "--description", f"{order.domain} — самостоятельный сайт (tenant {order.site_id})",
    ])
    if код != 0:
        raise StageBlocked(
            f"репозиторий {полное} не создан: {вывод.strip()[:300]}. "
            "Выпуск остановлен: публиковать сайт из монорепозитория нельзя."
        )
    return {"repository": полное, "created": True, "reused": False,
            "url": f"https://github.com/{полное}", "private": True}


def strings_last_is_true(строки: list[str]) -> bool:
    """`gh --jq` печатает поля построчно; приватность — последняя строка."""
    return bool(строки) and строки[-1].strip().lower() == "true"
