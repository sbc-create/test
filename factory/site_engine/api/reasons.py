"""Классификация причин отсутствия воспроизведения.

Версионированная и машиночитаемая: по коду можно понять, на каком звене
потеряно видео, повторять ли попытку, что показать зрителю, что сказать
оператору и что система вправе сделать сама.

Почему это отдельный модуль, а не строки в коде. Причина отказа переживает
запрос: она попадает в журнал, в метрику, в админку и в отчёт о покрытии.
Строка, написанная в трёх местах по-разному, превращает подсчёт в угадывание —
а весь смысл классификации в том, чтобы «сколько карточек без видео и почему»
имело один ответ.

Разделение на повторяемые и окончательные существеннее, чем кажется. Повторять
окончательное — жечь квоту поставщика на заведомо пустом запросе. Считать
окончательным временное — терять видео, которое появится через час.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

VERSION = "1.0"

# Звенья цепочки в порядке прохождения. Код причины обязан указывать, где
# именно потеряно видео: без стадии «не играет» не отличить от «не нашли».
STAGES = (
    "source",       # запись у поставщика содержимого
    "identity",     # сопоставление идентификаторов
    "projection",   # каталог и его свежесть
    "policy",       # правила витрины и лицензии
    "resolver",     # обращение к плееру за потоком
    "descriptor",   # то, что уходит в разметку
    "client",       # компонент плеера в браузере
    "media",        # запрос самого потока и первый кадр
)


@dataclass(frozen=True)
class Reason:
    code: str
    stage: str
    terminal: bool
    public: str
    operator: str
    metric: str
    remediation: str
    automatic: str | None = None
    cooldown_seconds: int = 0
    escalate_after: int = 0
    tags: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code, "stage": self.stage, "terminal": self.terminal,
            "retryable": not self.terminal, "public": self.public,
            "operator": self.operator, "metric": self.metric,
            "remediation": self.remediation, "automatic": self.automatic,
            "cooldownSeconds": self.cooldown_seconds,
            "escalateAfter": self.escalate_after, "tags": list(self.tags),
            "version": VERSION,
        }


_ОБЩЕЕ = "Видео для этого тайтла временно недоступно."

REASONS: dict[str, Reason] = {r.code: r for r in (
    Reason(
        code="MISSING_PROVIDER_ID", stage="source", terminal=True,
        public=_ОБЩЕЕ,
        operator="Источник не дал ни одного идентификатора: играть нечем и адресовать нечего. "
                 "Измерено 2026-09-05: 66 карточек из 53 203.",
        metric="playback_reason_total{code=MISSING_PROVIDER_ID}",
        remediation="Дождаться обогащения записи у поставщика. Идентификатор не выдумывать.",
        automatic=None, cooldown_seconds=86400, escalate_after=0,
        tags=("ожидаемое", "не-дефект"),
    ),
    Reason(
        code="UNSUPPORTED_AGGREGATOR", stage="identity", terminal=False,
        public=_ОБЩЕЕ,
        operator="Идентификаторы есть, но ни один не объявлен в playback_aggregator_priority. "
                 "Так были потеряны 637 карточек с одним лишь IMDb, пока imdb не добавили в контракт.",
        metric="playback_reason_total{code=UNSUPPORTED_AGGREGATOR}",
        remediation="Проверить у поставщика, принимает ли он этот агрегатор; при да — добавить "
                    "в контракт последним и переработать проекцию.",
        automatic="targeted-reprojection", cooldown_seconds=3600, escalate_after=100,
        tags=("наш-дефект", "массовое"),
    ),
    Reason(
        code="IDENTITY_MAPPING_MISS", stage="identity", terminal=False,
        public=_ОБЩЕЕ,
        operator="Запись есть у поставщика, но связать её с карточкой не удалось.",
        metric="playback_reason_total{code=IDENTITY_MAPPING_MISS}",
        remediation="Сверить алиасы внешних идентификаторов в контракте с ответом источника.",
        automatic="targeted-replay", cooldown_seconds=1800, escalate_after=50,
        tags=("наш-дефект",),
    ),
    Reason(
        code="IDENTITY_AMBIGUOUS", stage="identity", terminal=True,
        public=_ОБЩЕЕ,
        operator="Идентификатору соответствует более одной записи либо название у поставщика "
                 "расходится с нашим. Автоматический выбор запрещён: приклеить чужое видео "
                 "хуже, чем не показать своё.",
        metric="playback_reason_total{code=IDENTITY_AMBIGUOUS}",
        remediation="Отправить в очередь ручного разбора. Не выбирать вариант автоматически.",
        automatic=None, cooldown_seconds=0, escalate_after=1,
        tags=("ручной-разбор", "опасное"),
    ),
    Reason(
        code="PROVIDER_NOT_PLAYABLE", stage="resolver", terminal=True,
        public=_ОБЩЕЕ,
        operator="Поставщик ответил 204 или пустым списком: потока нет. Это честное «нечего "
                 "играть», а не сбой связи.",
        metric="playback_reason_total{code=PROVIDER_NOT_PLAYABLE}",
        remediation="Исключить из полок, обещающих просмотр. Перепроверять по расписанию: "
                    "поток может появиться позже.",
        automatic="scheduled-recheck", cooldown_seconds=21600, escalate_after=0,
        tags=("ожидаемое",),
    ),
    Reason(
        code="RESOLVER_TIMEOUT", stage="resolver", terminal=False,
        public=_ОБЩЕЕ,
        operator="Поставщик не ответил за отведённое время. Неопределённость, а не отказ: "
                 "прежний рабочий дескриптор стирать нельзя.",
        metric="playback_reason_total{code=RESOLVER_TIMEOUT}",
        remediation="Повтор с отступом; при массовости — снизить частоту опроса.",
        automatic="scoped-retry", cooldown_seconds=300, escalate_after=200,
        tags=("временное",),
    ),
    Reason(
        code="RESOLVER_ERROR", stage="resolver", terminal=False,
        public=_ОБЩЕЕ,
        operator="Поставщик ответил ошибкой (5xx либо неизвестный агрегатор — 503).",
        metric="playback_reason_total{code=RESOLVER_ERROR}",
        remediation="Проверить перечень агрегаторов и доступность поставщика.",
        automatic="scoped-retry", cooldown_seconds=600, escalate_after=100,
        tags=("временное",),
    ),
    Reason(
        code="DOMAIN_NOT_ELIGIBLE", stage="policy", terminal=True,
        public="Этот тайтл недоступен на этой витрине.",
        operator="Профиль витрины не допускает этот тип содержимого или направление.",
        metric="playback_reason_total{code=DOMAIN_NOT_ELIGIBLE}",
        remediation="Проверить профиль витрины. Менять — через ревью, не через API.",
        automatic=None, cooldown_seconds=86400, escalate_after=0,
        tags=("политика",),
    ),
    Reason(
        code="CONTENT_NOT_PLAYABLE_BY_POLICY", stage="policy", terminal=True,
        public="Этот тайтл доступен только в описании.",
        operator="Лицензионные или редакционные правила запрещают показ.",
        metric="playback_reason_total{code=CONTENT_NOT_PLAYABLE_BY_POLICY}",
        remediation="Решение редакции. Технических действий не требуется.",
        automatic=None, cooldown_seconds=86400, escalate_after=0,
        tags=("политика",),
    ),
    Reason(
        code="PROJECTION_STALE", stage="projection", terminal=False,
        public=_ОБЩЕЕ,
        operator="Каталог не обновлялся дольше обещанной свежести. Так было 2026-09-04: "
                 "таймер обновления застрял на infinity и сутки не запускался, оставаясь active.",
        metric="playback_projection_age_seconds",
        remediation="Проверить таймер обновления и его якорь по завершению; запустить "
                    "адресную переработку.",
        automatic="targeted-reprojection", cooldown_seconds=900, escalate_after=1,
        tags=("наш-дефект", "массовое"),
    ),
    Reason(
        code="DESCRIPTOR_INVALID", stage="descriptor", terminal=False,
        public=_ОБЩЕЕ,
        operator="Дескриптор собран, но неполон: нет агрегатора либо идентификатора.",
        metric="playback_reason_total{code=DESCRIPTOR_INVALID}",
        remediation="Проверить нормализацию записи; такой дескриптор в разметку не отдавать.",
        automatic="targeted-reprojection", cooldown_seconds=1800, escalate_after=20,
        tags=("наш-дефект",),
    ),
    Reason(
        code="CLIENT_COMPONENT_FAILED", stage="client", terminal=False,
        public="Проигрыватель не запустился. Обновите страницу.",
        operator="Компонент плеера не загрузился или упал в браузере.",
        metric="playback_reason_total{code=CLIENT_COMPONENT_FAILED}",
        remediation="Проверить доступность скрипта плеера и его версию.",
        automatic=None, cooldown_seconds=0, escalate_after=10,
        tags=("клиент",),
    ),
    Reason(
        code="IFRAME_FAILED", stage="client", terminal=False,
        public="Проигрыватель не запустился. Обновите страницу.",
        operator="Рамка плеера не загрузилась: сеть, блокировщик или запрет источника.",
        metric="playback_reason_total{code=IFRAME_FAILED}",
        remediation="Проверить заголовки разрешённых источников и доступность домена плеера.",
        automatic=None, cooldown_seconds=0, escalate_after=10,
        tags=("клиент",),
    ),
    Reason(
        code="MEDIA_REQUEST_FAILED", stage="media", terminal=False,
        public="Видео не начало воспроизводиться. Попробуйте ещё раз.",
        operator="Запрос самого потока завершился ошибкой уже после готовности плеера.",
        metric="playback_reason_total{code=MEDIA_REQUEST_FAILED}",
        remediation="Проверить доступность потока и срок действия ссылки.",
        automatic="scoped-retry", cooldown_seconds=300, escalate_after=25,
        tags=("клиент", "временное"),
    ),
    Reason(
        code="FIRST_FRAME_TIMEOUT", stage="media", terminal=False,
        public="Видео не начало воспроизводиться. Попробуйте ещё раз.",
        operator="Плеер сообщил о готовности, но первый кадр не пришёл за отведённое время. "
                 "Готовность не равна воспроизведению — засчитывать её за успех нельзя.",
        metric="playback_first_frame_timeout_total",
        remediation="Проверить пропускную способность источника потока и его задержку.",
        automatic="scoped-retry", cooldown_seconds=300, escalate_after=25,
        tags=("клиент", "временное"),
    ),
    Reason(
        code="UNKNOWN", stage="descriptor", terminal=False,
        public=_ОБЩЕЕ,
        operator="Причина не классифицирована. Допустима только как временная заглушка: "
                 "массовый UNKNOWN означает, что классификация отстала от действительности.",
        metric="playback_reason_total{code=UNKNOWN}",
        remediation="Разобрать выборку и завести код причины.",
        automatic=None, cooldown_seconds=0, escalate_after=25,
        tags=("требует-разбора",),
    ),
)}

TERMINAL = frozenset(c for c, r in REASONS.items() if r.terminal)
RETRYABLE = frozenset(c for c, r in REASONS.items() if not r.terminal)


def get(code: str) -> Reason:
    """Причина по коду. Неизвестный код — это UNKNOWN, а не исключение."""
    return REASONS.get(str(code or "").strip().upper(), REASONS["UNKNOWN"])


def catalogue() -> dict[str, Any]:
    """Полный справочник для Control API и админки."""
    return {
        "version": VERSION,
        "stages": list(STAGES),
        "codes": {c: r.as_dict() for c, r in sorted(REASONS.items())},
    }


def classify_descriptor(external_ids: dict | None, playback: dict | None,
                        *, supported: tuple[str, ...] = ("kp", "mali", "mdl", "imdb"),
                        probe: str | None = None) -> str:
    """Код причины по состоянию записи каталога.

    Порядок проверок повторяет порядок цепочки: сначала источник, потом
    сопоставление, потом резолвер. Иначе отсутствие идентификатора выглядело бы
    как отказ поставщика.
    """
    ext = external_ids or {}
    pb = playback if isinstance(playback, dict) else None
    if not pb:
        if not ext:
            return "MISSING_PROVIDER_ID"
        return "UNSUPPORTED_AGGREGATOR"
    aggr, tid = pb.get("aggregator"), pb.get("title_id")
    if not aggr or not tid:
        return "DESCRIPTOR_INVALID"
    if aggr not in supported:
        return "UNSUPPORTED_AGGREGATOR"
    if probe == "EMPTY":
        return "PROVIDER_NOT_PLAYABLE"
    if probe and probe.startswith("ERROR_Timeout"):
        return "RESOLVER_TIMEOUT"
    if probe and (probe.startswith("HTTP_") or probe.startswith("ERROR_")):
        return "RESOLVER_ERROR"
    return "OK"
