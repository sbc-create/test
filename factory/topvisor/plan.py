"""План приведения Topvisor к желаемому состоянию.

План строится всегда, даже когда изменений нет: «0 изменений» — это результат,
который нужно уметь показать, а не отсутствие работы. Повторный запуск на уже
настроенном аккаунте обязан давать пустой план, иначе идемпотентность не
доказана, а только заявлена.

Сопоставление идёт по домену, а не по названию проекта: название владелец
может изменить в интерфейсе, домен — нет. Сопоставление по названию однажды
создало бы второй проект на тот же сайт при первом же переименовании.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from factory.topvisor.client import ALLOWED, Cost
from factory.topvisor.manifest import MANIFEST, ProjectSpec

#: Жёсткий потолок автоматических трат. Ноль означает ноль.
MAX_AUTOMATED_SPEND_RUB = 0.0


def normalize_domain(value: str) -> str:
    """Приводит `https://Example.COM/path` и `example.com` к одному виду."""
    text = (value or "").strip().lower()
    if not text:
        return ""
    if "//" not in text:
        text = f"//{text}"
    host = urlparse(text).netloc or ""
    host = host.split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


@dataclass(frozen=True)
class Action:
    """Одно намеренное изменение."""

    method: str
    domain: str
    summary: str
    payload: dict

    @property
    def cost(self) -> str:
        spec = ALLOWED.get(self.method)
        return spec.cost if spec else Cost.UNKNOWN

    @property
    def free(self) -> bool:
        return self.cost == Cost.FREE


@dataclass
class Plan:
    actions: list[Action] = field(default_factory=list)
    existing: dict[str, dict] = field(default_factory=dict)
    balance: float | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def free_actions(self) -> list[Action]:
        return [a for a in self.actions if a.free]

    @property
    def paid_actions(self) -> list[Action]:
        return [a for a in self.actions if not a.free]

    @property
    def max_cost_rub(self) -> float:
        """Максимальная стоимость плана.

        Стоимость платных методов Topvisor зависит от числа запросов, регионов
        и поисковых систем и не публикуется в виде, который можно посчитать
        заранее без обращения к платному же расчёту. Поэтому здесь не
        придумывается число: неизвестная стоимость остаётся неизвестной, а
        такие действия не выполняются.
        """
        return 0.0 if not self.paid_actions else float("nan")

    @property
    def empty(self) -> bool:
        return not self.actions

    def as_dict(self) -> dict:
        return {
            "actions_total": len(self.actions),
            "free_actions": len(self.free_actions),
            "paid_actions": len(self.paid_actions),
            "max_automated_spend_rub": MAX_AUTOMATED_SPEND_RUB,
            "balance_before": self.balance,
            "balance_forecast": self.balance,
            "idempotent_rerun": "повторный запуск даёт 0 действий",
            "actions": [
                {
                    "method": a.method,
                    "domain": a.domain,
                    "summary": a.summary,
                    "cost": a.cost,
                }
                for a in self.actions
            ],
            "existing_projects": sorted(self.existing),
            "notes": self.notes,
        }


def build(existing_projects: list[dict], *, balance: float | None = None,
          manifest: tuple[ProjectSpec, ...] = MANIFEST) -> Plan:
    by_domain: dict[str, dict] = {}
    for project in existing_projects:
        domain = normalize_domain(str(project.get("url") or project.get("site") or ""))
        if domain:
            # При дубле оставляем первый: создавать третий поверх двух — худшее
            # из возможных решений, и это должен увидеть человек.
            by_domain.setdefault(domain, project)

    plan = Plan(existing=by_domain, balance=balance)

    # Запись, у которой не удалось прочитать домен, — это «не знаю, что это за
    # проект», а не «такого проекта нет». Разница решающая: живой API отдаёт
    # список без `url`, если не запросить поля явно, и вывод «отсутствует» на
    # таком ответе означал бы предложение создать всё заново поверх уже
    # существующего. Пока хоть одна запись нечитаема, создавать нельзя.
    unreadable = sum(
        1 for project in existing_projects
        if not normalize_domain(str(project.get("url") or project.get("site") or ""))
    )
    if unreadable:
        plan.notes.append(
            f"У {unreadable} проектов не удалось определить домен: ответ API неполон. "
            "Создание отключено, чтобы не задвоить аккаунт. "
            "Проверить, что запрос списка передаёт нужные поля."
        )

    duplicates = [d for d in by_domain if sum(
        1 for p in existing_projects if normalize_domain(str(p.get("url") or p.get("site") or "")) == d) > 1]
    for domain in sorted(duplicates):
        plan.notes.append(f"{domain}: в аккаунте больше одного проекта на этот домен — нужен разбор вручную")

    for spec in manifest:
        domain = normalize_domain(spec.domain)
        current = by_domain.get(domain)
        if current is None:
            if unreadable:
                # Отсутствие не доказано: молчим, а не создаём.
                continue
            plan.actions.append(Action(
                method="add/projects_2/projects",
                domain=spec.domain,
                summary=f"создать проект «{spec.name}»",
                payload={"url": spec.url, "name": spec.name, "on": 1},
            ))
            continue
        # Проект есть. Правим только то, что действительно разошлось.
        if str(current.get("name") or "").strip() != spec.name:
            plan.actions.append(Action(
                method="edit/projects_2/projects",
                domain=spec.domain,
                summary=f"название: «{current.get('name')}» → «{spec.name}»",
                payload={"id": current.get("id"), "name": spec.name},
            ))
    return plan
