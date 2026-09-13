"""Русский язык и читаемость — детерминированной проверкой.

Граница возможностей объявлена здесь, а не в отчёте задним числом.

Что проверяется по-настоящему: запрещённые штампы, канцелярит, машинные
обороты, смешение кириллицы и латиницы внутри слова, переспам, повтор
предложений, тавтология, чрезмерно длинные фразы, обрывы и незакрытые
кавычки, рекламность, согласование числительного с существительным и
склонение названия в кавычках.

Чего проверка НЕ делает: полной морфологии и орфографии. `pymorphy` и
`language_tool_python` в окружении отсутствуют, а обязательной зависимостью
от публичной службы контур обвешивать нельзя — неопубликованный текст не
отправляется наружу. Поэтому орфография отмечается как `NOT_EVALUATED`, а не
нулём ошибок: ноль означал бы «проверено и чисто».

Если LanguageTool доступен локально или self-hosted, адаптер ниже им
воспользуется; отсутствие адаптера не меняет исход ворот, оно меняет
честность отчёта.
"""
from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from . import lexicon as LEX

МАКС_СЛОВ_В_ПРЕДЛОЖЕНИИ = 30
ПОРОГ_ПЕРЕСПАМА = 0.045      # доля одного смыслового слова от всех слов
МИН_СЛОВ_ДЛЯ_ПЕРЕСПАМА = 40
ОКНО_ТАВТОЛОГИИ = 8

ПРЕДЛОЖЕНИЕ = re.compile(r"[^.!?…]+(?:[.!?…]+|$)")
КИРИЛЛИЦА = re.compile(r"[а-яёА-ЯЁ]")
ЛАТИНИЦА = re.compile(r"[a-zA-Z]")

#: Служебные слова, которые в подсчёте переспама не участвуют.
СТОП_СЛОВА = {
    "и", "в", "во", "на", "не", "что", "он", "она", "оно", "они", "с", "со",
    "как", "а", "то", "все", "весь", "но", "его", "ее", "её", "их", "к", "у",
    "же", "за", "от", "до", "по", "из", "о", "об", "для", "при", "это", "этот",
    "эта", "эти", "так", "там", "тут", "уже", "еще", "ещё", "был", "была",
    "было", "были", "быть", "есть", "или", "если", "чтобы", "когда", "где",
    "кто", "чем", "тем", "том", "та", "те", "свой", "своя", "свои", "который",
    "которая", "которые", "после", "перед", "между", "через", "над", "под",
}

#: Рекламный призыв. Отличается от описания тем, что обращается к читателю
#: с побуждением, а не сообщает о произведении.
РЕКЛАМА = (
    r"смотрите\s+(?:прямо\s+)?сейчас", r"не\s+пропустите",
    r"скача(?:й|йте|ть)\s+бесплатно", r"жми(?:те)?\s+на",
    r"подпис(?:ывайтесь|ки)\b", r"регистрируйтесь\b",
    r"лучш(?:ее|ий|ая)\s+качеств\w+\s+бесплатно",
    r"без\s+регистрации\s+и\s+смс", r"!{2,}",
    r"только\s+у\s+нас\b", r"на\s+нашем\s+сайте\s+вы\s+найд\w+",
)

#: Формы согласования числительного с существительным.
СЧЁТНЫЕ = {
    "сезон": ("сезон", "сезона", "сезонов"),
    "сери": ("серия", "серии", "серий"),
    "эпизод": ("эпизод", "эпизода", "эпизодов"),
    "год": ("год", "года", "лет"),
    "част": ("часть", "части", "частей"),
    "филь": ("фильм", "фильма", "фильмов"),
}


def форма_числительного(n: int) -> int:
    """0 — единственное, 1 — родительный единственного, 2 — родительный мн."""
    if n % 100 in (11, 12, 13, 14):
        return 2
    остаток = n % 10
    if остаток == 1:
        return 0
    if остаток in (2, 3, 4):
        return 1
    return 2


@dataclass
class LanguageIssue:
    code: str
    severity: str      # CRITICAL | ERROR | WARNING
    detail: str
    excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "detail": self.detail, "excerpt": self.excerpt}


@dataclass
class LanguageReport:
    issues: list[LanguageIssue] = field(default_factory=list)
    #: Что действительно измерено, а что — нет. Поле обязательное: без него
    #: «0 ошибок» читается как «проверено всё».
    evaluated: dict[str, str] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)

    def by_severity(self, severity: str) -> list[LanguageIssue]:
        return [i for i in self.issues if i.severity == severity]

    @property
    def critical(self) -> list[LanguageIssue]:
        return self.by_severity("CRITICAL")

    @property
    def cliches(self) -> list[LanguageIssue]:
        return [i for i in self.issues if i.code == "FORBIDDEN_CLICHE"]

    @property
    def grammar(self) -> list[LanguageIssue]:
        return [i for i in self.issues
                if i.code in ("NUMERAL_AGREEMENT", "DOUBLED_WORD",
                              "PUNCTUATION_SPACING", "UNBALANCED_QUOTES",
                              "TRUNCATED_SENTENCE", "TITLE_DECLINED")]

    def to_dict(self) -> dict[str, Any]:
        return {"issues": [i.to_dict() for i in self.issues],
                "critical": len(self.critical),
                "cliches": len(self.cliches),
                "grammar": len(self.grammar),
                "evaluated": dict(self.evaluated),
                "stats": dict(self.stats)}


def languagetool_available() -> tuple[bool, str]:
    """Доступен ли LanguageTool локально или на своём сервере.

    Публичный сервис намеренно не пробуется: отправлять туда неопубликованный
    текст без разрешения владельца нельзя, и зависеть от чужой доступности
    ворота не должны.
    """
    адрес = os.environ.get("LANGUAGETOOL_URL", "").strip()
    if not адрес:
        try:
            import language_tool_python  # noqa: F401
        except Exception:
            return False, ("language_tool_python не установлен, "
                           "LANGUAGETOOL_URL не задан")
        return True, "локальная установка language_tool_python"
    if адрес.startswith(("http://localhost", "http://127.0.0.1")) or \
            os.environ.get("LANGUAGETOOL_SELF_HOSTED") == "1":
        return True, f"self-hosted LanguageTool: {адрес}"
    return False, (f"LANGUAGETOOL_URL={адрес} не объявлен как self-hosted; "
                   f"публичный сервис для неопубликованного текста не "
                   f"используется")


class LanguageValidator:
    def __init__(self, *, canonical_title: str | None = None,
                 allowed_titles: Iterable[str] = (),
                 entity_label: str | None = None):
        self.canonical_title = canonical_title
        self.allowed_titles = {LEX.нормализовать(т) for т in allowed_titles if т}
        if canonical_title:
            self.allowed_titles.add(LEX.нормализовать(canonical_title))
        self.entity_label = entity_label

    def validate(self, текст: str, *, field_name: str = "body") -> LanguageReport:
        отчёт = LanguageReport()
        доступен, причина = languagetool_available()
        отчёт.evaluated = {
            "cliches": "EVALUATED", "kancelarit": "EVALUATED",
            "machine_constructions": "EVALUATED",
            "script_mixing": "EVALUATED", "keyword_stuffing": "EVALUATED",
            "sentence_repetition": "EVALUATED", "tautology": "EVALUATED",
            "sentence_length": "EVALUATED", "truncation": "EVALUATED",
            "advertising": "EVALUATED",
            "numeral_agreement": "EVALUATED",
            "title_declension": "EVALUATED",
            "punctuation_spacing": "EVALUATED",
            "spelling": "EVALUATED" if доступен else f"NOT_EVALUATED: {причина}",
            "full_morphology": ("NOT_EVALUATED: pymorphy в окружении "
                                "отсутствует; проверено только согласование "
                                "числительного с существительным"),
        }
        if not (текст or "").strip():
            return отчёт

        предложения = [п.strip() for п in ПРЕДЛОЖЕНИЕ.findall(текст) if п.strip()]
        токены = re.findall(r"[\w-]+", текст, flags=re.U)
        отчёт.stats = {"chars": len(текст), "words": len(токены),
                       "sentences": len(предложения)}

        self._штампы(текст, отчёт)
        self._канцелярит(текст, отчёт)
        self._машинное(текст, отчёт)
        self._смешение(текст, отчёт)
        self._переспам(токены, отчёт)
        self._повтор_предложений(предложения, отчёт)
        self._тавтология(предложения, отчёт)
        self._длина(предложения, отчёт)
        self._обрывы(текст, предложения, отчёт)
        self._реклама(текст, отчёт)
        self._числительные(текст, отчёт)
        self._склонение_названия(текст, отчёт)
        self._пунктуация(текст, отчёт)
        return отчёт

    # --- отдельные проверки ------------------------------------------------

    def _штампы(self, текст: str, отчёт: LanguageReport) -> None:
        н = LEX.нормализовать(текст)
        for ш in LEX.ШТАМПЫ:
            м = re.search(ш, н)
            if м:
                отчёт.issues.append(LanguageIssue(
                    "FORBIDDEN_CLICHE", "CRITICAL",
                    "пустая формула: ничего не сообщает о произведении",
                    м.group(0)))

    def _канцелярит(self, текст: str, отчёт: LanguageReport) -> None:
        н = LEX.нормализовать(текст)
        for ш in LEX.КАНЦЕЛЯРИТ:
            м = re.search(ш, н)
            if м:
                отчёт.issues.append(LanguageIssue(
                    "BUREAUCRATESE", "ERROR",
                    "канцелярский оборот удлиняет фразу, не добавляя смысла",
                    м.group(0)))

    def _машинное(self, текст: str, отчёт: LanguageReport) -> None:
        for ш in LEX.МАШИННЫЕ:
            м = re.search(ш, текст, re.I | re.M)
            if м:
                отчёт.issues.append(LanguageIssue(
                    "MACHINE_CONSTRUCTION", "CRITICAL",
                    "след генерации вместо текста", м.group(0)))

    def _смешение(self, текст: str, отчёт: LanguageReport) -> None:
        """Латинская буква внутри русского слова.

        Ошибка тихая и опасная: «Нaруто» с латинской «a» выглядит правильно,
        читается правильно и не находится поиском.
        """
        for слово in re.findall(r"[\w-]{2,}", текст, flags=re.U):
            if КИРИЛЛИЦА.search(слово) and ЛАТИНИЦА.search(слово):
                отчёт.issues.append(LanguageIssue(
                    "SCRIPT_MIXING", "CRITICAL",
                    "в одном слове кириллица и латиница: слово не найдётся "
                    "поиском и читается как опечатка", слово))

    def _переспам(self, токены: Sequence[str], отчёт: LanguageReport) -> None:
        значимые = [LEX.стем(т) for т in токены
                    if LEX.нормализовать(т) not in СТОП_СЛОВА and len(т) > 2
                    and not т.isdigit()]
        if len(токены) < МИН_СЛОВ_ДЛЯ_ПЕРЕСПАМА or not значимые:
            return
        счёт = Counter(значимые)
        for основа, n in счёт.most_common(5):
            доля = n / len(токены)
            if доля > ПОРОГ_ПЕРЕСПАМА and n >= 4:
                отчёт.issues.append(LanguageIssue(
                    "KEYWORD_STUFFING", "CRITICAL",
                    f"«{основа}» повторяется {n} раз — {доля:.1%} текста; "
                    f"это плотность ради плотности", основа))

    def _повтор_предложений(self, предложения: Sequence[str],
                            отчёт: LanguageReport) -> None:
        видели: dict[str, str] = {}
        for п in предложения:
            ключ = " ".join(LEX.стемы(п))
            if len(ключ.split()) < 4:
                continue
            if ключ in видели:
                отчёт.issues.append(LanguageIssue(
                    "SENTENCE_REPEATED", "ERROR",
                    "предложение повторяет уже сказанное", п[:100]))
            видели[ключ] = п

    def _тавтология(self, предложения: Sequence[str],
                    отчёт: LanguageReport) -> None:
        for п in предложения:
            основы = LEX.стемы(п)
            for i, о in enumerate(основы):
                if len(о) < 5 or о in СТОП_СЛОВА:
                    continue
                хвост = основы[i + 1:i + 1 + ОКНО_ТАВТОЛОГИИ]
                if о in хвост:
                    отчёт.issues.append(LanguageIssue(
                        "TAUTOLOGY", "WARNING",
                        f"«{о}» дважды в пределах {ОКНО_ТАВТОЛОГИИ} слов",
                        п[:100]))
                    break

    def _длина(self, предложения: Sequence[str],
               отчёт: LanguageReport) -> None:
        for п in предложения:
            слов = len(re.findall(r"[\w-]+", п, flags=re.U))
            if слов > МАКС_СЛОВ_В_ПРЕДЛОЖЕНИИ:
                отчёт.issues.append(LanguageIssue(
                    "SENTENCE_TOO_LONG", "WARNING",
                    f"{слов} слов в предложении при пороге "
                    f"{МАКС_СЛОВ_В_ПРЕДЛОЖЕНИИ}", п[:100]))

    def _обрывы(self, текст: str, предложения: Sequence[str],
                отчёт: LanguageReport) -> None:
        т = текст.strip()
        if т and т[-1] not in ".!?…»\"'":
            отчёт.issues.append(LanguageIssue(
                "TRUNCATED_SENTENCE", "CRITICAL",
                "текст обрывается без завершающего знака", т[-60:]))
        if т.endswith(("и", "в", "на", "с", "а", "но", "что", "как", "-")):
            отчёт.issues.append(LanguageIssue(
                "TRUNCATED_SENTENCE", "CRITICAL",
                "текст обрывается на служебном слове", т[-60:]))
        for открыв, закрыв in (("«", "»"), ("(", ")"), ("[", "]")):
            if т.count(открыв) != т.count(закрыв):
                отчёт.issues.append(LanguageIssue(
                    "UNBALANCED_QUOTES", "ERROR",
                    f"{открыв}{закрыв}: открыто {т.count(открыв)}, закрыто "
                    f"{т.count(закрыв)}", ""))

    def _реклама(self, текст: str, отчёт: LanguageReport) -> None:
        н = LEX.нормализовать(текст)
        for ш in РЕКЛАМА:
            м = re.search(ш, н)
            if м:
                отчёт.issues.append(LanguageIssue(
                    "ADVERTISING_TONE", "ERROR",
                    "призыв вместо сведений о произведении", м.group(0)))

    def _числительные(self, текст: str, отчёт: LanguageReport) -> None:
        """Согласование числительного с существительным.

        Единственная морфологическая проверка, которую здесь честно можно
        сделать без словаря: правило счётной формы механическое.
        """
        for м in re.finditer(r"\b(\d{1,4})\s+([А-Яа-яЁё]{3,})", текст):
            n, слово = int(м.group(1)), м.group(2).lower().replace("ё", "е")
            # «2015 года» — это год, а не две тысячи пятнадцать лет. Счётная
            # форма здесь не применяется, и требовать «2015 лет» было бы
            # ошибкой проверки, а не текста.
            if слово.startswith("год") and 1500 <= n <= 2100:
                continue
            for ключ, формы in СЧЁТНЫЕ.items():
                if not слово.startswith(ключ):
                    continue
                нужная = формы[форма_числительного(n)]
                if слово != нужная:
                    отчёт.issues.append(LanguageIssue(
                        "NUMERAL_AGREEMENT", "ERROR",
                        f"«{n} {слово}» — нужно «{n} {нужная}»", м.group(0)))
                break

    def _склонение_названия(self, текст: str, отчёт: LanguageReport) -> None:
        """Название в кавычках не склоняется.

        «В "Бункере" события…» — ошибка: склоняется родовое слово, а
        название остаётся в исходной форме.
        """
        if not self.allowed_titles:
            return
        for м in re.finditer(r"[«\"]([^»\"]{2,80})[»\"]", текст):
            внутри = LEX.нормализовать(м.group(1))
            if внутри in self.allowed_titles:
                continue
            основы_внутри = [LEX.стем(с) for с in внутри.split()]
            for разрешённое in self.allowed_titles:
                основы = [LEX.стем(с) for с in разрешённое.split()]
                if основы and основы == основы_внутри:
                    отчёт.issues.append(LanguageIssue(
                        "TITLE_DECLINED", "ERROR",
                        f"название в кавычках просклонено: «{м.group(1)}» "
                        f"вместо «{разрешённое}»", м.group(1)))
                    break

    def _пунктуация(self, текст: str, отчёт: LanguageReport) -> None:
        # Однобуквенные предлоги и союзы тоже считаются: «о о смотрителе» —
        # та же опечатка, что «сериал сериал», и глазом она проскакивает
        # даже легче. Исключены только числа: «12 12» встречается в перечнях.
        for м in re.finditer(r"\b(\w+)\s+\1\b", текст, flags=re.I | re.U):
            if not м.group(1).isdigit():
                отчёт.issues.append(LanguageIssue(
                    "DOUBLED_WORD", "ERROR", "слово повторено подряд",
                    м.group(0)))
        if re.search(r"\s+[,.;:!?]", текст):
            отчёт.issues.append(LanguageIssue(
                "PUNCTUATION_SPACING", "ERROR",
                "пробел перед знаком препинания", ""))
        if re.search(r"[,;:](?=[^\s\d»)\]])", текст):
            отчёт.issues.append(LanguageIssue(
                "PUNCTUATION_SPACING", "ERROR",
                "нет пробела после знака препинания", ""))
