"""Контракт шаблона: что манифест вправе объявить и чем это подтверждается.

Контракт исполняемый. Форма манифеста задана JSON Schema
`schemas/template-manifest.schema.json`, а смысловые правила — функциями ниже.
Оба уровня нужны по разным причинам: схема ловит опечатку и лишнее поле, а код
ловит расхождение манифеста с рендерером, которое схема увидеть не может.

Главное правило контракта: **список блоков главной не выдуман, а вычитан из
рендерера.** `renderer_blocks()` разбирает исходник `factory/lords/render.py`
и возвращает блоки, у которых там есть ветка. Поэтому:

* блок, объявленный шаблоном, но не умеющий рисоваться, отвергается;
* блок, появившийся в рендерере, но не описанный здесь, тоже отвергается —
  иначе реестр молча отстанет от кода.

Сегодня в направлении есть ровно две таких рассинхронизации, и обе безобидны
только на вид: `lords-new` объявляет `hero_timeline`, `lords-curated` —
`hero_editorial`. Ни того, ни другого рендерер не знает; оформление первого
экрана задаёт `layout.hero`, а эти два имени в `home_blocks` не делают ничего.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from factory.paths import PATHS

#: Схема формы манифеста.
SCHEMA_FILE = "template-manifest.schema.json"

#: Исходник, из которого вычитывается перечень блоков главной.
RENDERER_FILE = Path("factory") / "lords" / "render.py"
HOME_FUNCTION = "_home"

#: Каталог шаблонов направления.
PROFILE_DIR = Path("blueprints") / "lords" / "profiles"
BLUEPRINT_FILE = Path("blueprints") / "lords" / "blueprint.yaml"
PACKAGE_SCHEMA_FILE = "site-package.schema.json"

#: Разделы с особым владением: их шаблон не «владеет», их владение задано
#: blueprint (`owner: self` у главной, `owner: none` у поиска).
NON_OWNABLE = ("home", "search")


@dataclass(frozen=True)
class Block:
    """Блок главной: слот, вид содержимого и флаг, без которого он не рисуется."""

    id: str
    #: hero — внутри первого экрана; stream — отдельная секция в потоке главной.
    slot: str
    #: cards — карточки произведений; chips — ссылки-плашки; text — только текст.
    produces: str
    #: Ключ layout, при выключенном значении которого блок молча пропадает.
    flag: str | None
    why: str


#: Реестр блоков. Ключи обязаны совпадать с ветками рендерера — это проверяется.
BLOCKS: dict[str, Block] = {
    "hero_search": Block(
        "hero_search", "hero", "text", None,
        "форма поиска внутри первого экрана"),
    "hero_facets": Block(
        "hero_facets", "hero", "chips", None,
        "жанровые плашки внутри первого экрана"),
    "top_carousel": Block(
        "top_carousel", "stream", "cards", None,
        "полка ранжировщика; состав собирает factory/lords/recommend.py"),
    "latest_grid": Block(
        "latest_grid", "stream", "cards", None,
        "последние добавления со ссылкой на весь каталог"),
    "type_rows": Block(
        "type_rows", "stream", "cards", None,
        "по ряду на каждый включённый тип контента"),
    "top_rated": Block(
        "top_rated", "stream", "cards", None,
        "полка по подтверждённой оценке; на трёх записях не рисуется вовсе"),
    "genre_chips": Block(
        "genre_chips", "stream", "chips", None,
        "плашки жанров каталога"),
    "year_grid": Block(
        "year_grid", "stream", "chips", None,
        "плашки годов выпуска"),
    "country_grid": Block(
        "country_grid", "stream", "chips", None,
        "плашки стран производства"),
    "calendar": Block(
        "calendar", "stream", "text", "show_calendar",
        "календарь серий; без флага show_calendar не рисуется"),
    "fresh_episodes": Block(
        "fresh_episodes", "stream", "cards", None,
        "продолжающиеся истории; пусто, если в каталоге нет сериальных записей"),
    "collection_cards": Block(
        "collection_cards", "stream", "cards", "show_collection_cards",
        "карточки подборок; без флага show_collection_cards не рисуется"),
    "editor_note": Block(
        "editor_note", "stream", "text", None,
        "оговорка о том, по каким признакам собран список"),
}

#: Блоки, дающие на главной хотя бы одну карточку.
CARD_BLOCKS = frozenset(b.id for b in BLOCKS.values() if b.produces == "cards")

#: Ширины, на которых шаблон обязан быть проверен. 390/768/1440 — те же три
#: ширины, что у harness'а Lords (tests/e2e-lords/helpers.js) и у манифеста
#: Yummy (src/site-blueprint/yami.ts design.breakpoints). Медиазапросы Lords
#: переключаются на 640 и 1024 (factory/lords/theme.py), поэтому эти три ширины
#: попадают ровно в три разные ветки: mobile, tablet, desktop.
BREAKPOINTS = (390, 768, 1440)

#: Порог приёмки боевого обновления: главная больше 4000 байт и содержит
#: `class="card`. automation/host/lords-content-refresh.sh:233. Шаблон, не
#: объявивший ни одного блока с карточками, этот порог не пройдёт, и релиз
#: откатится сам — молча и на каждом обновлении каталога.
RELEASE_GATE_HOME_BYTES = 4000
RELEASE_GATE_MARKER = 'class="card'


@dataclass(frozen=True)
class Problem:
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.where}: {self.message}"


def _root(root: Path | None) -> Path:
    return Path(root) if root else PATHS.root


def schema(root: Path | None = None) -> dict:
    path = _root(root) / "schemas" / SCHEMA_FILE
    return json.loads(path.read_text(encoding="utf-8"))


def renderer_blocks(root: Path | None = None) -> dict[str, int]:
    """Блоки, у которых в `_home()` есть ветка. Имя блока → строка исходника.

    Разбирается AST, а не текст: `grep` по строке нашёл бы и комментарий, и
    константу из соседней функции. Ветки в `_home()` бывают двух видов —
    `block == "x"` в цепочке elif и `"x" in blocks` для блоков первого экрана;
    учитываются оба.
    """
    source = (_root(root) / RENDERER_FILE).read_text(encoding="utf-8")
    tree = ast.parse(source)
    home = next(
        (n for n in ast.walk(tree)
         if isinstance(n, ast.FunctionDef) and n.name == HOME_FUNCTION),
        None,
    )
    if home is None:
        raise ValueError(f"{RENDERER_FILE}: функция {HOME_FUNCTION}() не найдена")

    found: dict[str, int] = {}
    for node in ast.walk(home):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        op = node.ops[0]
        left, right = node.left, node.comparators[0]
        if isinstance(op, ast.Eq) and isinstance(left, ast.Name) and left.id == "block":
            if isinstance(right, ast.Constant) and isinstance(right.value, str):
                found.setdefault(right.value, node.lineno)
        elif (isinstance(op, ast.In) and isinstance(right, ast.Name)
                and right.id == "blocks" and isinstance(left, ast.Constant)
                and isinstance(left.value, str)):
            found.setdefault(left.value, node.lineno)
    return found


def load_manifest(path: Path) -> dict:
    """Манифест из YAML или JSON. Формат выбирается по расширению."""
    text = Path(path).read_text(encoding="utf-8")
    if str(path).endswith(".json"):
        return json.loads(text)
    return yaml.safe_load(text) or {}


def _blueprint(root: Path | None = None) -> dict:
    return yaml.safe_load((_root(root) / BLUEPRINT_FILE).read_text(encoding="utf-8")) or {}


def validate_manifest(manifest: dict, *, root: Path | None = None,
                      where: str = "manifest") -> list[Problem]:
    """Все претензии к одному манифесту. Пустой список — манифест принят."""
    problems: list[Problem] = []
    validator = Draft202012Validator(schema(root))
    for error in sorted(validator.iter_errors(manifest), key=lambda e: list(e.path)):
        location = "/".join(str(p) for p in error.absolute_path) or "(корень)"
        problems.append(Problem(where, f"{location}: {error.message}"))
    if problems:
        # Смысловые правила читают поля, которых при ошибке формы может не быть.
        return problems

    layout = manifest.get("layout") or {}
    blocks = list(layout.get("home_blocks") or [])
    known = renderer_blocks(root)

    for block in blocks:
        if block not in known:
            problems.append(Problem(
                where,
                f"блок «{block}» объявлен, но рендерер его не рисует: ветки в "
                f"{RENDERER_FILE.as_posix()} {HOME_FUNCTION}() нет. "
                f"Известные блоки: {', '.join(sorted(known))}",
            ))
        elif block not in BLOCKS:
            problems.append(Problem(
                where,
                f"блок «{block}» рендерер рисует, но реестр контракта его не знает — "
                f"допиши его в factory/templates/contract.py BLOCKS",
            ))

    for block in blocks:
        spec = BLOCKS.get(block)
        if spec and spec.flag and not layout.get(spec.flag):
            problems.append(Problem(
                where,
                f"блок «{block}» объявлен, а флаг layout.{spec.flag} выключен — "
                f"блок не появится на главной и не сообщит об этом",
            ))

    slotted = [(b, BLOCKS[b].slot) for b in blocks if b in BLOCKS]
    slots = [slot for _b, slot in slotted]
    if "stream" in slots:
        first_stream = slots.index("stream")
        late = [b for i, (b, slot) in enumerate(slotted)
                if slot == "hero" and i > first_stream]
        if late:
            problems.append(Problem(
                where,
                f"блоки первого экрана перечислены после блоков потока: {', '.join(late)}. "
                "Первый экран рисуется до цикла по home_blocks (render.py _home), поэтому "
                "порядок в манифесте обязан начинаться с них — иначе манифест обещает "
                "порядок, которого на странице не будет",
            ))

    if not set(blocks) & CARD_BLOCKS:
        problems.append(Problem(
            where,
            "на главной нет ни одного блока с карточками "
            f"({', '.join(sorted(CARD_BLOCKS))}) — приёмка боевого обновления ищет "
            f"«{RELEASE_GATE_MARKER}» на главной и без него возвращает прежний релиз "
            "(automation/host/lords-content-refresh.sh:233)",
        ))

    columns = (layout.get("columns") or {})
    order = [columns.get("mobile"), columns.get("tablet"), columns.get("desktop")]
    if all(isinstance(v, int) for v in order) and not (order[0] <= order[1] <= order[2]):
        problems.append(Problem(
            where,
            f"колонки не растут с шириной: mobile={order[0]}, tablet={order[1]}, "
            f"desktop={order[2]}. Медиазапросы 640px и 1024px переопределяют --cols "
            "по возрастанию, и убывающий ряд означает, что на широком экране "
            "карточек меньше, чем на узком",
        ))

    blueprint = _blueprint(root)
    sections = blueprint.get("sections") or {}
    for name in manifest.get("owns") or []:
        if name not in sections:
            problems.append(Problem(
                where, f"раздел «{name}» во владении не объявлен в {BLUEPRINT_FILE.as_posix()}"))
        elif name in NON_OWNABLE:
            problems.append(Problem(
                where,
                f"раздел «{name}» нельзя взять во владение: его владение задано blueprint "
                f"(owner: {sections[name].get('owner')})",
            ))

    texts = manifest.get("sections") or {}
    for name in manifest.get("owns") or []:
        if name not in texts:
            problems.append(Problem(
                where,
                f"раздел «{name}» во владении, но текстов у него нет: владелец "
                "индексирует раздел и обязан дать ему собственные title, h1 и description "
                "(factory/lords/plan.py build_plan)",
            ))
    for name in texts:
        if name not in sections:
            problems.append(Problem(
                where, f"тексты раздела «{name}»: такого раздела в blueprint нет"))
        elif name not in NON_OWNABLE and name not in (manifest.get("owns") or []):
            problems.append(Problem(
                where,
                f"тексты раздела «{name}» не попадут на страницу: раздел не во владении, "
                "а невладельцу build_plan текстов не отдаёт",
            ))

    if manifest.get("owns_title_page") and not manifest.get("title_page"):
        problems.append(Problem(
            where,
            "owns_title_page: true без блока title_page — страница произведения "
            "останется с подстановочными шаблонами «{name}» (render.py _context)",
        ))

    theme = manifest.get("theme") or {}
    declared_themes = list(blueprint.get("themes") or [])
    if theme.get("name") and theme["name"] not in declared_themes:
        problems.append(Problem(
            where,
            f"тема «{theme['name']}» не объявлена в {BLUEPRINT_FILE.as_posix()} themes — "
            "пакет сайта с такой темой будет отклонён валидацией "
            "(factory/validation.py _lords_themes)",
        ))

    return problems


def manifest_paths(root: Path | None = None) -> list[Path]:
    return sorted((_root(root) / PROFILE_DIR).glob("*.yaml"))


def validate_repository(root: Path | None = None) -> list[Problem]:
    """Все шаблоны направления разом, включая правила между шаблонами."""
    problems: list[Problem] = []
    manifests: dict[str, dict] = {}
    for path in manifest_paths(root):
        data = load_manifest(path)
        where = path.relative_to(_root(root)).as_posix()
        problems.extend(validate_manifest(data, root=root, where=where))
        name = data.get("profile")
        if name:
            manifests[name] = data

    owner_of: dict[str, str] = {}
    for name, data in sorted(manifests.items()):
        for section in data.get("owns") or []:
            if section in owner_of:
                problems.append(Problem(
                    "направление",
                    f"раздел «{section}» во владении и у «{owner_of[section]}», и у «{name}»: "
                    "ownership_rule: exactly_one_owner_per_section",
                ))
            else:
                owner_of[section] = name

    title_owners = sorted(n for n, d in manifests.items() if d.get("owns_title_page"))
    if len(title_owners) > 1:
        problems.append(Problem(
            "направление",
            f"страницы произведений индексируют сразу несколько шаблонов: {', '.join(title_owners)}",
        ))

    known = renderer_blocks(root)
    unknown = sorted(set(known) - set(BLOCKS))
    if unknown:
        problems.append(Problem(
            "направление",
            f"рендерер рисует блоки, которых нет в реестре контракта: {', '.join(unknown)}",
        ))
    stale = sorted(set(BLOCKS) - set(known))
    if stale:
        problems.append(Problem(
            "направление",
            f"реестр контракта обещает блоки, которых рендерер не рисует: {', '.join(stale)}",
        ))

    return problems
