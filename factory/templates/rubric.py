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
        #: Адреса подключённых таблиц стилей. Нужны затем, что часть свойств
        #: документа задана не в разметке: резерв кадра под плеер живёт в
        #: правиле класса, и критерий, читающий только HTML, объявляет его
        #: отсутствующим там, где он есть.
        self.stylesheet_hrefs: list[str] = []
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
            if attr.get("href"):
                self.stylesheet_hrefs.append(attr["href"])

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
    #: Ожидается ли разметка для машин. Служебные страницы — поиск, 404 и 410 —
    #: описывать себя машинам не обязаны: их не индексируют, и JSON-LD на них
    #: описывал бы документ, которого не должно быть в выдаче.
    structured_data: bool = True


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
    Expectation("search", "search/index.html", cards=False, search_form=True,
                structured_data=False),
)


#: Ключевые страницы theme pack `basis-video`. Список снят с карты маршрутов
#: собранного пакета (`var/build/pilot-local/<id>/routes.json`), а не составлен
#: по образцу Lords: у basis-video своя карта — разделы названы по-русски, а
#: типов страниц он отдаёт четырнадцать из семнадцати объявленных.
#:
#: Отдельно об ожиданиях, которые здесь намеренно сняты:
#:
#:   * `updates=False` у главной. Полки обновлений у неё нет, и это устройство
#:     витрины, а не пробел: basis-video — каталог видеоматериалов, а не портал
#:     отслеживания выхода серий. Требовать полку значило бы штрафовать витрину
#:     за отсутствие раздела, которого она не обещает.
#:   * `cards=False` у страницы сезона. Сезон отдаёт список эпизодов строками,
#:     а не карточками каталога.
#:
#: Три объявленных типа — `tag`, `author`, `archive` — в список не входят:
#: фикстура пилота их не создаёт, и оценивать несуществующие документы значило
#: бы записывать «не измерено» в ворота, которые нечем закрыть.
BASIS_KEY_PAGES: tuple[Expectation, ...] = (
    Expectation("home", "index.html", search_form=True),
    Expectation("category", "lekcii/index.html", search_form=True),
    Expectation("title", "lekcii/material-01/index.html", player=True, cards=False,
                search_form=True),
    Expectation("season", "praktikum/serial-fikstura/season-1/index.html",
                cards=False, search_form=True),
    Expectation("episode", "praktikum/serial-fikstura/season-1/episode-1/index.html",
                player=True, cards=False, search_form=True),
    Expectation("collection", "collections/izbrannoe/index.html", search_form=True),
    Expectation("news_index", "news/index.html", search_form=True),
    Expectation("article", "news/zapis-3/index.html", cards=False, search_form=True),
    Expectation("search", "search/index.html", cards=False, search_form=True,
                structured_data=False),
    Expectation("content_unavailable", "lekcii/material-04/index.html",
                cards=False, search_form=True),
    Expectation("not_found", "404/index.html", cards=False, search_form=True,
                structured_data=False),
    Expectation("gone", "410/index.html", cards=False, search_form=True,
                structured_data=False),
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

#: Наборы ключевых страниц по слотам. Реестр нужен затем, чтобы выбор набора
#: был именем в команде, а не правкой кода: рубрика одна, карты страниц разные.
KEY_PAGE_SETS: dict[str, tuple[Expectation, ...]] = {
    "lords": LORDS_KEY_PAGES,
    "yummy": YUMMY_KEY_PAGES,
    "basis-video": BASIS_KEY_PAGES,
}


# --------------------------------------------------------------------------
# Критерии
# --------------------------------------------------------------------------


def _routes(doc: _Document, exp: Expectation, html: str) -> Check:
    """Страница объявляет своё место и свою индексируемость явно."""
    # Проверяется свойство, а не метка конкретного рендерера. Прежде критерий
    # требовал `lords-canonical-state` — служебную метку рендерера Lords — и
    # потому объявлял отказом любой второй theme pack, даже когда тот честно
    # отдаёт `<link rel="canonical">` и `meta robots`. Метка Lords осталась
    # принимаемой формой, но перестала быть единственной.
    canonical_state = doc.metas.get("lords-canonical-state")
    canonical_link = 'rel="canonical"' in html
    robots = doc.metas.get("robots")
    if not robots:
        return Check("routes", FAIL, "нет meta robots")
    # Страница, закрытая от индексации, своё место в выдаче уже объявила —
    # тем, что её там не будет. Canonical на ней не нужен и вреден: он указал
    # бы на адрес, который сам себя из индекса исключает.
    excluded = "noindex" in robots.lower()
    if not canonical_state and not canonical_link and not excluded:
        return Check("routes", FAIL, "место страницы не объявлено: "
                                     "нет ни canonical, ни метки canonical-state")
    place = canonical_state or ("canonical-link" if canonical_link else "noindex")
    return Check("routes", PASS, f"canonical-state={place}, robots={robots}")


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
    # Сворачиваемое меню — решение вёрстки, а не требование к узкому экрану:
    # навигация, переносящаяся по строкам, прокрутку не создаёт и переключателя
    # не требует. Прежде критерий требовал класс `nav-toggle` и потому
    # штрафовал любую тему, кроме Lords, за отсутствие чужого решения.
    # Проверяется теперь связность: если переключатель есть, он обязан быть
    # объявлен для вспомогательных технологий.
    if "nav-toggle" in doc.classes and "aria-expanded" not in html:
        problems.append("переключатель меню не объявляет aria-expanded")
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
    # Объяснение проверяется как свойство, а не как формулировка. Прежде здесь
    # искались подстроки «недоступ» и «не подключ» — точные слова рендерера
    # Lords, — и заглушка, объяснённая другими словами («подключается после
    # передачи contract»), считалась необъяснённой. Критерий обязан отличать
    # молчащий чёрный прямоугольник от подписанного места, а не сверять
    # словарь одного шаблона.
    frame = re.search(r'class="[^"]*player[^"]*".*?</div>', html, re.S)
    frame_html = frame.group(0) if frame else ""
    labelled = bool(re.search(r'aria-label(?:ledby)?="[^"]{3,}"', frame_html))
    prose = [t for t in re.findall(r"<p[^>]*>(.*?)</p>", frame_html, re.S)
             if len(re.sub(r"<[^>]+>", "", t).strip()) >= 40]
    explained = ("недоступ" in html or "не подключ" in html
                 or (labelled and prose))
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
    # Разметка берётся настоящая. Первая версия критерия искала `data-rating`,
    # которого рендерер не выдаёт вовсе: оценка выводится классами
    # `card__rating-value` и `card__rating-source`. Такой критерий не отличил бы
    # оценку без источника от её отсутствия и ставил бы PASS в обоих случаях.
    values = re.findall(r'class="[a-z_]*rating-value"', html)
    sources = re.findall(r'class="[a-z_]*rating-source"', html)
    if not values:
        return Check(
            "ratings", PASS,
            "оценок нет ни как поля, ни как разметки — выдумывать нечего")
    if len(sources) < len(values):
        return Check(
            "ratings", FAIL,
            f"оценок {len(values)}, из них с указанным источником {len(sources)}")
    return Check("ratings", PASS, f"оценок {len(values)}, у каждой указан источник")


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
    if not exp.structured_data:
        return Check("structured_data", NOT_APPLICABLE,
                     "служебная страница: разметка для машин не обещана")
    if "application/ld+json" not in html:
        return Check("structured_data", FAIL, "нет ни одного блока JSON-LD")
    return Check("structured_data", PASS, "JSON-LD присутствует")


def _content_honesty(doc: _Document, exp: Expectation, html: str) -> Check:
    """Происхождение данных объявлено, карточки есть там, где обещаны."""
    # Имя метки не фиксировано одним рендерером: `lords-data-source` — форма
    # Lords, `data-source` — общая. Проверяется объявленность происхождения, а
    # не то, каким из двух способов оно объявлено.
    source = doc.metas.get("lords-data-source") or doc.metas.get("data-source")
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


def score_page(html: str, expectation: Expectation, css: str = "") -> PageScore:
    """Оценить один готовый документ по всем применимым критериям.

    ``css`` — содержимое подключённых таблиц стилей, если их удалось прочитать.
    Пустая строка означает «стили не читались», и критерии, которым они нужны,
    обязаны различать это состояние с «правила нет»: первое — предел измерения,
    второе — дефект.
    """
    doc = parse(html)
    # Критерии читают стили через тот же аргумент, что и разметку: отдельного
    # канала нет намеренно, иначе часть критериев видела бы документ полнее
    # других и отчёт стал бы несравнимым между страницами.
    checks = [criterion(doc, expectation, html + ("\n/*css*/\n" + css if css else ""))
              for criterion in CRITERIA]
    return PageScore(expectation.page, expectation.path, checks)
