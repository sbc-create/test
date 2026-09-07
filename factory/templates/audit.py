"""Прогон рубрики по собранному стенду и сводка по направлению.

Аудит работает по каталогу, который уже выложил ``lords-preview``. Это
сознательный выбор: оценивается тот же документ, который увидит браузер, а не
промежуточное представление рендерера. Расхождение между ними — самая дорогая
из возможных ошибок отчёта, и такой способ прогона её исключает.

Страницы с переменным адресом (``title/{slug}/``, ``genres/{slug}/``)
разрешаются в **лексикографически первый** существующий документ. Выбор
детерминирован намеренно: иначе балл направления менялся бы между прогонами
без единой правки кода.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from factory.templates.rubric import (
    CRITERIA,
    NOT_APPLICABLE,
    LORDS_KEY_PAGES,
    UNMEASURED,
    Check,
    Expectation,
    PageScore,
    score_page,
)


@dataclass
class SiteScore:
    """Оценка одного пакета: страницы и минимум по ним."""

    site: str
    profile: str
    pages: list[PageScore] = field(default_factory=list)

    @property
    def existing(self) -> list[PageScore]:
        """Страницы, которые эта витрина обязана иметь."""
        return [p for p in self.pages if p.applies]

    @property
    def worst(self) -> PageScore | None:
        return min(self.existing, key=lambda p: p.score) if self.existing else None

    @property
    def minimum(self) -> float:
        return min((p.score for p in self.existing), default=0.0)

    @property
    def average(self) -> float:
        if not self.existing:
            return 0.0
        return round(sum(p.score for p in self.existing) / len(self.existing), 1)

    def meets(self, threshold: float) -> bool:
        """Порог берётся по худшей странице, а не по средней.

        Среднее скрывает провал: восемь отличных страниц и одна сломанная дают
        приличное число и негодный сайт. Владелец открывает не среднее.
        """
        return bool(self.pages) and self.minimum >= threshold

    def as_dict(self) -> dict:
        return {
            "site": self.site,
            "profile": self.profile,
            "minimum": self.minimum,
            "average": self.average,
            "pages": [p.as_dict() for p in self.pages],
        }


def _disabled_types(preview_root: Path) -> set[str]:
    """Типы содержимого, выключенные профилем, по отчёту сборки.

    Читается именно отчёт сборки, а не пакет сайта: отчёт описывает то, что
    рендерер на самом деле собрал, включая типы, отключённые не настройкой, а
    отсутствием записей в источнике.
    """
    report_file = preview_root / "preview-report.json"
    if not report_file.exists():
        return set()
    data = json.loads(report_file.read_text(encoding="utf-8"))
    return {
        name for name, state in (data.get("content_types") or {}).items()
        if not state.get("active")
    }


def _resolve(root: Path, path: str) -> Path | None:
    """Найти документ по шаблону адреса, разрешив ``{slug}`` детерминированно."""
    if "{slug}" not in path:
        candidate = root / path
        return candidate if candidate.exists() else None
    prefix, _, suffix = path.partition("{slug}")
    parent = root / prefix.rstrip("/")
    if not parent.is_dir():
        return None
    tail = suffix.strip("/")
    found = sorted(
        child / tail for child in parent.iterdir()
        if child.is_dir() and (child / tail).exists()
    )
    return found[0] if found else None


def _stylesheets(root: Path, html: str) -> str:
    """Содержимое локальных таблиц стилей документа.

    Читаются только файлы внутри собранного каталога: внешний адрес не
    загружается — оценка обязана быть воспроизводимой и не зависеть от сети.
    Недоступный файл молча пропускается: его отсутствие уже видно критерию
    как отсутствие правила.
    """
    from factory.templates.rubric import parse

    parts = []
    for href in parse(html).stylesheet_hrefs:
        if "://" in href or href.startswith("//"):
            continue
        candidate = root / href.lstrip("/")
        if candidate.is_file():
            try:
                parts.append(candidate.read_text(encoding="utf-8"))
            except OSError:
                continue
    return "\n".join(parts)


def audit_site(
    preview_root: Path,
    site: str,
    profile: str = "",
    expectations: tuple[Expectation, ...] = LORDS_KEY_PAGES,
) -> SiteScore:
    """Оценить один собранный пакет по всем ключевым страницам."""
    score = SiteScore(site=site, profile=profile)
    disabled = _disabled_types(preview_root)
    for expectation in expectations:
        if expectation.requires_type and expectation.requires_type in disabled:
            # Раздел выключен профилем. Это исполненное решение владельца, а не
            # пробел качества: выключенный тип не создаёт ни маршрута, ни
            # страницы, и штрафовать витрину за его отсутствие значило бы
            # требовать раздел, который она обязана не показывать.
            score.pages.append(PageScore(
                expectation.page, expectation.path,
                [Check(c.__name__.strip("_"), NOT_APPLICABLE,
                       f"тип {expectation.requires_type} выключен профилем")
                 for c in CRITERIA]))
            continue
        document = _resolve(preview_root, expectation.path)
        if document is None:
            # Отсутствующая страница не «ноль по всем критериям»: она не
            # измерена. Разница видна в отчёте и не выдаёт себя за провал
            # качества там, где раздел выключен профилем.
            missing = PageScore(
                expectation.page,
                expectation.path,
                [Check(c.__name__.strip("_"), UNMEASURED, "документ не собран")
                 for c in CRITERIA],
            )
            score.pages.append(missing)
            continue
        html = document.read_text(encoding="utf-8")
        page = score_page(html, expectation, css=_stylesheets(preview_root, html))
        page.path = str(document.relative_to(preview_root))
        score.pages.append(page)
    return score


def report(scores: list[SiteScore], threshold: float = 8.0) -> dict:
    """Свести оценки пакетов в один машиночитаемый отчёт."""
    return {
        "threshold": threshold,
        "meets_threshold": all(s.meets(threshold) for s in scores),
        "sites": [s.as_dict() for s in scores],
        "worst": min(
            ((s.site, s.worst.page, s.worst.score) for s in scores if s.worst),
            key=lambda row: row[2], default=None),
    }


def render_table(scores: list[SiteScore], threshold: float = 8.0) -> str:
    """Человекочитаемая таблица: строка на страницу, столбец на пакет."""
    # Строки таблицы — те страницы, которые действительно оценены. Прежде здесь
    # стоял список Lords, и таблица для чужого набора выходила пустой: все
    # ячейки «—», потому что имена страниц не совпадали ни с одной строкой.
    pages = list(dict.fromkeys(p.page for s in scores for p in s.pages)) or [
        e.page for e in LORDS_KEY_PAGES]
    width = max(len(p) for p in pages) + 2
    header = "страница".ljust(width) + "".join(s.site.rjust(11) for s in scores)
    lines = [header, "-" * len(header)]
    for page in pages:
        row = page.ljust(width)
        for site in scores:
            found = next((p for p in site.pages if p.page == page), None)
            absent = found is None or not found.applies
            cell = "—" if absent else f"{found.score:.1f}"
            mark = "" if absent or found.score >= threshold else " !"
            row += (cell + mark).rjust(11)
        lines.append(row)
    lines.append("-" * len(header))
    lines.append("минимум".ljust(width) + "".join(f"{s.minimum:.1f}".rjust(11) for s in scores))
    return "\n".join(lines)
