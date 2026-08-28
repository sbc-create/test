"""Ranker v1 — детерминированное ранжирование витрин.

Никакого обучения и никакого внешнего сервиса: формула, веса и правила
разнообразия заданы явно. Это сознательный выбор первого релиза — детерминизм
позволяет объяснить любую позицию в полке и воспроизвести выдачу по версии
алгоритма и входу. Metarank и pgvector встают вторым этапом поверх этого же
интерфейса.

Два правила, которые важнее остальных:

* Недоступное видео ничем не компенсируется. Ни высокой оценкой, ни
  упоминанием у референса, ни редакторским закреплением.
* Отсутствующий сигнал не равен нулевому. Вес отсутствующего сигнала
  распределяется между теми, что есть, иначе запись без счётчиков навсегда
  проигрывала бы записи с одним просмотром.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from factory.recs.model import ItemFeatures, merge_duplicates

ALGORITHM_VERSION = "ranker-v1"

WEIGHTS = {
    "freshness": 0.30,
    "rating_confidence": 0.20,
    "local_engagement": 0.20,
    "episode_update": 0.10,
    "reference_trend": 0.10,
    "metadata_quality": 0.10,
}

#: Сколько голосов считается «подтверждённой» оценкой. Одна случайная десятка
#: не должна обгонять 7.9, за которой стоят тысячи голосов.
VOTES_FOR_CONFIDENCE = 1000
#: Оценка, к которой стягивается запись с малым числом голосов.
PRIOR_RATING = 6.5
FRESH_WINDOW_DAYS = 30
EVERGREEN_YEARS = 3


@dataclass(frozen=True)
class Scored:
    item: ItemFeatures
    score: float
    signals: dict
    reasons: tuple[str, ...] = ()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _age_days(moment: datetime | None, now: datetime) -> float | None:
    if moment is None:
        return None
    return max(0.0, (now - moment).total_seconds() / 86400.0)


def freshness(item: ItemFeatures, now: datetime) -> float | None:
    """Свежесть по дате поступления. Экспоненциальное затухание за месяц.

    Дата поступления, дата выхода и дата новой серии — три разные вещи, и
    смешивать их нельзя: фильм 1979 года, заведённый вчера, свежий для витрины
    «недавно добавленные» и несвежий для «новинок проката».
    """
    age = _age_days(item.added_at, now)
    if age is None:
        return None
    return _clamp(math.exp(-age / FRESH_WINDOW_DAYS))


def rating_confidence(item: ItemFeatures) -> float | None:
    """Оценка, сглаженная числом голосов.

    Оценка без голосов не отбрасывается, но и не принимается на веру: она
    стягивается к среднему тем сильнее, чем меньше за ней стоит. Так «10.0 без
    голосов» оказывается ниже «7.9 при десяти тысячах».
    """
    pairs = [(item.kp_rating, item.kp_votes), (item.imdb_rating, item.imdb_votes)]
    usable = [(r, v) for r, v in pairs
              if isinstance(r, int | float) and not isinstance(r, bool) and r > 0]
    if not usable:
        return None
    best = 0.0
    for rating, votes in usable:
        count = votes if isinstance(votes, int) and votes > 0 else 0
        weight = count / (count + VOTES_FOR_CONFIDENCE)
        smoothed = weight * float(rating) + (1 - weight) * PRIOR_RATING
        best = max(best, smoothed / 10.0)
    return _clamp(best)


def local_engagement(item: ItemFeatures) -> float | None:
    """Наш собственный спрос за месяц. Логарифм, чтобы хвост не решал всё."""
    counts = [c for c in (item.events_30d, item.events_7d, item.events_1d)
              if isinstance(c, int)]
    if not counts:
        return None
    return _clamp(math.log1p(max(counts)) / math.log1p(10000))


def episode_update(item: ItemFeatures, now: datetime) -> float | None:
    age = _age_days(item.episode_updated_at, now)
    if age is None:
        return None
    return _clamp(math.exp(-age / 14.0))


def reference_trend(item: ItemFeatures, now: datetime) -> float | None:
    """Упоминание у референса — слабый и затухающий сигнал.

    Он говорит лишь о том, что кто-то другой поставил тайтл на витрину. Вес
    ограничен, сигнал затухает за две недели, и он никогда не переопределяет
    ни доступность видео, ни профиль домена.
    """
    if not item.reference_mentions:
        return None
    best = 0.0
    for mention in item.reference_mentions:
        seen = mention.get("seen_at") if isinstance(mention, dict) else None
        if isinstance(seen, str):
            from factory.recs.model import parse_time
            seen = parse_time(seen)
        age = _age_days(seen, now)
        decay = math.exp(-age / 14.0) if age is not None else 0.5
        position = mention.get("position") if isinstance(mention, dict) else None
        rank = 1.0 / (1.0 + (position - 1) / 10.0) if isinstance(position, int) and position > 0 else 0.6
        best = max(best, decay * rank)
    return _clamp(best)


def metadata_quality(item: ItemFeatures) -> float | None:
    if isinstance(item.metadata_completeness, int | float):
        return _clamp(float(item.metadata_completeness))
    present = sum(bool(x) for x in (item.title, item.poster, item.genres,
                                    item.countries, item.release_date))
    return _clamp(present / 5.0)


def score_item(item: ItemFeatures, now: datetime, *, editorial=None) -> Scored:
    """Взвешенная сумма доступных сигналов.

    Вес отсутствующего сигнала перераспределяется между присутствующими, а не
    засчитывается нулём: иначе «о записи ничего не известно» читалось бы как
    «запись плохая».
    """
    signals = {
        "freshness": freshness(item, now),
        "rating_confidence": rating_confidence(item),
        "local_engagement": local_engagement(item),
        "episode_update": episode_update(item, now),
        "reference_trend": reference_trend(item, now),
        "metadata_quality": metadata_quality(item),
    }
    available = {k: v for k, v in signals.items() if v is not None}
    if available:
        total_weight = sum(WEIGHTS[k] for k in available)
        base = sum(WEIGHTS[k] * v for k, v in available.items()) / total_weight
    else:
        base = 0.0

    boost = 0.0
    reasons: list[str] = []
    if editorial is not None:
        boost = editorial.boost_for(item.content_id, now)
        if boost:
            reasons.append("editorial_boost")

    # Штрафы за то, что делает карточку плохой витриной, а не за незнание.
    penalty = 0.0
    if not item.poster:
        penalty += 0.25
        reasons.append("no_poster")
    if not item.title.strip():
        penalty += 0.25
        reasons.append("no_title")

    return Scored(item, base + boost - penalty, signals, tuple(reasons))


def is_eligible(item: ItemFeatures, *, domain: str | None = None,
                profile_directions: tuple = (), editorial=None,
                now: datetime | None = None) -> tuple[bool, str]:
    """Жёсткий допуск на витрину. Возвращает решение и его причину."""
    now = now or datetime.now(timezone.utc)
    if editorial is not None and editorial.is_banned(item.content_id, now, domain=domain):
        return False, "banned"
    # Подтверждённое отсутствие потока — единственный приговор по видео.
    # Непроверенная запись на витрину не идёт тоже: карусель обещает просмотр.
    if item.playback_state is not True:
        return False, "no_confirmed_playback"
    if not item.has_title_page:
        return False, "no_title_page"
    if not item.poster:
        return False, "no_poster"
    if not item.title.strip():
        return False, "no_title"
    if profile_directions and item.direction is not None \
            and item.direction not in profile_directions:
        return False, "foreign_direction"
    if domain and item.domain_eligibility and domain not in item.domain_eligibility:
        return False, "domain_excluded"
    return True, "ok"


def _is_fresh(item: ItemFeatures, now: datetime) -> bool:
    age = _age_days(item.added_at, now)
    return age is not None and age <= FRESH_WINDOW_DAYS


def _is_evergreen(item: ItemFeatures, now: datetime) -> bool:
    age = _age_days(item.release_date, now)
    return age is not None and age > EVERGREEN_YEARS * 365


def diversify(scored: list[Scored], limit: int, now: datetime) -> list[Scored]:
    """Расстановка с ограничениями разнообразия.

    Полка из десяти боевиков одной франшизы — это не подборка, а сбой.
    Ограничения жёсткие: если их нельзя выполнить, полка становится короче, но
    не превращается в повтор. Прежде здесь стояло «взять первого попавшегося,
    если правила мешают», и правило про франшизу нарушалось ровно тогда, когда
    оно было нужнее всего — при избытке однотипных кандидатов.
    """
    chosen: list[Scored] = []
    used_franchise: set[str] = set()
    remaining = list(scored)

    def genre_run_ok(candidate: Scored) -> bool:
        if not candidate.item.genres:
            return True
        top = candidate.item.genres[0]
        tail = [c.item.genres[0] for c in chosen[-2:] if c.item.genres]
        return not (len(tail) == 2 and all(g == top for g in tail))

    def franchise_ok(candidate: Scored) -> bool:
        fid = candidate.item.franchise_id
        return not (fid and fid in used_franchise)

    while remaining and len(chosen) < limit:
        picked = next((c for c in remaining if franchise_ok(c) and genre_run_ok(c)), None)
        if picked is None:
            # Ни один оставшийся кандидат не проходит по разнообразию. Полка
            # заканчивается здесь: короткая подборка честнее однообразной.
            break
        remaining.remove(picked)
        if picked.item.franchise_id:
            used_franchise.add(picked.item.franchise_id)
        chosen.append(picked)
    return chosen


def rank(items, *, now: datetime | None = None, limit: int = 18,
         domain: str | None = None, profile_directions: tuple = (),
         editorial=None) -> list[Scored]:
    """Полный конвейер: слияние → допуск → счёт → закрепления → разнообразие."""
    now = now or datetime.now(timezone.utc)
    merged = merge_duplicates(items)
    eligible = [i for i in merged
                if is_eligible(i, domain=domain, profile_directions=profile_directions,
                               editorial=editorial, now=now)[0]]
    scored = [score_item(i, now, editorial=editorial) for i in eligible]
    # Детерминизм: при равных счетах порядок задаёт устойчивый идентификатор,
    # а не случайность обхода словаря.
    scored.sort(key=lambda s: (-round(s.score, 12), s.item.content_id))

    if editorial is not None:
        scored = editorial.apply_pins(scored, now)
    return diversify(scored, limit, now)
