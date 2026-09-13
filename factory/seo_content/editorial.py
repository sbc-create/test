"""Редакционная заметка — не отзыв и не комментарий пользователя.

Разница не в формулировке, а в природе записи. Отзыв утверждает чей-то опыт
и чьё-то мнение; у него есть автор-человек, время, оценка, ответы и лайки.
Ничего этого у нас нет и быть не может: сочинить их значило бы завести
несуществующего человека. Поэтому заметка не «помечена как редакционная» —
она устроена так, что персоны, оценки, времени просмотра и ответов у неё нет
физически: полей не существует, и попытка их прислать отклоняется.

Отсюда же запрет на разметку `Review` и `AggregateRating`: разметка — это
утверждение для машины, и утверждать машине, что модельный текст является
отзывом зрителя, нельзя ровно по той же причине, по которой нельзя написать
это человеку.

Настоящие пользовательские комментарии — отдельная будущая система с
происхождением актора, модерацией, антиспамом и `rel="ugc"` на внешних
ссылках. Здесь её нет, и подменять её этой сущностью нельзя.
"""
from __future__ import annotations

import dataclasses
import hashlib
import re
from typing import Any, Iterable, Mapping, Sequence

from .factpack import SEOFactPack, sha256_of

RESOURCE_KIND = "seo.editorial_note"
COMMENT_MODE = "EDITORIAL_COMMENTARY"
AUTHOR_TYPE = "EDITORIAL_AI"
SCHEMA_VERSION = "seo.editorial_note/1.0.0"

MAX_NOTES = 3

#: Поля, наличие которых превратило бы заметку в поддельный пользовательский
#: отзыв. Список закрыт и проверяется на входе.
ЗАПРЕЩЁННЫЕ_ПОЛЯ = frozenset({
    "author_name", "author_avatar", "user_id", "persona", "nickname",
    "rating", "rating_value", "stars", "score_by_user", "likes", "dislikes",
    "upvotes", "reply_to", "replies", "watched_at", "posted_at",
    "review_body", "reviewRating", "aggregateRating", "helpful_count",
})

#: Разметка, которой заметка не является ни при каких условиях.
ЗАПРЕЩЁННАЯ_РАЗМЕТКА = ("Review", "AggregateRating", "UserComments",
                        "Rating", "Comment")


class FakeUgcAttempt(ValueError):
    """Попытка выдать редакционную заметку за пользовательскую."""


@dataclasses.dataclass(frozen=True, slots=True)
class EditorialNote:
    """Одна заметка. Без автора-человека, оценки, времени и реакций."""

    note_id: str
    site_id: str
    entity_type: str
    entity_id: str
    locale: str
    text: str
    fact_refs: tuple[str, ...]
    angle: str                  # чем эта мысль отличается от прочих
    model_version: str
    prompt_version: str
    resource_kind: str = RESOURCE_KIND
    comment_mode: str = COMMENT_MODE
    author_type: str = AUTHOR_TYPE
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.fact_refs:
            raise FakeUgcAttempt(
                "заметка без ссылок на факты: полезная мысль обязана на чём-то "
                "стоять, иначе это украшение")
        if self.comment_mode != COMMENT_MODE or self.author_type != AUTHOR_TYPE:
            raise FakeUgcAttempt(
                "заметка объявляет себя не редакционной")

    @property
    def text_sha256(self) -> str:
        return hashlib.sha256(нормализовать(self.text).encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Словарь для записи и проверки по схеме.

        Кортеж превращается в список намеренно: JSON-схема знает только
        массив, и кортеж она отвергает — не как ошибку данных, а как ошибку
        сериализации, которую легко принять за первое.
        """
        д = dataclasses.asdict(self)
        д["fact_refs"] = list(self.fact_refs)
        return д


def нормализовать(текст: str) -> str:
    return re.sub(r"\s+", " ", (текст or "").strip().lower())


def reject_ugc_fields(сырое: Mapping[str, Any]) -> None:
    """Отклонить всё, что делает из заметки поддельный отзыв."""
    лишние = sorted(set(сырое) & ЗАПРЕЩЁННЫЕ_ПОЛЯ)
    if лишние:
        raise FakeUgcAttempt(
            "заметка не является пользовательским отзывом; присланы поля: "
            + ", ".join(лишние))


def reject_review_markup(разметка: Any) -> None:
    """Заметка не размечается как отзыв или агрегированный рейтинг."""
    текст = str(разметка)
    для_машины = [т for т in ЗАПРЕЩЁННАЯ_РАЗМЕТКА
                  if re.search(rf'"@type"\s*:\s*"{т}"', текст)]
    if для_машины:
        raise FakeUgcAttempt(
            "модельный текст размечен как " + ", ".join(для_машины)
            + ": это утверждение о существовании отзыва или оценки зрителя")


#: Обороты, выдающие выдуманный личный опыт. Заметка объясняет, а не вспоминает.
ЛИЧНЫЙ_ОПЫТ = (
    r"\bя\s+(?:смотрел|посмотрел|пересматрива|плакал|советую|рекомендую)",
    r"\bмне\s+(?:понравил|зашло|показалось)",
    r"\bмы\s+(?:посмотрели|смотрели)",
    r"\bнаш[аи]?\s+(?:редакци[яи]\s+)?(?:считает|полагает|рекомендует)",
    r"\bпо\s+моему\s+мнению\b",
    r"\bна\s+мой\s+взгляд\b",
    r"\bлично\s+(?:я|мне)\b",
)
_ЛИЧНЫЙ_ОПЫТ = tuple(re.compile(ш, re.I) for ш in ЛИЧНЫЙ_ОПЫТ)


def personal_experience_markers(текст: str) -> list[str]:
    return [ш.pattern for ш in _ЛИЧНЫЙ_ОПЫТ if ш.search(текст or "")]


@dataclasses.dataclass
class NotesReport:
    notes: list[EditorialNote] = dataclasses.field(default_factory=list)
    rejected: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"notes": [н.to_dict() for н in self.notes],
                "rejected": list(self.rejected),
                "auto_user_comments_created": 0, "fake_personas": 0,
                "fake_timestamps": 0, "fake_likes": 0, "fake_replies": 0,
                "model_reviews": 0, "model_ratings": 0}


def validate_notes(заметки: Sequence[EditorialNote], *, pack: SEOFactPack,
                   body: str | None, corpus_note_hashes: Iterable[str] = (),
                   allowed_spoiler: str = "NONE") -> NotesReport:
    """Отсеять заметки, которые не добавляют мысли или добавляют выдумку.

    Пустой результат — нормальный исход. Если новой полезной мысли нет,
    честно не писать её лучше, чем написать ради заполнения места.
    """
    отчёт = NotesReport()
    корпус = set(corpus_note_hashes)
    свои: set[str] = set()
    тело = нормализовать(body or "")
    известные = {ф.fact_id for ф in pack.facts}

    for н in заметки[:]:
        причины: list[str] = []
        if len(отчёт.notes) >= MAX_NOTES:
            причины.append("NOTE_LIMIT_EXCEEDED")
        чужие = [r for r in н.fact_refs if r not in известные]
        if чужие:
            причины.append(f"FACT_REF_UNKNOWN:{','.join(sorted(чужие))}")
        следы = personal_experience_markers(н.text)
        if следы:
            причины.append("INVENTED_PERSONAL_EXPERIENCE")
        н_норм = нормализовать(н.text)
        if тело and (н_норм in тело or тело in н_норм):
            причины.append("DUPLICATES_BODY")
        if н.text_sha256 in свои:
            причины.append("DUPLICATE_WITHIN_PACKAGE")
        if н.text_sha256 in корпус:
            причины.append("REPEATED_ACROSS_PAGES")
        if _спойлер_выше(н.text, pack, allowed_spoiler):
            причины.append("SPOILER_ABOVE_ALLOWED")
        if причины:
            отчёт.rejected.append({"note_id": н.note_id, "reasons": причины,
                                   "text": н.text})
            continue
        свои.add(н.text_sha256)
        отчёт.notes.append(н)
    return отчёт


#: Обороты, раскрывающие развязку. Точный разбор сюжета здесь невозможен, и
#: заявлять его было бы неправдой: проверяется явное называние исхода.
_РАЗВЯЗКА = re.compile(
    r"\b(?:в\s+финале|в\s+конце\s+(?:сезона|сериала|фильма)|погиба[ею]т|"
    r"умира[ею]т|оказывается\s+(?:предателем|отцом|братом)|"
    r"развязка\s+раскрывает)", re.I)


def _спойлер_выше(текст: str, pack: SEOFactPack, разрешено: str) -> bool:
    уровень = pack.value("/spoiler_level") or разрешено
    if str(уровень).upper() in ("FULL", "MIDPOINT"):
        return False
    return bool(_РАЗВЯЗКА.search(текст or ""))
