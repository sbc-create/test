"""Установление вида произведения по данным самого каталога.

Отдельный модуль, потому что здесь решается вопрос, который до сих пор решался
на витрине и решался неверно: какой вид у записи, если поставщик знает только
«фильм» и «сериал».

Измерено на боевом каталоге 2026-09-05 (53 229 записей): поле `type`
принимает ровно два значения, `movie` (32 918) и `tv` (20 311). При этом 332
записи несут свой настоящий вид в тегах — `ona` 257, `ova` 44, `special` 31, —
и **все 332** с двоичным `type` расходятся.

Правило разрешения одно и оно осторожное:

* тег уточняет `type`, если они из одной группы (ONA у `tv` — это тот же
  эпизодический вид, только точнее). Уточнение принимается;
* тег противоречит `type`, если группы разные (ONA у `movie`). Тогда вид
  остаётся UNKNOWN, а запись уходит в разбор. Автоматически не выбирается
  ничего: «Чаша снега» помечена `movie` и `ona` одновременно, и решать, что
  из этого правда, по весу тега — значит угадывать.

Отсутствие сезонов видом не является. Слово «anime» тоже: это способ
исполнения, и оно попадает в отдельный признак.
"""

from __future__ import annotations

import dataclasses

from factory.site_engine.content_kind import (
    ALIASES,
    KIND_TAGS,
    ContentKind,
    is_animation_marker,
    normalise_alias,
)

_ЭПИЗОДИЧЕСКИЕ = frozenset(
    {
        ContentKind.SERIES,
        ContentKind.MINISERIES,
        ContentKind.OVA,
        ContentKind.OAD,
        ContentKind.ONA,
        ContentKind.SEASON,
        ContentKind.EPISODE,
    }
)
_ЕДИНИЧНЫЕ = frozenset(
    {
        ContentKind.MOVIE,
        ContentKind.SHORT,
        ContentKind.DOCUMENTARY,
        ContentKind.MUSIC,
        ContentKind.SPECIAL,
    }
)


@dataclasses.dataclass
class KindDecision:
    """Итог установления вида и то, чем он подтверждён."""

    kind: ContentKind
    is_animation: bool | None
    #: Что сказал поставщик своим полем type.
    provider_kind: ContentKind
    #: Что сказали теги, если сказали.
    tag_kinds: tuple[ContentKind, ...] = ()
    conflicts: tuple[str, ...] = ()
    confidence: float = 0.0
    reason: str = ""

    @property
    def conflicted(self) -> bool:
        return bool(self.conflicts)


def _группа(kind: ContentKind):
    if kind in _ЭПИЗОДИЧЕСКИЕ:
        return "episodic"
    if kind in _ЕДИНИЧНЫЕ:
        return "single"
    return None


def decide(*, provider_type: str | None, tags=(), episode_count: int | None = None) -> KindDecision:
    """Вид произведения по записи каталога. Ничего не додумывает."""
    поставщик = ALIASES.get(normalise_alias(str(provider_type or "")), ContentKind.UNKNOWN)
    метки = [str(t) for t in (tags or ())]
    анимация = any(is_animation_marker(t) for t in метки) or None
    виды = tuple(
        dict.fromkeys(
            KIND_TAGS[normalise_alias(t)] for t in метки if normalise_alias(t) in KIND_TAGS
        )
    )

    if not виды:
        if поставщик is ContentKind.UNKNOWN:
            return KindDecision(
                ContentKind.UNKNOWN,
                анимация,
                поставщик,
                reason="поставщик не назвал тип, тегов вида нет",
            )
        return KindDecision(
            поставщик,
            анимация,
            поставщик,
            confidence=1.0,
            reason="тип поставщика без уточняющих тегов",
        )

    if len(виды) > 1:
        # Два разных вида в тегах одной записи. Выбирать «более вероятный»
        # нечем: у источника нет приоритета между ними.
        return KindDecision(
            ContentKind.UNKNOWN,
            анимация,
            поставщик,
            виды,
            conflicts=("MULTIPLE_KIND_TAGS",),
            reason="в тегах больше одного вида: " + ", ".join(k.value for k in виды),
        )

    (тег,) = виды
    if поставщик is ContentKind.UNKNOWN:
        return KindDecision(
            тег,
            анимация,
            поставщик,
            виды,
            confidence=0.9,
            reason="вид взят из тега, тип поставщика отсутствует",
        )

    if _группа(тег) == _группа(поставщик):
        # Тег точнее: ONA — это тот же эпизодический вид, но названный точно.
        return KindDecision(
            тег,
            анимация,
            поставщик,
            виды,
            confidence=1.0,
            reason=f"тег {тег.value} уточняет тип поставщика "
            f"{поставщик.value} внутри одной группы",
        )

    return KindDecision(
        ContentKind.UNKNOWN,
        анимация,
        поставщик,
        виды,
        conflicts=("PROVIDER_TYPE_VS_KIND_TAG",),
        confidence=0.0,
        reason=f"тип поставщика {поставщик.value} и тег {тег.value} из разных "
        f"групп: эпизодический против единичного. Выбор без внешнего "
        f"источника был бы угадыванием",
    )
