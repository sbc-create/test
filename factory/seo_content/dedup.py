"""Уникальность и каннибализация.

Задача здесь не «пройти проверку уникальности». Девять витрин с тем же
каталогом и слегка переставленными словами не образуют девяти независимых
ценностей, и обмануть измеритель значило бы обмануть себя. Поэтому набор
методов подобран так, чтобы поймать именно переписывание: точное совпадение
ловит копию, нормализованное — копию с другой пунктуацией, маскирование
названия — межсайтовый шаблон, в котором поменяли одно слово.

Отдельно измеряется повторяющееся вступление. Одинаковое начало у всего
корпуса — признак того, что текстов много, а сведений мало.

Локальные embeddings в окружении отсутствуют. Семантическая близость
поэтому НЕ измеряется и не объявляется измеренной: соответствующий порог
возвращается со статусом `NOT_EVALUATED`, а не с нулём.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping, Sequence

from . import lexicon as LEX

#: Длина совпадающей цепочки слов, начиная с которой совпадение считается
#: заимствованием, а не совпадением языка.
ПОРОГ_ЦЕПОЧКИ = 12
ПОРОГ_JACCARD_5GRAM = 0.85
ПОРОГ_SEMANTIC = 0.92
ПОРОГ_SIMHASH_БИТ = 6          # расстояние Хэмминга, ниже которого — близнецы
ДОЛЯ_ОДИНАКОВЫХ_ВСТУПЛЕНИЙ = 0.02
СЛОВ_ВО_ВСТУПЛЕНИИ = 6


def нормализовать(текст: str) -> str:
    """Форма, в которой различаются слова, а не пунктуация и регистр."""
    т = (текст or "").lower().replace("ё", "е")
    т = re.sub(r"[^\w\s]", " ", т, flags=re.U)
    return re.sub(r"\s+", " ", т).strip()


def слова(текст: str) -> list[str]:
    return нормализовать(текст).split()


def exact_hash(текст: str) -> str:
    return hashlib.sha256((текст or "").encode("utf-8")).hexdigest()


def normalized_hash(текст: str) -> str:
    return hashlib.sha256(нормализовать(текст).encode("utf-8")).hexdigest()


def stem_hash(текст: str) -> str:
    """Отпечаток по основам слов: ловит замену окончаний и порядка форм."""
    основы = sorted(LEX.стемы(текст))
    return hashlib.sha256(" ".join(основы).encode("utf-8")).hexdigest()


# --- char 5-граммы ---------------------------------------------------------

def char_ngrams(текст: str, n: int = 5) -> set[str]:
    т = нормализовать(текст)
    if len(т) < n:
        return {т} if т else set()
    return {т[i:i + n] for i in range(len(т) - n + 1)}


def jaccard(а: set, б: set) -> float:
    if not а and not б:
        return 1.0
    if not а or not б:
        return 0.0
    return len(а & б) / len(а | б)


# --- MinHash ---------------------------------------------------------------

_МАСКА = (1 << 64) - 1


def _хэш(шингл: str, соль: int) -> int:
    сырое = hashlib.blake2b(f"{соль}\x1f{шингл}".encode("utf-8"),
                            digest_size=8).digest()
    return int.from_bytes(сырое, "big")


def minhash(текст: str, k: int = 64, n: int = 5) -> tuple[int, ...]:
    шинглы = char_ngrams(текст, n)
    if not шинглы:
        return tuple([_МАСКА] * k)
    return tuple(min(_хэш(ш, соль) for ш in шинглы) for соль in range(k))


def minhash_similarity(а: Sequence[int], б: Sequence[int]) -> float:
    if not а or len(а) != len(б):
        return 0.0
    return sum(1 for x, y in zip(а, б) if x == y) / len(а)


# --- SimHash ---------------------------------------------------------------

def simhash(текст: str, бит: int = 64) -> int:
    вектор = [0] * бит
    токены = слова(текст)
    if not токены:
        return 0
    for т in токены:
        х = int.from_bytes(hashlib.blake2b(т.encode(), digest_size=8).digest(),
                           "big")
        for i in range(бит):
            вектор[i] += 1 if (х >> i) & 1 else -1
    итог = 0
    for i in range(бит):
        if вектор[i] > 0:
            итог |= 1 << i
    return итог


def hamming(а: int, б: int) -> int:
    return bin(а ^ б).count("1")


# --- совпадающие цепочки ---------------------------------------------------

def longest_common_run(а: str, б: str) -> tuple[int, str]:
    """Самая длинная общая цепочка слов и она сама."""
    сл_а, сл_б = слова(а), слова(б)
    if not сл_а or not сл_б:
        return 0, ""
    м = SequenceMatcher(None, сл_а, сл_б, autojunk=False)
    лучший = м.find_longest_match(0, len(сл_а), 0, len(сл_б))
    return лучший.size, " ".join(сл_а[лучший.a:лучший.a + лучший.size])


def sequence_ratio(а: str, б: str) -> float:
    return SequenceMatcher(None, нормализовать(а), нормализовать(б),
                           autojunk=False).ratio()


# --- маскирование личности -------------------------------------------------

def mask_identity(текст: str, *, names: Iterable[str]) -> str:
    """Заменить собственные имена сущности на метку.

    Так проверяется главный способ подделать уникальность: взять чужой текст
    и поменять название. После маскирования оба текста становятся одним, и
    совпадение видно.
    """
    т = текст or ""
    for имя in sorted({str(и) for и in names if и}, key=len, reverse=True):
        if len(имя) < 3:
            continue
        т = re.sub(re.escape(имя), "〈ИМЯ〉", т, flags=re.I)
        # Отдельно — основа, чтобы «Бункера» тоже попало под маску.
        основа = LEX.стем(имя.split()[0]) if имя.split() else ""
        if len(основа) >= 4:
            т = re.sub(rf"\b{re.escape(основа)}\w*", "〈ИМЯ〉", т, flags=re.I)
    return re.sub(r"\b\d{1,4}\b", "〈ЧИСЛО〉", т)


# --- корпус ----------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CorpusEntry:
    """Одна запись корпуса, с которой сравнивается кандидат."""

    entry_id: str
    site_id: str
    entity_type: str
    entity_id: str
    text: str
    franchise_id: str | None = None
    #: `approved` — одобренный текст витрины, `source` — исходный источник,
    #: `page_body` — основной текст страницы, `note` — редакционная заметка.
    kind: str = "approved"
    names: tuple[str, ...] = ()
    indexable: bool = True


@dataclass
class DuplicateFinding:
    method: str
    entry_id: str
    site_id: str
    entity_id: str
    score: float
    detail: str
    severity: str  # BLOCK | REVIEW | INFO

    def to_dict(self) -> dict[str, Any]:
        return {"method": self.method, "entry_id": self.entry_id,
                "site_id": self.site_id, "entity_id": self.entity_id,
                "score": round(self.score, 4), "detail": self.detail,
                "severity": self.severity}


@dataclass
class UniquenessReport:
    findings: list[DuplicateFinding] = field(default_factory=list)
    exact_duplicates: int = 0
    normalized_duplicates: int = 0
    long_run_matches: int = 0
    cross_site_template_copies: int = 0
    review_required: int = 0
    #: Семантическая близость не измерялась — локальных embeddings нет.
    semantic_status: str = "NOT_EVALUATED"
    semantic_reason: str = ("локальные embeddings в окружении отсутствуют; "
                            "порог 0,92 не измерялся и не объявляется пройденным")
    doorway_risk: str = "NONE"
    doorway_detail: str = ""

    @property
    def blocked(self) -> bool:
        return any(f.severity == "BLOCK" for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"exact_duplicates": self.exact_duplicates,
                "normalized_duplicates": self.normalized_duplicates,
                "long_run_matches": self.long_run_matches,
                "cross_site_template_copies": self.cross_site_template_copies,
                "review_required": self.review_required,
                "semantic_status": self.semantic_status,
                "semantic_reason": self.semantic_reason,
                "doorway_risk": self.doorway_risk,
                "doorway_detail": self.doorway_detail,
                "blocked": self.blocked,
                "findings": [f.to_dict() for f in self.findings]}


class NearDuplicateDetector:
    """Несколько независимых измерителей вместо одного «процента уникальности».

    Один измеритель обмануть легко и незаметно. Здесь совпадение должно
    пережить точное сравнение, нормализованное, сравнение основ, пятисимвольные
    n-граммы, MinHash, SimHash и маскирование имён — и каждый из них смотрит
    на текст по-своему.
    """

    def __init__(self, корпус: Sequence[CorpusEntry]):
        self.корпус = list(корпус)
        self._индекс = {
            з.entry_id: {
                "exact": exact_hash(з.text),
                "norm": normalized_hash(з.text),
                "stem": stem_hash(з.text),
                "5gram": char_ngrams(з.text),
                "minhash": minhash(з.text),
                "simhash": simhash(з.text),
                "masked": нормализовать(mask_identity(з.text, names=з.names)),
            } for з in self.корпус}

    def add(self, запись: CorpusEntry) -> None:
        """Пополнить корпус уже принятым текстом.

        Нужно ровно затем, чтобы следующий кандидат сравнивался с тем, что мы
        только что приняли, а не только с тем, что лежало до начала прогона.
        """
        self.корпус.append(запись)
        self._индекс[запись.entry_id] = {
            "exact": exact_hash(запись.text),
            "norm": normalized_hash(запись.text),
            "stem": stem_hash(запись.text),
            "5gram": char_ngrams(запись.text),
            "minhash": minhash(запись.text),
            "simhash": simhash(запись.text),
            "masked": нормализовать(mask_identity(запись.text,
                                                  names=запись.names)),
        }

    def check(self, текст: str, *, site_id: str, entity_id: str,
              names: Iterable[str] = (), franchise_id: str | None = None,
              allowed_titles: Iterable[str] = ()) -> UniquenessReport:
        отчёт = UniquenessReport()
        если_пусто = (текст or "").strip()
        if not если_пусто:
            return отчёт

        мой = {"exact": exact_hash(текст), "norm": normalized_hash(текст),
               "stem": stem_hash(текст), "5gram": char_ngrams(текст),
               "minhash": minhash(текст), "simhash": simhash(текст),
               "masked": нормализовать(mask_identity(текст, names=names))}
        разрешённые_цепочки = {нормализовать(т) for т in allowed_titles if т}

        for запись in self.корпус:
            if запись.site_id == site_id and запись.entity_id == entity_id \
                    and запись.kind == "approved":
                continue  # своя же одобренная ревизия — не дубль
            и = self._индекс[запись.entry_id]
            своя_сущность = (запись.site_id == site_id
                             and запись.entity_id == entity_id)

            if мой["exact"] == и["exact"]:
                отчёт.exact_duplicates += 1
                отчёт.findings.append(DuplicateFinding(
                    "exact", запись.entry_id, запись.site_id, запись.entity_id,
                    1.0, "побайтовое совпадение", "BLOCK"))
                continue
            if мой["norm"] == и["norm"]:
                отчёт.normalized_duplicates += 1
                отчёт.findings.append(DuplicateFinding(
                    "normalized", запись.entry_id, запись.site_id,
                    запись.entity_id, 1.0,
                    "совпадение после снятия регистра и пунктуации", "BLOCK"))
                continue
            if мой["stem"] == и["stem"]:
                отчёт.normalized_duplicates += 1
                отчёт.findings.append(DuplicateFinding(
                    "stem", запись.entry_id, запись.site_id, запись.entity_id,
                    1.0, "совпадение по основам слов: переставлены формы",
                    "BLOCK"))
                continue

            # Межсайтовая копия с заменой названия.
            if мой["masked"] and мой["masked"] == и["masked"]:
                отчёт.cross_site_template_copies += 1
                отчёт.findings.append(DuplicateFinding(
                    "masked_identity", запись.entry_id, запись.site_id,
                    запись.entity_id, 1.0,
                    "после маскирования имён и чисел тексты совпали: это одна "
                    "болванка с подставленным названием", "BLOCK"))
                continue

            длина, цепочка = longest_common_run(текст, запись.text)
            if длина >= ПОРОГ_ЦЕПОЧКИ and нормализовать(цепочка) not in \
                    разрешённые_цепочки:
                отчёт.long_run_matches += 1
                отчёт.findings.append(DuplicateFinding(
                    "word_run", запись.entry_id, запись.site_id,
                    запись.entity_id, float(длина),
                    f"совпадает цепочка из {длина} слов: «{цепочка[:90]}»",
                    "BLOCK"))
                continue

            j = jaccard(мой["5gram"], и["5gram"])
            if j >= ПОРОГ_JACCARD_5GRAM and not своя_сущность:
                отчёт.review_required += 1
                отчёт.findings.append(DuplicateFinding(
                    "char_5gram_jaccard", запись.entry_id, запись.site_id,
                    запись.entity_id, j,
                    f"разные сущности, близость 5-грамм {j:.3f} ≥ "
                    f"{ПОРОГ_JACCARD_5GRAM}", "REVIEW"))
                continue

            m = minhash_similarity(мой["minhash"], и["minhash"])
            h = hamming(мой["simhash"], и["simhash"])
            if (m >= ПОРОГ_JACCARD_5GRAM or h <= ПОРОГ_SIMHASH_БИТ) and \
                    not своя_сущность:
                отчёт.review_required += 1
                отчёт.findings.append(DuplicateFinding(
                    "minhash_simhash", запись.entry_id, запись.site_id,
                    запись.entity_id, max(m, 1 - h / 64),
                    f"MinHash {m:.3f}, SimHash расстояние {h}", "REVIEW"))

        return отчёт


# --- повторяющиеся вступления ---------------------------------------------

#: Длина вступления в символах, а не в словах.
#:
#: Шесть слов обрезают название посередине: «Серия 1 1-го сезона „Талая…"» и
#: «…„Талая гать"» дают одно и то же начало, хотя называют разные вещи. Мера
#: в символах доводит окно до конца названия и перестаёт считать разные
#: произведения одинаковым вступлением.
СИМВОЛОВ_ВО_ВСТУПЛЕНИИ = 60


def opening(текст: str, символов: int = СИМВОЛОВ_ВО_ВСТУПЛЕНИИ) -> str:
    return нормализовать(текст)[:символов]


def ending(текст: str, символов: int = СИМВОЛОВ_ВО_ВСТУПЛЕНИИ) -> str:
    н = нормализовать(текст)
    return н[-символов:] if н else ""


def opening_frame(текст: str, *, names=(),
                  символов: int = СИМВОЛОВ_ВО_ВСТУПЛЕНИИ) -> str:
    """Вступление без имён и чисел — то есть сама обвязка.

    Более требовательная мера, чем `opening`: она спрашивает не «одинаков ли
    текст начала», а «одинакова ли рамка». У страниц серий рамка одинакова по
    устройству — описание серии начинается с названия, сезона и номера, и
    честного способа это разнообразить нет. Поэтому мера считается и
    показывается отдельно, а бюджет в два процента остаётся за `opening`.
    """
    return нормализовать(mask_identity(текст, names=names))[:символов]


@dataclass
class CorpusPatternReport:
    total: int
    repeated_opening_rate: float
    repeated_ending_rate: float
    top_openings: list[tuple[str, int]]
    top_endings: list[tuple[str, int]]
    within_budget: bool
    repeated_frame_rate: float = 0.0
    top_frames: list[tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"total": self.total,
                "repeated_opening_rate": round(self.repeated_opening_rate, 4),
                "repeated_ending_rate": round(self.repeated_ending_rate, 4),
                "repeated_frame_rate": round(self.repeated_frame_rate, 4),
                "top_openings": self.top_openings[:5],
                "top_endings": self.top_endings[:5],
                "top_frames": self.top_frames[:5],
                "budget": ДОЛЯ_ОДИНАКОВЫХ_ВСТУПЛЕНИЙ,
                "within_budget": self.within_budget,
                "frame_note": (
                    "repeated_frame_rate — вступление после снятия имён и "
                    "чисел. Бюджет 2% относится к repeated_opening_rate; "
                    "рамка показана отдельно и у страниц серий одинакова по "
                    "устройству")}


def corpus_patterns(тексты: Sequence[str],
                    names_by_index: Sequence[Sequence[str]] = ()
                    ) -> CorpusPatternReport:
    """Доля корпуса, начинающаяся и заканчивающаяся одинаково.

    Считается доля текстов, попавших в группу размером больше одного: один
    одинаковый зачин у двух текстов из ста — это два процента корпуса, а не
    один случай.
    """
    всего = len(тексты)
    if всего == 0:
        return CorpusPatternReport(0, 0.0, 0.0, [], [], True)
    from collections import Counter
    зачины = Counter(opening(т) for т in тексты if (т or "").strip())
    концовки = Counter(ending(т) for т in тексты if (т or "").strip())
    повтор_з = sum(n for _, n in зачины.items() if n > 1)
    повтор_к = sum(n for _, n in концовки.items() if n > 1)
    доля_з, доля_к = повтор_з / всего, повтор_к / всего
    рамки = Counter(
        opening_frame(т, names=(names_by_index[i] if i < len(names_by_index)
                                else ()))
        for i, т in enumerate(тексты) if (т or "").strip())
    повтор_р = sum(n for _, n in рамки.items() if n > 1)
    return CorpusPatternReport(
        всего, доля_з, доля_к,
        [(з, n) for з, n in зачины.most_common() if n > 1],
        [(к, n) for к, n in концовки.most_common() if n > 1],
        доля_з <= ДОЛЯ_ОДИНАКОВЫХ_ВСТУПЛЕНИЙ,
        повтор_р / всего,
        [(р, n) for р, n in рамки.most_common() if n > 1])


# --- doorway / scaled content ---------------------------------------------

def doorway_risk(*, site_id: str, own_angle: str | None,
                 sibling_sites: Sequence[str],
                 same_catalog: bool) -> tuple[str, str]:
    """Есть ли у витрины собственный смысл, кроме повторения каталога.

    Ответ не про текст, а про устройство сети. Если у сайта нет своего угла
    и каталог тот же, механический рерайт ничего не создаёт — честнее
    канонизировать или закрыть от индексации, и здесь это и рекомендуется.
    """
    if own_angle and own_angle.strip():
        return "NONE", f"{site_id}: объявлен собственный угол — {own_angle}"
    if same_catalog and len(sibling_sites) >= 1:
        return ("HIGH",
                f"{site_id}: тот же каталог, что у {len(sibling_sites)} "
                f"соседних витрин, и собственного информационного угла нет. "
                f"Рерайт не создаёт ценности; уместны канонизация на одну "
                f"витрину либо noindex")
    return ("MEDIUM",
            f"{site_id}: собственный угол не объявлен; ценность страницы "
            f"держится только на фактах каталога")
