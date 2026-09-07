"""Сопоставление произведений: объяснимая оценка и лестница признаков.

Три свойства, ради которых модуль написан именно так.

**Оценка объяснима.** Возвращается не число, а разбор: какой признак совпал,
какой не совпал, какой отсутствовал и сколько каждый весил. «Совпало на 0,93»
без разбора невозможно ни проверить, ни оспорить, а привязка чужого рейтинга
к чужому произведению — ровно та ошибка, которую нельзя заметить по числу.

**Противоречие закрывает кандидата, а не понижает оценку.** Разница
принципиальная: понижение позволяет добрать порог другими признаками, и фильм
привяжется к сериалу, если совпали название, год и страна. Совпадение
названия при разном виде произведения — это не «немного не то», это не то.

**Оценка делится на сумму ПРИМЕНИМЫХ весов.** Если у записи нет студии и
создателей, отсутствие этих признаков не должно опускать её ниже порога:
она не хуже сопоставлена, о ней просто меньше известно. Иначе резолвер
систематически отвергал бы бедные метаданными записи — то есть именно те,
ради которых он и нужен.
"""

from __future__ import annotations

import dataclasses
import difflib
from pathlib import Path
from typing import Any

import yaml

from factory.site_engine.content_identity import IdentityStatus, MappingMethod
from factory.site_engine.content_kind import ContentKind
from factory.site_engine.title_normalize import ключ_поиска, ключ_транслита

CONFIG_REF = "config/identity-resolution.yaml"
RESOLVER_VERSION = "identity-resolver/1.0.0"

#: Виды, которые нельзя перепутать между собой. Пары внутри одной группы
#: считаются совместимыми, пары из разных групп — жёстким противоречием.
_ГРУППА_ФИЛЬМ = frozenset({ContentKind.MOVIE, ContentKind.SHORT, ContentKind.DOCUMENTARY})
_ГРУППА_СЕРИАЛ = frozenset({ContentKind.SERIES, ContentKind.MINISERIES, ContentKind.SEASON})
_ГРУППА_ВЫПУСК = frozenset({ContentKind.OVA, ContentKind.ONA, ContentKind.SPECIAL})


class ResolutionError(RuntimeError):
    """Настройка сопоставления непригодна."""


@dataclasses.dataclass(frozen=True)
class Candidate:
    """Запись-кандидат из источника. Отсутствующее поле — None, не пустая строка."""

    entity_id: str
    source: str = ""
    external_ids: dict[str, str] = dataclasses.field(default_factory=dict)
    provider_asset_id: str | None = None
    original_title: str | None = None
    alternative_titles: tuple[str, ...] = ()
    displayed_title: str | None = None
    release_year: int | None = None
    content_kind: ContentKind | None = None
    duration: int | None = None
    episode_count: int | None = None
    country: str | None = None
    studio: str | None = None
    creators: tuple[str, ...] = ()
    is_remake: bool | None = None


#: Субъект сопоставления — наша запись. Та же форма, что у кандидата:
#: асимметрия полей приводила бы к признакам, которые сравнить не с чем.
Subject = Candidate


@dataclasses.dataclass
class FeatureScore:
    feature: str
    weight: float
    matched: bool | None  # None — признак неприменим (нет данных с одной из сторон)
    detail: str = ""

    @property
    def applicable(self) -> bool:
        return self.matched is not None


@dataclasses.dataclass
class MatchScore:
    """Разбор сопоставления одной пары."""

    candidate_id: str
    confidence: float
    features: list[FeatureScore]
    conflicts: list[str]
    #: Сколько применимых признаков совпало. Одного мало всегда: доля 1,0 при
    #: единственном совпавшем признаке — это не уверенность, а бедность входа.
    matched_features: int = 0
    #: Совпало ли хотя бы одно название ТОЧНО, а не по похожести.
    exact_title: bool = False

    @property
    def blocked(self) -> bool:
        return bool(self.conflicts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidateId": self.candidate_id,
            "confidence": round(self.confidence, 4),
            "matchedFeatures": self.matched_features,
            "exactTitle": self.exact_title,
            "conflicts": list(self.conflicts),
            "features": [
                {"feature": f.feature, "weight": f.weight, "matched": f.matched, "detail": f.detail}
                for f in self.features
            ],
        }


def load_config(root: Path | None = None) -> dict:
    if root is None:
        from factory.paths import PATHS

        root = PATHS.root
    путь = Path(root) / CONFIG_REF
    if not путь.exists():
        raise ResolutionError(f"нет файла настройки {путь}")
    данные = yaml.safe_load(путь.read_text(encoding="utf-8"))
    if not isinstance(данные, dict) or "weights" not in данные:
        raise ResolutionError(f"{путь} не содержит весов")
    for имя in ("auto_accept", "review", "ambiguity_margin"):
        if имя not in (данные.get("thresholds") or {}):
            raise ResolutionError(f"в настройке нет порога {имя!r}")
    return данные


def _группа(kind: ContentKind | None):
    if kind is None or kind is ContentKind.UNKNOWN:
        return None
    for группа in (_ГРУППА_ФИЛЬМ, _ГРУППА_СЕРИАЛ, _ГРУППА_ВЫПУСК):
        if kind in группа:
            return группа
    return frozenset({kind})


def похожесть(a: str | None, b: str | None) -> float:
    """Похожесть названий по нормализованным ключам.

    Кросс-язычное совпадение здесь приблизительно и таковым остаётся:
    японское название, прошедшее через русскую запись и обратно в латиницу,
    точным ключом не станет. Поэтому похожесть — признак среди прочих, а не
    основание для привязки.
    """
    if not a or not b:
        return 0.0
    ka, kb = ключ_поиска(a), ключ_поиска(b)
    if not ka or not kb:
        return 0.0
    if ka == kb or ключ_транслита(a) == ключ_транслита(b):
        return 1.0
    # Ключ без хвостового номера сюда НЕ входит. Он расширяет список
    # кандидатов и только: на adversarial-наборе «Дом» и «Дом 2» через него
    # совпадали ровно, и резолвер привязывал разные произведения без сомнений.
    return difflib.SequenceMatcher(None, ka, kb).ratio()


def hard_conflicts(subject: Subject, candidate: Candidate, config: dict) -> list[str]:
    """Противоречия, закрывающие кандидата. Порядок — от самого дешёвого."""
    доп = config.get("tolerances") or {}
    найдено: list[str] = []

    общие_источники = set(subject.external_ids) & set(candidate.external_ids)
    if any(str(subject.external_ids[k]) != str(candidate.external_ids[k]) for k in общие_источники):
        найдено.append("EXTERNAL_ID_DIFFERS")

    гс, гк = _группа(subject.content_kind), _группа(candidate.content_kind)
    if гс is not None and гк is not None and гс is not гк:
        # Сезон против выпуска и фильм против сериала — разные противоречия:
        # оператору они говорят разное.
        if {гс, гк} == {_ГРУППА_СЕРИАЛ, _ГРУППА_ВЫПУСК}:
            найдено.append("SEASON_VS_SPECIAL")
        else:
            найдено.append("KIND_MOVIE_VS_SERIES")

    if (
        subject.release_year
        and candidate.release_year
        and abs(subject.release_year - candidate.release_year) > int(доп.get("year_slack", 1))
    ):
        найдено.append("YEAR_INCOMPATIBLE")

    if (
        subject.episode_count
        and candidate.episode_count
        and abs(subject.episode_count - candidate.episode_count)
        > int(доп.get("episode_count_slack", 1))
    ):
        найдено.append("EPISODE_COUNT_INCOMPATIBLE")

    if (
        subject.is_remake is not None
        and candidate.is_remake is not None
        and subject.is_remake != candidate.is_remake
    ):
        найдено.append("ORIGINAL_VS_REMAKE")

    расхождения = 0
    for свой, чужой in ((subject.country, candidate.country), (subject.studio, candidate.studio)):
        if свой and чужой and ключ_поиска(свой) != ключ_поиска(чужой):
            расхождения += 1
    if subject.creators and candidate.creators:
        свои = {ключ_поиска(c) for c in subject.creators}
        чужие = {ключ_поиска(c) for c in candidate.creators}
        if свои and чужие and not (свои & чужие):
            расхождения += 1
    # Одно расхождение — это разные написания или разный уровень
    # подробностей. Два и больше — это другое произведение.
    if расхождения >= 2:
        найдено.append("ORIGIN_DIFFERS")

    return найдено


def score(subject: Subject, candidate: Candidate, config: dict) -> MatchScore:
    """Объяснимая оценка одной пары."""
    веса = config["weights"]
    доп = config.get("tolerances") or {}
    порог_названия = float(доп.get("title_similarity", 0.90))
    признаки: list[FeatureScore] = []
    #: Совпало ли название ТОЧНО, а не похоже. Различие решающее: похожесть —
    #: это признак, а не доказательство, и «Побег» с «Побеги» похожи на 0,91.
    точное: dict[str, bool] = {}

    def добавить(имя: str, ключ_веса: str, совпало: bool | None, detail: str = ""):
        признаки.append(FeatureScore(имя, float(веса.get(ключ_веса, 0.0)), совпало, detail))

    общие = set(subject.external_ids) & set(candidate.external_ids)
    if общие:
        совпали = [
            k for k in общие if str(subject.external_ids[k]) == str(candidate.external_ids[k])
        ]
        добавить(
            "external_id",
            "external_id",
            bool(совпали),
            f"совпали: {sorted(совпали)}" if совпали else f"разошлись: {sorted(общие)}",
        )
    else:
        добавить("external_id", "external_id", None, "общих источников нет")

    for имя, ключ_веса, свой, чужой in (
        ("original_title", "original_title", subject.original_title, candidate.original_title),
    ):
        if свой and чужой:
            s = похожесть(свой, чужой)
            точное["original_title"] = s >= 1.0
            добавить(имя, ключ_веса, s >= порог_названия, f"похожесть {s:.2f}")
        else:
            добавить(имя, ключ_веса, None, "нет с одной из сторон")

    свои_альт = tuple(t for t in (subject.alternative_titles or ()) if t)
    чужие_альт = tuple(t for t in (candidate.alternative_titles or ()) if t)
    if свои_альт and чужие_альт:
        лучшая = max(похожесть(a, b) for a in свои_альт for b in чужие_альт)
        точное["alternative_title"] = лучшая >= 1.0
        добавить(
            "alternative_title",
            "alternative_title",
            лучшая >= порог_названия,
            f"лучшая похожесть {лучшая:.2f}",
        )
    else:
        добавить("alternative_title", "alternative_title", None, "нет с одной из сторон")

    if subject.release_year and candidate.release_year:
        разница = abs(subject.release_year - candidate.release_year)
        добавить("year", "year", разница <= int(доп.get("year_slack", 1)), f"разница {разница}")
    else:
        добавить("year", "year", None, "год отсутствует")

    if (
        subject.content_kind
        and candidate.content_kind
        and ContentKind.UNKNOWN not in (subject.content_kind, candidate.content_kind)
    ):
        добавить(
            "content_kind",
            "content_kind",
            subject.content_kind is candidate.content_kind,
            f"{subject.content_kind.value} / {candidate.content_kind.value}",
        )
    else:
        добавить("content_kind", "content_kind", None, "вид не установлен")

    if subject.duration and candidate.duration:
        дельта = abs(subject.duration - candidate.duration)
        допуск = max(
            float(доп.get("duration_absolute_minutes", 5)),
            float(доп.get("duration_percent", 0.10)) * max(subject.duration, candidate.duration),
        )
        добавить(
            "duration",
            "duration",
            дельта <= допуск,
            f"дельта {дельта} мин при допуске {допуск:.1f}",
        )
    else:
        добавить("duration", "duration", None, "длительность не измерена")

    if subject.episode_count and candidate.episode_count:
        дельта = abs(subject.episode_count - candidate.episode_count)
        добавить(
            "episode_count",
            "episode_count",
            дельта <= int(доп.get("episode_count_slack", 1)),
            f"дельта {дельта}",
        )
    else:
        добавить("episode_count", "episode_count", None, "число эпизодов неизвестно")

    for имя, свой, чужой in (
        ("country", subject.country, candidate.country),
        ("studio", subject.studio, candidate.studio),
    ):
        if свой and чужой:
            добавить(имя, имя, ключ_поиска(свой) == ключ_поиска(чужой), f"{свой} / {чужой}")
        else:
            добавить(имя, имя, None, "нет с одной из сторон")

    if subject.creators and candidate.creators:
        свои = {ключ_поиска(c) for c in subject.creators}
        чужие = {ключ_поиска(c) for c in candidate.creators}
        пересечение = свои & чужие
        добавить("creators", "creators", bool(пересечение), f"общих {len(пересечение)}")
    else:
        добавить("creators", "creators", None, "нет с одной из сторон")

    применимые = [f for f in признаки if f.applicable]
    делитель = sum(f.weight for f in применимые)
    набрано = sum(f.weight for f in применимые if f.matched)
    уверенность = (набрано / делитель) if делитель else 0.0

    return MatchScore(
        candidate_id=candidate.entity_id,
        confidence=уверенность,
        features=признаки,
        conflicts=hard_conflicts(subject, candidate, config),
        matched_features=sum(1 for f in применимые if f.matched),
        exact_title=any(точное.values()),
    )


@dataclasses.dataclass
class Resolution:
    status: IdentityStatus
    method: MappingMethod
    confidence: float
    conflicts: tuple[str, ...]
    chosen: MatchScore | None
    runner_up: MatchScore | None = None
    considered: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "identityStatus": self.status.value,
            "mappingMethod": self.method.value,
            "mappingConfidence": round(self.confidence, 4),
            "conflictState": list(self.conflicts),
            "consideredCandidates": self.considered,
            "chosen": self.chosen.as_dict() if self.chosen else None,
            "runnerUp": self.runner_up.as_dict() if self.runner_up else None,
        }


def _метод(лучший: MatchScore, subject: Subject, кандидат: Candidate) -> MappingMethod:
    """Каким признаком сопоставление, собственно, держится."""
    по_имени = {f.feature: f for f in лучший.features}
    if по_имени["external_id"].matched:
        return MappingMethod.EXACT_EXTERNAL_ID
    if (
        subject.provider_asset_id
        and кандидат.provider_asset_id
        and subject.provider_asset_id == кандидат.provider_asset_id
    ):
        return MappingMethod.EXACT_PROVIDER_ASSET_ID
    if (
        по_имени["original_title"].matched
        and по_имени["year"].matched
        and по_имени["content_kind"].matched
    ):
        return MappingMethod.ORIGINAL_TITLE_YEAR_KIND
    if по_имени["alternative_title"].matched and по_имени["year"].matched:
        return MappingMethod.ALTERNATIVE_TITLE_YEAR_PLUS
    return MappingMethod.NORMALIZED_TITLE_YEAR_PLUS


def _доказательств_хватает(лучший: MatchScore, config: dict) -> bool:
    """Достаточно ли оснований для автоматической привязки.

    Оценка сама по себе этого не показывает. Доля считается от применимых
    признаков, и запись, у которой применим ровно один, получает 1,0 при
    единственном совпадении — на adversarial-наборе так привязывалась запись
    без года к записи с годом по одному лишь названию.

    Два правила, каждое найдено этим набором:

    * совпавших признаков должно быть не меньше указанного в настройке;
    * название обязано совпасть ТОЧНО либо должен совпасть внешний
      идентификатор. Похожесть 0,91 у «Побег» и «Побеги» — это основание
      посмотреть, а не привязать.
    """
    правила = config.get("evidence") or {}
    минимум = int(правила.get("min_matched_features_for_auto", 3))
    if лучший.matched_features < минимум:
        return False
    if not правила.get("require_exact_title_or_external_id_for_auto", True):
        return True
    по_имени = {f.feature: f for f in лучший.features}
    if по_имени.get("external_id") and по_имени["external_id"].matched:
        return True
    return лучший.exact_title


def resolve(subject: Subject, candidates, config: dict) -> Resolution:
    """Итог сопоставления. Автоматический выбор только при явном превосходстве."""
    пороги = config["thresholds"]
    авто = float(пороги["auto_accept"])
    ревью = float(пороги["review"])
    зазор = float(пороги["ambiguity_margin"])

    кандидаты = list(candidates or ())
    if not кандидаты:
        return Resolution(IdentityStatus.UNMATCHED, MappingMethod.NONE, 0.0, (), None, considered=0)

    оценки = [(к, score(subject, к, config)) for к in кандидаты]
    открытые = [(к, s) for к, s in оценки if not s.blocked]
    закрытые = [s for _, s in оценки if s.blocked]

    if not открытые:
        # Все кандидаты закрыты противоречиями. Это не «не нашли»: нашли и
        # отвергли, и причины обязаны сохраниться.
        причины = sorted({c for s in закрытые for c in s.conflicts})
        лучший = max(закрытые, key=lambda s: s.confidence)
        return Resolution(
            IdentityStatus.CONFLICTED,
            MappingMethod.NONE,
            лучший.confidence,
            tuple(причины),
            лучший,
            considered=len(кандидаты),
        )

    открытые.sort(key=lambda пара: пара[1].confidence, reverse=True)

    # Первая ступень лестницы: точный внешний идентификатор решает сам.
    #
    # Совокупная оценка здесь не годится. Идентификатор поставщика — это ключ
    # записи у источника, а не признак среди прочих: расхождение в написании
    # страны («USSR» и «СССР») опускало оценку до 0,956 и отправляло в разбор
    # запись, у которой совпал kp-идентификатор. Противоречия при этом уже
    # отфильтрованы: кандидат с ДРУГИМ значением того же идентификатора сюда
    # не доходит — его закрывает EXTERNAL_ID_DIFFERS.
    по_id = [
        (к, s)
        for к, s in открытые
        if any(f.feature == "external_id" and f.matched for f in s.features)
    ]
    if len(по_id) == 1:
        кандидат, лучший = по_id[0]
        прочие = [s for _, s in открытые if s is not лучший]
        return Resolution(
            IdentityStatus.RESOLVED_EXACT_ID,
            MappingMethod.EXACT_EXTERNAL_ID,
            лучший.confidence,
            (),
            лучший,
            прочие[0] if прочие else None,
            considered=len(кандидаты),
        )
    if len(по_id) > 1:
        # Два кандидата с одним и тем же внешним идентификатором — это
        # рассогласование источника, а не выбор между ними.
        лучший = по_id[0][1]
        return Resolution(
            IdentityStatus.AMBIGUOUS,
            MappingMethod.MANUAL_QUEUE,
            лучший.confidence,
            (),
            лучший,
            по_id[1][1],
            considered=len(кандидаты),
        )

    (кандидат, лучший) = открытые[0]
    второй = открытые[1][1] if len(открытые) > 1 else None

    if второй is not None and (лучший.confidence - второй.confidence) < зазор:
        return Resolution(
            IdentityStatus.AMBIGUOUS,
            MappingMethod.MANUAL_QUEUE,
            лучший.confidence,
            (),
            лучший,
            второй,
            considered=len(кандидаты),
        )

    достаточно = _доказательств_хватает(лучший, config)
    if лучший.confidence >= авто and достаточно:
        метод = _метод(лучший, subject, кандидат)
        статус = (
            IdentityStatus.RESOLVED_EXACT_ID
            if метод in (MappingMethod.EXACT_EXTERNAL_ID, MappingMethod.EXACT_PROVIDER_ASSET_ID)
            else IdentityStatus.RESOLVED_HIGH_CONFIDENCE
        )
        return Resolution(
            статус, метод, лучший.confidence, (), лучший, второй, considered=len(кандидаты)
        )

    if лучший.confidence >= ревью:
        return Resolution(
            IdentityStatus.AMBIGUOUS,
            MappingMethod.MANUAL_QUEUE,
            лучший.confidence,
            (),
            лучший,
            второй,
            considered=len(кандидаты),
        )

    return Resolution(
        IdentityStatus.UNMATCHED,
        MappingMethod.NONE,
        лучший.confidence,
        (),
        лучший,
        второй,
        considered=len(кандидаты),
    )
