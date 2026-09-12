"""Готовность onboarding как ВЫЧИСЛЯЕМАЯ проекция.

Отдельного хранилища состояния здесь нет намеренно. Всё, что нужно, уже
записано: состав и жизненный цикл сайта — в Site Registry, исходы изменений —
в наборах CORE-003, связи внешних ресурсов — в таблице связей. Заведи мы
рядом собственное поле «стадия», и появился бы второй ответ на вопрос, что
сейчас происходит, — а расходятся такие ответы всегда молча.

`lifecycle_state` реестра не переопределяется: готовность — про то, доведён
ли onboarding, а не про то, жив ли сайт.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REQUESTED = "REQUESTED"
INFRA_PLANNED = "INFRA_PLANNED"
DNS_READY = "DNS_READY"
TLS_READY = "TLS_READY"
TEMPLATE_READY = "TEMPLATE_READY"
ANALYTICS_READY = "ANALYTICS_READY"
SEO_READY = "SEO_READY"
MONITORING_READY = "MONITORING_READY"
COMPLETE = "COMPLETE"
BLOCKED = "BLOCKED"
FAILED = "FAILED"

#: Порядок стадий. Готовность — наибольшая достигнутая, а не «последняя, что
#: попробовали»: попытка, окончившаяся ничем, стадию не двигает.
ПОРЯДОК = (REQUESTED, INFRA_PLANNED, DNS_READY, TLS_READY, TEMPLATE_READY,
           ANALYTICS_READY, SEO_READY, MONITORING_READY, COMPLETE)

#: Какая связь закрывает какую стадию.
СТАДИЯ_ПО_РЕСУРСУ = {
    ("dns", "record_set"): DNS_READY,
    ("tls", "certificate"): TLS_READY,
    ("analytics", "counter"): ANALYTICS_READY,
    ("seo_rank", "project"): SEO_READY,
}

ЖИВЫЕ = ("CREATED", "ADOPTED")


@dataclass(frozen=True)
class Готовность:
    site_id: str
    stage: str
    reached: tuple[str, ...]
    blocked_reason: str | None = None
    waiting: tuple[str, ...] = ()
    details: dict[str, Any] | None = None

    def в_словарь(self) -> dict[str, Any]:
        return {"site_id": self.site_id, "stage": self.stage,
                "reached": list(self.reached),
                "blocked_reason": self.blocked_reason,
                "waiting": list(self.waiting),
                "details": self.details or {}}


def вычислить(*, site_id: str, запись_реестра: dict | None,
              связи: list, наборы: list[dict],
              шаблон_готов: bool = False,
              мониторинг_готов: bool = False) -> Готовность:
    """Собрать стадию из того, что уже записано другими."""
    достигнуто = {REQUESTED}
    подробности: dict[str, Any] = {}
    ожидание: list[str] = []

    if запись_реестра:
        достигнуто.add(INFRA_PLANNED)
        подробности["lifecycle_state"] = запись_реестра.get("lifecycle_state")
        подробности["environment"] = запись_реестра.get("environment")

    for связь in связи:
        стадия = СТАДИЯ_ПО_РЕСУРСУ.get((связь.provider_type, связь.resource_kind))
        if стадия and связь.lifecycle in ЖИВЫЕ:
            достигнуто.add(стадия)
            подробности[f"{связь.provider_type}.{связь.resource_kind}"] = {
                "external_id": связь.external_id, "origin": связь.origin,
                "lifecycle": связь.lifecycle}
        elif стадия and связь.lifecycle == "RETIRED":
            подробности[f"{связь.provider_type}.{связь.resource_kind}"] = {
                "external_id": связь.external_id, "lifecycle": "RETIRED"}

    if шаблон_готов:
        достигнуто.add(TEMPLATE_READY)
    if мониторинг_готов:
        достигнуто.add(MONITORING_READY)

    # Появление первых данных Метрики — асинхронное ожидание, а не незакрытая
    # стадия. Крутить onboarding, пока не придут данные, значило бы никогда
    # его не завершить: данные приходят по расписанию провайдера.
    for связь in связи:
        if (связь.provider_type, связь.resource_kind) == ("analytics", "counter") \
                and связь.lifecycle in ЖИВЫЕ:
            ожидание.append("analytics.data:WAITING_DATA")

    провал = next((н for н in наборы
                   if н.get("status") in ("APPLY_FAILED", "VERIFY_FAILED",
                                          "MANUAL_INTERVENTION_REQUIRED")), None)
    if провал:
        return Готовность(site_id, FAILED, tuple(sorted(достигнуто)),
                          blocked_reason=f"набор {провал.get('changeset_id')}: "
                                         f"{провал.get('status')}",
                          waiting=tuple(ожидание), details=подробности)
    заблокирован = next((н for н in наборы if н.get("status") == "BLOCKED"), None)
    if заблокирован:
        return Готовность(site_id, BLOCKED, tuple(sorted(достигнуто)),
                          blocked_reason=заблокирован.get("failure_reason"),
                          waiting=tuple(ожидание), details=подробности)

    # Стадия — самая дальняя НЕПРЕРЫВНО достигнутая: закрытая аналитика при
    # незакрытом DNS не означает, что onboarding дошёл до аналитики.
    стадия = REQUESTED
    for ш in ПОРЯДОК:
        if ш == COMPLETE:
            continue
        if ш in достигнуто:
            стадия = ш
        else:
            break
    обязательные = set(ПОРЯДОК) - {COMPLETE}
    if обязательные <= достигнуто:
        стадия = COMPLETE
    return Готовность(site_id, стадия, tuple(sorted(достигнуто)),
                      waiting=tuple(ожидание), details=подробности)
