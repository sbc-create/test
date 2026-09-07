"""Потребление контракта обогащения оценок `ratings-enrichment/1.0.0`.

Что здесь есть и чего здесь нет
-------------------------------

Здесь только сторона потребителя: разбор ответа, правила доверия значению и
правила отказа. Самого обогащения — очереди, квот, повторов, обращений к
поставщикам — здесь нет и быть не должно. Ежедневный сбор оценок принадлежит
Core: он требует хранилища, расписания, учёта лимитов и ключей доступа, а
шаблоны ничего этого не имеют и иметь не должны.

Зачем контракт вообще нужен
---------------------------

Измерено на полном боевом каталоге, 53 251 запись:

* оценка Кинопоиска есть у 19 575 (36,8 %), IMDb — у 27 003 (50,7 %);
* число голосов не даёт ни один слой источника — 0 %;
* при этом идентификатор Кинопоиска есть у 46 695 (87,7 %), IMDb — у 44 943
  (84,4 %);
* значит **27 127 записей (50,9 %) имеют ключ сопоставления и не имеют
  оценки** — их можно обогатить прямым запросом по ключу, без угадывания.

Проверено отдельно, что нынешний источник исчерпан: списочный ответ и ответ
detail дают одни и те же значения — сверено на 12 009 парах, прибавка ноль,
расхождений ноль. Дальнейший рост покрытия требует другого поставщика, а не
лучшей работы с этим.

Главные правила потребления
---------------------------

1. **Оценка без происхождения не показывается.** Число, поставленное неизвестно
   кем, нельзя ни проверить, ни объяснить. Требуется поставщик, шкала и время
   наблюдения; полоса SEO отдельным решением отказалась выпускать оценку без
   этого, и здесь то же правило.
2. **Последнее известное хорошее значение не затирается пустым ответом.**
   Поставщик, промолчавший сегодня, не отменяет вчерашнего наблюдения.
3. **Уверенность сопоставления обязательна и проверяется.** Оценка, привязанная
   к записи по названию и году, а не по идентификатору, может принадлежать
   другому произведению — одноимённому фильму или ремейку. Такая оценка
   принимается только выше порога уверенности и всегда несёт признак способа
   сопоставления.
4. **Шкалы не смешиваются.** 7,4 у Кинопоиска и 7,4 у IMDb — разные
   утверждения; усреднять их или подставлять одно вместо другого запрещено.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

#: Версия контракта, под которую написано потребление.
CONTRACT_VERSION = "ratings-enrichment/1.0.0"

#: Поставщики, оценки которых витрина умеет показывать. Список закрыт: оценка
#: от незнакомого поставщика не показывается, потому что её шкалу неизвестно
#: как подписать.
PROVIDERS = ("kinopoisk", "imdb")

#: Способы сопоставления записи с записью поставщика, по убыванию надёжности.
#: `id` — совпадение по идентификатору, сомнений не вызывает. `title_year` —
#: по названию и году: так сопоставляются ремейки и одноимённые произведения,
#: и поэтому такому сопоставлению нужна уверенность выше порога.
MATCH_METHODS = ("id", "title_year")

#: Порог уверенности для сопоставления не по идентификатору. Значение выбрано
#: не из общих соображений: 12,3 % каталога — 6 549 записей — не имеют ни
#: идентификатора Кинопоиска, ни оценки, и именно они попадут под сопоставление
#: по названию. Ошибка здесь показывает зрителю оценку чужого произведения, что
#: хуже отсутствия оценки, поэтому порог высокий.
MIN_CONFIDENCE = 0.95

#: Возраст наблюдения, после которого значение считается устаревшим, но не
#: исчезает: показывать вчерашнюю оценку честнее, чем не показывать никакой,
#: если сказано, когда она наблюдалась.
STALE_AFTER_DAYS = 30


class ContractError(ValueError):
    """Ответ не соответствует контракту. Это отказ, а не повод догадываться."""


@dataclass(frozen=True)
class Observation:
    """Одно наблюдение оценки: кто, что, когда и насколько уверенно."""

    provider: str
    value: float
    votes: int | None
    scale_max: float
    observed_at: str
    match_method: str
    confidence: float
    external_id: str | None = None

    @property
    def trustworthy(self) -> bool:
        """Можно ли показать это наблюдение зрителю."""
        if self.provider not in PROVIDERS:
            return False
        if self.match_method not in MATCH_METHODS:
            return False
        if self.match_method != "id" and self.confidence < MIN_CONFIDENCE:
            return False
        return 0.0 <= self.value <= self.scale_max

    def age_days(self, now: datetime | None = None) -> float | None:
        moment = _parse_time(self.observed_at)
        if moment is None:
            return None
        now = now or datetime.now(timezone.utc)
        return (now - moment).total_seconds() / 86400

    def stale(self, now: datetime | None = None) -> bool:
        age = self.age_days(now)
        return age is not None and age > STALE_AFTER_DAYS


def _parse_time(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _number(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_observation(raw) -> Observation:
    """Одно наблюдение из ответа Core. Недостающее поле — отказ, а не умолчание.

    Умолчаний здесь нет намеренно. Отсутствующая шкала означала бы, что число
    не с чем сравнить; отсутствующее время наблюдения — что нельзя отличить
    вчерашнюю оценку от прошлогодней; отсутствующий способ сопоставления — что
    неизвестно, этому ли произведению оценка принадлежит. Подставить сюда
    разумное значение значит выдумать факт.
    """
    if not isinstance(raw, dict):
        raise ContractError("наблюдение не является объектом")
    provider = str(raw.get("provider") or "").strip()
    if provider not in PROVIDERS:
        raise ContractError(f"незнакомый поставщик оценки: {provider!r}")
    value = _number(raw.get("value"))
    if value is None:
        raise ContractError(f"{provider}: оценка не является числом")
    scale_max = _number(raw.get("scale_max"))
    if scale_max is None or scale_max <= 0:
        raise ContractError(f"{provider}: шкала оценки не объявлена")
    observed_at = raw.get("observed_at")
    if _parse_time(observed_at) is None:
        raise ContractError(f"{provider}: время наблюдения не объявлено или неразборчиво")
    method = str(raw.get("match_method") or "").strip()
    if method not in MATCH_METHODS:
        raise ContractError(f"{provider}: способ сопоставления не объявлен: {method!r}")
    confidence = _number(raw.get("confidence"))
    if confidence is None or not 0.0 <= confidence <= 1.0:
        raise ContractError(f"{provider}: уверенность сопоставления не объявлена")
    votes = raw.get("votes")
    if votes is not None and (isinstance(votes, bool) or not isinstance(votes, int)):
        raise ContractError(f"{provider}: число голосов не является целым")
    return Observation(
        provider=provider, value=value, votes=votes, scale_max=scale_max,
        observed_at=str(observed_at), match_method=method, confidence=float(confidence),
        external_id=(str(raw["external_id"]) if raw.get("external_id") else None),
    )


def current_ratings(payload, *, now: datetime | None = None) -> dict[str, Observation]:
    """Показываемые оценки записи: по одной на поставщика, самая свежая.

    Из нескольких наблюдений одного поставщика берётся последнее по времени.
    Наблюдения, которым нельзя доверять, отбрасываются молча для зрителя, но
    видимо для отчёта: причина возвращается отдельным вызовом `rejected`.
    """
    out: dict[str, Observation] = {}
    for observation in _observations(payload):
        if not observation.trustworthy:
            continue
        previous = out.get(observation.provider)
        if previous is None:
            out[observation.provider] = observation
            continue
        left, right = _parse_time(observation.observed_at), _parse_time(previous.observed_at)
        if left and right and left > right:
            out[observation.provider] = observation
    return out


def rejected(payload) -> list[tuple[dict, str]]:
    """Отвергнутые наблюдения и причина. Нужны отчёту, а не витрине."""
    out = []
    for raw in _raw_list(payload):
        try:
            observation = parse_observation(raw)
        except ContractError as error:
            out.append((raw, str(error)))
            continue
        if not observation.trustworthy:
            if observation.match_method != "id" and observation.confidence < MIN_CONFIDENCE:
                out.append((raw, f"уверенность {observation.confidence} ниже порога "
                                 f"{MIN_CONFIDENCE} при сопоставлении по названию"))
            else:
                out.append((raw, "значение вне объявленной шкалы"))
    return out


def merge_last_known_good(known: dict[str, Observation],
                          fresh: dict[str, Observation]) -> dict[str, Observation]:
    """Свежие наблюдения поверх известных. Пустой ответ ничего не отменяет.

    Поставщик, промолчавший сегодня, не отменяет вчерашнего наблюдения:
    молчание — это отсутствие сведений, а не сообщение об отсутствии оценки.
    Ровно на этом правиле держится устойчивость витрины к сетевым отказам.
    """
    merged = dict(known)
    merged.update(fresh)
    return merged


def _raw_list(payload) -> list:
    if isinstance(payload, dict):
        version = str(payload.get("contract") or "")
        if version and version != CONTRACT_VERSION:
            raise ContractError(
                f"версия контракта {version!r} не та, под которую написано потребление "
                f"({CONTRACT_VERSION})")
        return list(payload.get("observations") or [])
    if isinstance(payload, list):
        return list(payload)
    raise ContractError("ответ не является ни объектом контракта, ни списком наблюдений")


def _observations(payload):
    for raw in _raw_list(payload):
        try:
            yield parse_observation(raw)
        except ContractError:
            continue


__all__ = [
    "CONTRACT_VERSION", "ContractError", "MATCH_METHODS", "MIN_CONFIDENCE",
    "Observation", "PROVIDERS", "STALE_AFTER_DAYS", "current_ratings",
    "merge_last_known_good", "parse_observation", "rejected",
]
