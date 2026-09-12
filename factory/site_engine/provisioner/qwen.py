"""Роль локального Qwen: оркестратор заявок и автор SEO-текстов.

Что он делает
-------------

Принимает заявку на сайт, превращает её в OnboardingIntent, выбирает профиль
из УТВЕРЖДЁННОГО перечня, запускает контур и пишет тексты. Тексты сохраняются
как версионированные черновики со статусом DRAFT — не как опубликованный
контент.

Чего он не делает и почему именно так
-------------------------------------

Qwen — актор типа MODEL. Запреты держатся не на его сговорчивости, а на трёх
механизмах, каждый из которых действует сам по себе:

* права в контуре изменений: у службы `qwen` есть только роль PROPOSER, а
  действия approve/apply/rollback/grant_authority закрыты для MODEL отдельно
  и независимо от роли;
* журнал аудита: тип актора MODEL не вправе записывать исполнительные фазы;
* операционная система: учётная запись `qwen` не входит ни в одну
  привилегированную группу, не имеет sudo, docker и оболочки.

Здесь — четвёртый слой: сам контракт не предоставляет ни одного способа
дотянуться до провайдера, секрета или произвольного адреса. Отсутствие
метода надёжнее проверки внутри метода.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from factory.site_engine.provisioner.intent import IntentError, OnboardingIntent

РОЛЬ = "AI_ORCHESTRATOR_AND_CONTENT_AUTHOR"
АКТОР = {"actor_id": "service:qwen", "actor_type": "MODEL", "service": "qwen"}

#: Только утверждённые связки семейства и профиля. Свободный ввод здесь
#: означал бы, что модель придумывает шаблон, которого нет.
УТВЕРЖДЁННЫЕ_ПРОФИЛИ = {
    "yummy": ("catalog-search", "catalog-editorial", "catalog-schedule"),
    "lords": ("lords-general", "lords-new", "lords-curated"),
    "zona": ("zona-general",),
    "animedia": ("animedia-general",),
}

СТАТУС_ЧЕРНОВИКА = "DRAFT"


class QwenDenied(PermissionError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.error_code, self.detail = code, detail


@dataclass(frozen=True)
class Черновик:
    site_id: str
    resource_id: str
    locale: str
    model: str
    model_version: str
    prompt_profile_version: str
    content_hash: str
    created_at: str
    correlation_id: str
    status: str = СТАТУС_ЧЕРНОВИКА
    title: str = ""
    description: str = ""
    h1: str = ""
    body: str = ""
    quality: dict[str, Any] | None = None

    def в_словарь(self) -> dict[str, Any]:
        д = {
            "site_id": self.site_id, "page_resource_id": self.resource_id,
            "locale": self.locale, "model": self.model,
            "model_version": self.model_version,
            "prompt_profile_version": self.prompt_profile_version,
            "content_hash": self.content_hash, "created_at": self.created_at,
            "correlation_id": self.correlation_id, "status": self.status,
            "title": self.title, "description": self.description,
            "h1": self.h1, "body": self.body,
        }
        if self.quality is not None:
            д["quality_checks"] = self.quality
        return д


class QwenКонтракт:
    """Единственная поверхность, доступная модели.

    Методов для обращения к провайдерам, чтения секретов, одобрения и
    применения здесь нет — не отключены, а отсутствуют.
    """

    роль = РОЛЬ

    def __init__(self, *, модель: str = "qwen-local",
                 версия_модели: str = "unknown",
                 версия_профиля: str = "unknown") -> None:
        self.модель = модель
        self.версия_модели = версия_модели
        self.версия_профиля = версия_профиля

    # --- разрешённое --------------------------------------------------------
    def создать_намерение(self, заявка: dict[str, Any]) -> OnboardingIntent:
        семейство = str(заявка.get("template_family") or "").strip()
        профиль = str(заявка.get("template_profile") or "").strip()
        допустимые = УТВЕРЖДЁННЫЕ_ПРОФИЛИ.get(семейство)
        if допустимые is None:
            raise QwenDenied("TEMPLATE_FAMILY_NOT_APPROVED",
                             f"семейство {семейство!r} не входит в утверждённый перечень")
        if профиль not in допустимые:
            raise QwenDenied(
                "TEMPLATE_PROFILE_NOT_APPROVED",
                f"профиль {профиль!r} не утверждён для семейства {семейство}")
        намерение = OnboardingIntent.разобрать({**заявка, "requested_by": "service:qwen"})
        return намерение

    def черновик(self, *, site_id: str, resource_id: str, locale: str,
                 correlation_id: str, created_at: str, title: str,
                 description: str, h1: str, body: str,
                 quality: dict[str, Any] | None = None) -> Черновик:
        """SEO-текст как версионированный черновик, а не как публикация."""
        пустые = [и for и, з in (("title", title), ("h1", h1), ("body", body))
                  if not str(з).strip()]
        if пустые:
            raise QwenDenied("DRAFT_INCOMPLETE", f"не заполнены поля: {пустые}")
        содержимое = json.dumps(
            {"title": title, "description": description, "h1": h1, "body": body},
            ensure_ascii=False, sort_keys=True)
        return Черновик(
            site_id=site_id, resource_id=resource_id, locale=locale,
            model=self.модель, model_version=self.версия_модели,
            prompt_profile_version=self.версия_профиля,
            content_hash="sha256:" + hashlib.sha256(
                содержимое.encode("utf-8")).hexdigest(),
            created_at=created_at, correlation_id=correlation_id,
            title=title, description=description, h1=h1, body=body,
            quality=quality)

    # --- явные отказы -------------------------------------------------------
    #
    # Эти методы существуют, чтобы отказ был НАЗВАН. Их отсутствие давало бы
    # AttributeError — по нему нельзя отличить запрет от опечатки, а в отчёте
    # такое выглядит как «не проверяли».
    def approve(self, *_: Any, **__: Any) -> None:
        raise QwenDenied("MODEL_ACTION_DENIED",
                         "актор типа MODEL не одобряет изменения ни при какой роли")

    def apply(self, *_: Any, **__: Any) -> None:
        raise QwenDenied("MODEL_ACTION_DENIED",
                         "актор типа MODEL не применяет изменения")

    def rollback(self, *_: Any, **__: Any) -> None:
        raise QwenDenied("MODEL_ACTION_DENIED",
                         "актор типа MODEL не выполняет откат")

    def read_secret(self, *_: Any, **__: Any) -> None:
        raise QwenDenied("SECRET_ACCESS_DENIED",
                         "модель не получает значений секретов ни в каком виде")

    def call_provider(self, *_: Any, **__: Any) -> None:
        raise QwenDenied("PROVIDER_ACCESS_DENIED",
                         "обращение к API регистратора, DNS, Метрики и Topvisor "
                         "идёт только через Integration Provisioner")

    def change_policy(self, *_: Any, **__: Any) -> None:
        raise QwenDenied("POLICY_CHANGE_DENIED", "политика модели не принадлежит")

    def run(self, *_: Any, **__: Any) -> None:
        raise QwenDenied("EXECUTION_DENIED",
                         "произвольные команды оболочки, SQL и HTTP недоступны")


def предложить(контракт: QwenКонтракт, намерение: OnboardingIntent) -> dict[str, Any]:
    """Заявка от модели: предложение, а не исполнение."""
    return {"actor": dict(АКТОР), "role": контракт.роль,
            "proposal": намерение.в_словарь(),
            "authority": "PROPOSE", "phase": "PROPOSED"}
