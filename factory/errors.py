"""Статусы конвейера и типизированные ошибки.

Общего `failed` не существует: каждая ветка отказа обязана назвать точный статус.
"""
from __future__ import annotations

PIPELINE_STATES = (
    "RECEIVED", "VALIDATING", "READY", "BUILDING", "BUILT", "STAGING_DEPLOY", "STAGING_QA",
    "AUTHORIZATION_CHECK", "PRODUCTION_DEPLOY", "PRODUCTION_SMOKE", "MONITORING", "DONE",
)

FAILURE_STATES = (
    "BLOCKED_INPUT", "BLOCKED_LICENSE", "BLOCKED_RIGHTS", "BLOCKED_SECRET", "BLOCKED_ACCESS",
    "BLOCKED_AUTHORIZATION", "BLOCKED_SEO",
    # Введены вторым change request: три сайта на общем каталоге создают три
    # новых способа отказа, которые нельзя честно назвать общим BLOCKED_SEO.
    "BLOCKED_SEO_DUPLICATE", "BLOCKED_CONTENT_RIGHTS", "BLOCKED_PLAYER_CONTRACT",
    # Введён заданием об автоматизации Яндекс.Метрики и Вебмастера: недоступный
    # API аналитики нельзя называть ни BLOCKED_SECRET (секрет на месте), ни
    # BLOCKED_ACCESS (доступа к серверу это не касается), ни тем более DONE.
    "BLOCKED_ANALYTICS_ACCESS",
    "QA_FAILED", "DEPLOY_FAILED", "ROLLED_BACK", "QUARANTINED",
)

ALL_STATES = PIPELINE_STATES + FAILURE_STATES

#: Статусы, которые никогда не ретраятся: они означают отсутствие входных данных,
#: прав или разрешения, а не временную ошибку среды.
NON_RETRYABLE = {
    "BLOCKED_INPUT", "BLOCKED_LICENSE", "BLOCKED_RIGHTS", "BLOCKED_SECRET",
    "BLOCKED_AUTHORIZATION", "BLOCKED_SEO",
    # Дубль между сайтами, неподтверждённые права и нарушенный контракт плеера
    # исправляются входными данными, а не повтором задания.
    "BLOCKED_SEO_DUPLICATE", "BLOCKED_CONTENT_RIGHTS", "BLOCKED_PLAYER_CONTRACT",
    # Отсутствующий хост, незапиненный host key или неустановленный ansible от
    # повтора не появятся, а каждая попытка делает новый бэкап и рестарт сервера.
    "BLOCKED_ACCESS",
    # Провал ворот качества — это найденный дефект, а не временная ошибка среды.
    "QA_FAILED",
    # Повторы 429 и 5xx уже сделаны внутри провайдера аналитики
    # (`factory.analytics.transport`). Дошло сюда — значит кончился токен, права
    # или сам сервис; конвейер этого не исправит, а каждый повтор создаёт риск
    # дубля счётчика.
    "BLOCKED_ANALYTICS_ACCESS",
}


class FactoryError(Exception):
    """Базовая ошибка фабрики с обязательным статусом."""

    status = "QUARANTINED"

    def __init__(self, reason: str, *, field: str = "", required_input: str = "", blocks_stage: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.field = field
        self.required_input = required_input
        self.blocks_stage = blocks_stage

    def as_blocker(self) -> dict:
        return {
            "status": self.status,
            "field": self.field or "-",
            "reason": self.reason,
            "required_input": self.required_input or "-",
            "blocks_stage": self.blocks_stage or "-",
        }

    @property
    def retryable(self) -> bool:
        return self.status not in NON_RETRYABLE


class BlockedInput(FactoryError):
    status = "BLOCKED_INPUT"


class BlockedLicense(FactoryError):
    status = "BLOCKED_LICENSE"


class BlockedRights(FactoryError):
    status = "BLOCKED_RIGHTS"


class BlockedSecret(FactoryError):
    status = "BLOCKED_SECRET"


class BlockedAccess(FactoryError):
    status = "BLOCKED_ACCESS"


class BlockedAuthorization(FactoryError):
    status = "BLOCKED_AUTHORIZATION"


class BlockedSeo(FactoryError):
    status = "BLOCKED_SEO"


class BlockedSeoDuplicate(FactoryError):
    """Индексируемые страницы разных сайтов совпадают по смыслу или по тексту."""

    status = "BLOCKED_SEO_DUPLICATE"


class BlockedContentRights(FactoryError):
    """Публикация материала без подтверждённых прав или происхождения."""

    status = "BLOCKED_CONTENT_RIGHTS"


class BlockedPlayerContract(FactoryError):
    """Встраивание плеера расходится с документированным контрактом провайдера."""

    status = "BLOCKED_PLAYER_CONTRACT"


class BlockedAnalyticsAccess(FactoryError):
    """API Метрики или Вебмастера недоступен, отвечает отказом или не даёт нужных прав.

    Отдельный статус существует ровно затем, чтобы конвейер не продолжал работу
    с выдуманными идентификаторами счётчика и выдуманными показателями.
    """

    status = "BLOCKED_ANALYTICS_ACCESS"


class QaFailed(FactoryError):
    status = "QA_FAILED"


class DeployFailed(FactoryError):
    status = "DEPLOY_FAILED"


class TransientError(FactoryError):
    """Явно временная ошибка среды: сеть, таймаут, занятый ресурс."""

    status = "DEPLOY_FAILED"

    @property
    def retryable(self) -> bool:
        return True
