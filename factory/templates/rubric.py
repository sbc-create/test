"""Рубрика качества шаблона: чем «8 из 10» отличается от мнения.

Оценка страницы должна быть воспроизводимой. Поэтому здесь нет ни одного
критерия, который нельзя проверить кодом по готовому документу: рубрика читает
собранный HTML, а не намерение рендерера.

Три статуса вместо двух — существенная часть замысла:

* ``PASS``  — проверка запускалась и прошла;
* ``FAIL``  — проверка запускалась и не прошла;
* ``UNMEASURED`` — проверку запустить не удалось (нет данных, закрыт доступ).

``UNMEASURED`` **не** засчитывается как успех. Это прямое следствие правила
фабрики: «формулировки „проверено“ без запуска — ошибка отчёта». Балл за
непроверенный критерий был бы ровно такой формулировкой.

Четвёртый статус ``NOT_APPLICABLE`` снимает критерий со страницы целиком: у
поиска нет полки обновлений, у жанровой посадочной нет плеера. Такой критерий
не даёт балла и не входит в знаменатель — иначе страница получала бы штраф за
то, чего у неё по устройству нет.

Итоговый балл: ``10 * PASS / (PASS + FAIL + UNMEASURED)``.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser

PASS = "pass"
FAIL = "fail"
UNMEASURED = "unmeasured"
NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class Check:
    """Результат одного критерия по одной странице."""

    criterion: str
    status: str
    detail: str

    @property
    def counts(self) -> bool:
        """Входит ли критерий в знаменатель оценки."""
        return self.status != NOT_APPLICABLE


@dataclass
class PageScore:
    """Оценка одной страницы: балл и полный список того, чем он получен."""

    page: str
    path: str
    checks: list[Check] = field(default_factory=list)

    @property
    def applicable(self) -> list[Check]:
        return [c for c in self.checks if c.counts]

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status == PASS)

    @property
    def applies(self) -> bool:
        """Существует ли страница для этой витрины вообще.

        Раздел, выключенный профилем, не «набрал ноль баллов»: его нет по
        решению владельца. Ноль здесь означал бы провал качества и уводил бы
        минимум по сайту в пол на ровном месте.
        """
        return bool(self.applicable)

    @property
    def score(self) -> float:
        denominator = len(self.applicable)
        if not denominator:
            return 0.0
        return round(10.0 * self.passed / denominator, 1)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if c.status in (FAIL, UNMEASURED)]

    def as_dict(self) -> dict:
        return {
            "page": self.page,
            "path": self.path,
            "score": self.score,
            "passed": self.passed,
            "applicable": len(self.applicable),
            "checks": [
                {"criterion": c.criterion, "status": c.status, "detail": c.detail}
                for c in self.checks
            ],
        }


# --------------------------------------------------------------------------
# Разбор документа
# --------------------------------------------------------------------------


class _Document(HTMLParser):
    """Минимальный разбор: рубрике нужна структура, а не дерево целиком.

    Стандартный ``html.parser`` выбран намеренно вместо внешнего парсера:
    рубрика обязана работать в том же окружении, что и сборка, без новой
    зависимости в ``requirements.txt``.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: Counter[str] = Counter()
        self.tags: Counter[str] = Counter()
        self.headings: list[tuple[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.inputs: list[dict[str, str]] = []
        self.labels_for: set[str] = set()
        self.links: list[dict[str, str]] = []
        self.blocks: list[str] = []
        self.metas: dict[str, str] = {}
        self.aria_labels: list[str] = []
        self.landmarks: set[str] = set()
        self.classes: Counter[str] = Counter()
        self.inline_styles: list[str] = []
        self.scripts: int = 0
        self.stylesheets: int = 0
        self._heading: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: (v or "") for k, v in attrs}
        self.tags[tag] += 1
        if "id" in attr:
            self.ids[attr["id"]] += 1
        for cls in attr.get("class", "").split():
            self.classes[cls] += 1
        if "style" in attr:
            self.inline_styles.append(attr["style"])
        if "data-block" in attr:
            self.blocks.append(attr["data-block"])
        if "aria-label" in attr:
            self.aria_labels.append(attr["aria-label"])
        if tag in ("header", "main", "footer", "nav", "aside"):
            self.landmarks.add(tag)
        if attr.get("role") in ("banner", "main", "contentinfo", "navigation", "search"):
            self.landmarks.add(attr["role"])
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._heading = tag
            self._text = []
        if tag == "img":
            self.images.append(attr)
        if tag in ("input", "select", "textarea"):
            self.inputs.append(attr)
        if tag == "label" and "for" in attr:
            self.labels_for.add(attr["for"])
        if tag == "a":
            self.links.append(attr)
        if tag == "meta":
            key = attr.get("name") or attr.get("property")
            if key:
                self.metas[key] = attr.get("content", "")
        if tag == "script":
            self.scripts += 1
        if tag == "link" and attr.get("rel") == "stylesheet":
            self.stylesheets += 1

    def handle_endtag(self, tag: str) -> None:
        if self._heading and tag == self._heading:
            self.headings.append((tag, "".join(self._text).strip()))
            self._heading = None
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._heading:
            self._text.append(data)


def parse(html: str) -> _Document:
    doc = _Document()
    doc.feed(html)
    return doc


# --------------------------------------------------------------------------
# Ожидания страницы
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Expectation:
    """Что рубрика вправе требовать именно от этой страницы.

    Ожидание — не украшение: оно решает, какой критерий входит в знаменатель.
    Требовать плеер от жанровой посадочной значило бы занижать её балл за
    отсутствие того, чего у неё нет по устройству.
    """

    page: str
    path: str
    #: Ожидается ли на странице полка обновлений/новых поступлений.
    updates: bool = False
    #: Чем обновления показаны: полками главной или самим списком страницы.
    #: Различие существенно: у `/new/` весь документ и есть лента поступлений,
    #: и требовать от неё «полку» значило бы искать витрину внутри витрины.
    updates_via: str = "blocks"
    #: Тип содержимого, без которого раздела не существует. Профиль вправе его
    #: выключить, и тогда отсутствие страницы — исполненное решение владельца,
    #: а не пробел качества.
    requires_type: str | None = None
    #: Ожидается ли посадочное место плеера.
    player: bool = False
    #: Ожидается ли хотя бы одна карточка каталога.
    cards: bool = True
    #: Ожидается ли форма поиска.
    search_form: bool = False
    #: Бюджет веса документа в килобайтах.
    weight_budget_kb: int = 120


#: Ключевые страницы направления Lords. Список закрыт намеренно: «ключевая»
#: значит «её отказ виден владельцу сразу», а не «она существует».
LORDS_KEY_PAGES: tuple[Expectation, ...] = (
    Expectation("home", "index.html", updates=True, search_form=True),
    Expectation("catalog", "catalog/index.html"),
    Expectation("title", "title/{slug}/index.html", player=True, cards=False),
    Expectation("new", "new/index.html", updates=True, updates_via="listing"),
    Expectation("schedule", "schedule/index.html", cards=False, requires_type="series"),
    Expectation("genres", "genres/index.html", cards=False),
    Expectation("genre_landing", "genres/{slug}/index.html"),
    Expectation("collections", "collections/index.html", cards=False,
                requires_type="collections"),
    Expectation("search", "search/index.html", cards=False, search_form=True),
)


#: Ключевые страницы направления Yummy. Список снят с матрицы страниц самого
#: приложения (`src/site-blueprint/page-matrix.ts`, строки `implemented` и
#: индексируемые), а не придуман здесь: у Yummy карта живёт в коде приложения,
#: и второй её редакции быть не должно.
#:
#: Пути ведут к сохранённому HTML, а не к живому сайту. Оценка Yummy сегодня не
#: приводится: чтобы получить эти документы, нужно поднять приложение с базой,
#: а база и учётные данные этому потоку не переданы. Ожидания описаны заранее
#: именно затем, чтобы в момент появления HTML оценка была одной командой, а не
#: новой работой.
YUMMY_KEY_PAGES: tuple[Expectation, ...] = (
    Expectation("home", "index.html", updates=True, search_form=True),
    Expectation("catalog", "catalog/index.html"),
    Expectation("title", "anime/{slug}/index.html", player=True, cards=False),
    Expectation("updates", "catalog/anime-updates/index.html",
                updates=True, updates_via="listing"),
    Expectation("ongoing", "catalog/ongoing/index.html"),
    Expectation("schedule", "catalog/schedule/index.html", cards=False),
    Expectation("top", "catalog/top/index.html"),
    Expectation("announcements", "catalog/announcement/index.html"),
)

# --------------------------------------------------------------------------
# Критерии
# --------------------------------------------------------------------------


def _routes(doc: _Document, exp: Expectation, html: str) -> Check:
    """Страница объявляет своё место и свою индексируемость явно."""
    canonical_state = doc.metas.get("lords-canonical-state")
    robots = doc.metas.get("robots")
    if not canonical_state:
        return Check("routes", FAIL, "нет метки lords-canonical-state")
    if not robots:
        return Check("routes", FAIL, "нет meta robots")
    return Check("routes", PASS, f"canonical-state={canonical_state}, robots={robots}")


def _document(doc: _Document, exp: Expectation, html: str) -> Check:
    """Ровно один h1, заполненные title и description, объявленный язык."""
    h1 = [t for tag, t in doc.headings if tag == "h1"]
    problems = []
    if len(h1) != 1:
        problems.append(f"h1: {len(h1)}, ожидался ровно один")
    elif not h1[0]:
        problems.append("h1 пуст")
    if "<html lang=" not in html:
        problems.append("не объявлен lang")
    indexable = "noindex" not in doc.metas.get("robots", "")
    if indexable and not doc.metas.get("description", "").strip():
        # Требование повторяет SEO-003: описание спрашивают у страницы,
        # которая идёт в индекс. У навигационного раздела с `noindex`
        # собственного текста нет намеренно — его пишет владелец раздела.
        problems.append("индексируемая страница без description")
    if "<title>" not in html:
        problems.append("нет title")
    if problems:
        return Check("document", FAIL, "; ".join(problems))
    return Check("document", PASS, f"h1={h1[0][:40]!r}, description и lang на месте")


def _validity(doc: _Document, exp: Expectation, html: str) -> Check:
    """Идентификаторы уникальны, ссылки ведут куда-то, у картинок есть размеры."""
    problems = []
    dupes = {i: n for i, n in doc.ids.items() if n > 1}
    if dupes:
        listed = ", ".join(f"{i}×{n}" for i, n in sorted(dupes.items()))
        problems.append(f"повторяющиеся id: {listed}")
    empty_href = [a for a in doc.links if not a.get("href", "").strip()]
    if empty_href:
        problems.append(f"ссылок без href: {len(empty_href)}")
    sized = [i for i in doc.images if i.get("width") and i.get("height")]
    if doc.images and len(sized) != len(doc.images):
        problems.append(f"картинок без размеров: {len(doc.images) - len(sized)}")
    if problems:
        return Check("validity", FAIL, "; ".join(problems))
    return Check("validity", PASS, f"id уникальны ({len(doc.ids)}), картинок {len(doc.images)}")


def _accessibility(doc: _Document, exp: Expectation, html: str) -> Check:
    """Ориентиры, подписи к полям и управляемое меню."""
    problems = []
    required = {"header", "main", "footer", "nav"}
    missing = required - doc.landmarks
    if missing:
        problems.append(f"нет ориентиров: {', '.join(sorted(missing))}")
    if "visually-hidden" not in doc.classes and "skip" not in html[:2000].lower():
        problems.append("нет ссылки перехода к содержимому")
    unlabelled = [
        i for i in doc.inputs
        if i.get("type") not in ("hidden", "submit", "button")
        and not i.get("aria-label")
        and i.get("id", "\0") not in doc.labels_for
    ]
    if unlabelled:
        problems.append(f"полей без подписи: {len(unlabelled)}")
    if "nav-toggle" in doc.classes and "aria-expanded" not in html:
        problems.append("переключатель меню без aria-expanded")
    if problems:
        return Check("accessibility", FAIL, "; ".join(problems))
    return Check(
        "accessibility", PASS,
        f"ориентиры {len(doc.landmarks)}, полей с подписью {len(doc.inputs)}")


def _adaptivity(doc: _Document, exp: Expectation, html: str) -> Check:
    """Документ пригоден к узкому экрану без горизонтальной прокрутки."""
    problems = []
    viewport = doc.metas.get("viewport", "")
    if "width=device-width" not in viewport:
        problems.append("нет viewport width=device-width")
    fixed = [s for s in doc.inline_styles if re.search(r"width:\s*\d{3,}px", s)]
    if fixed:
        problems.append(f"фиксированная ширина в inline-стиле: {len(fixed)}")
    if "nav-toggle" not in doc.classes:
        problems.append("нет переключателя меню для узкого экрана")
    if problems:
        return Check("adaptivity", FAIL, "; ".join(problems))
    return Check("adaptivity", PASS, f"viewport={viewport!r}, меню сворачивается")


def _updates(doc: _Document, exp: Expectation, html: str) -> Check:
    """Полка обновлений присутствует и не пуста — там, где она обещана."""
    if not exp.updates:
        return Check("updates", NOT_APPLICABLE, "страница не обещает полку обновлений")
    if exp.updates_via == "listing":
        # Сама страница и есть лента поступлений: обновления показаны списком.
        if doc.classes.get("card", 0) == 0:
            return Check("updates", FAIL, "лента поступлений пуста")
        return Check(
            "updates", PASS,
            f"лента поступлений, карточек {doc.classes['card']}")
    shelves = {"latest_grid", "fresh_episodes", "type_rows"}
    found = shelves.intersection(doc.blocks)
    if not found:
        return Check("updates", FAIL, "нет ни одного блока обновлений")
    if doc.classes.get("card", 0) == 0:
        return Check("updates", FAIL, f"блоки {sorted(found)} есть, но карточек нет")
    return Check(
        "updates", PASS,
        f"блоки {sorted(found)}, карточек {doc.classes['card']}")


def _player_shell(doc: _Document, exp: Expectation, html: str) -> Check:
    """Место плеера занято и честно подписано до подключения поставщика.

    Заглушка засчитывается: критерий проверяет посадочное место, а не работу
    поставщика. Работу поставщика проверяет ``player.contract_check()``, и она
    сегодня честно возвращает «не запускалась».
    """
    if not exp.player:
        return Check("player_shell", NOT_APPLICABLE, "у страницы нет плеера")
    if "player" not in html:
        return Check("player_shell", FAIL, "посадочного места плеера нет")
    reserved = bool(
        re.search(r"aspect-ratio|padding-top:\s*5[06]", html)
        or "player__frame" in doc.classes
        or doc.classes.get("player", 0)
    )
    # Критерий проверяет посадочное место и вежливость, но не наличие кода
    # отказа: код отказа принадлежит отчёту сборки, а не публичной странице
    # (REQ-LORDS-PLAYER-LIVE, D128). Утечка служебного кода — не признак
    # диагностируемости, а отдельный дефект, и он тоже проверяется здесь.
    explained = "недоступ" in html or "не подключ" in html
    leaked = [c for c in ("BLOCKED_INPUT", "CDNVIDEOHUB_CREDENTIALS") if c in html]
    problems = []
    if not reserved:
        problems.append("кадр не зарезервирован — включение плеера сдвинет раскладку")
    if not explained:
        problems.append("состояние плеера не объяснено читателю")
    if leaked:
        problems.append(f"в разметку утёк служебный код: {', '.join(leaked)}")
    if problems:
        return Check("player_shell", FAIL, "; ".join(problems))
    return Check(
        "player_shell", PASS,
        "кадр зарезервирован, состояние объяснено, служебный код не утёк")


def _ratings(doc: _Document, exp: Expectation, html: str) -> Check:
    """Оценка показывается только с источником и никогда не выдумывается."""
    shown = re.findall(r'data-rating="([^"]*)"', html)
    if not shown:
        return Check(
            "ratings", PASS,
            "оценок нет ни как поля, ни как разметки — выдумывать нечего")
    sourced = re.findall(r'data-rating-source="([^"]+)"', html)
    if len(sourced) < len(shown):
        return Check(
            "ratings", FAIL,
            f"оценок {len(shown)}, из них с источником {len(sourced)}")
    return Check("ratings", PASS, f"оценок {len(shown)}, у каждой указан источник")


def _speed(doc: _Document, exp: Expectation, html: str) -> Check:
    """Вес документа и число запросов в пределах бюджета."""
    weight_kb = len(html.encode("utf-8")) / 1024
    problems = []
    if weight_kb > exp.weight_budget_kb:
        problems.append(f"документ {weight_kb:.0f} КБ при бюджете {exp.weight_budget_kb}")
    below_fold = [i for i in doc.images if i.get("loading") != "lazy"]
    if len(below_fold) > 4:
        problems.append(f"картинок без lazy: {len(below_fold)}")
    if doc.stylesheets > 2:
        problems.append(f"таблиц стилей: {doc.stylesheets}")
    if problems:
        return Check("speed", FAIL, "; ".join(problems))
    return Check(
        "speed", PASS,
        f"{weight_kb:.0f} КБ, картинок {len(doc.images)}, стилей {doc.stylesheets}")


def _structured_data(doc: _Document, exp: Expectation, html: str) -> Check:
    """Страница описывает себя машинам: хлебные крошки или тип документа."""
    if "application/ld+json" not in html:
        return Check("structured_data", FAIL, "нет ни одного блока JSON-LD")
    return Check("structured_data", PASS, "JSON-LD присутствует")


def _content_honesty(doc: _Document, exp: Expectation, html: str) -> Check:
    """Происхождение данных объявлено, карточки есть там, где обещаны."""
    source = doc.metas.get("lords-data-source")
    if not source:
        return Check("content_honesty", FAIL, "не объявлено происхождение данных")
    if exp.cards and doc.classes.get("card", 0) == 0:
        return Check("content_honesty", FAIL, f"источник {source}, но карточек нет")
    return Check("content_honesty", PASS, f"источник {source}")


#: Порядок критериев фиксирован: отчёт сравнивается между прогонами построчно.
CRITERIA = (
    _routes,
    _document,
    _validity,
    _accessibility,
    _adaptivity,
    _updates,
    _player_shell,
    _ratings,
    _speed,
    _structured_data,
    _content_honesty,
)


def score_page(html: str, expectation: Expectation) -> PageScore:
    """Оценить один готовый документ по всем применимым критериям."""
    doc = parse(html)
    checks = [criterion(doc, expectation, html) for criterion in CRITERIA]
    return PageScore(expectation.page, expectation.path, checks)
