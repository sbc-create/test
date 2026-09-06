"""Отпечаток шаблонного слоя: чем именно отличается одна сдача от другой.

Коммит отвечает на вопрос «что лежит в репозитории», но не на вопрос «изменился
ли шаблон»: правка отчёта и правка рендерера дают одинаково новый SHA. Отпечаток
считается только по тем файлам, которые определяют вид и поведение витрины,
поэтому его совпадение означает, что витрина осталась прежней, а расхождение —
что её нужно пересматривать.

Состав намеренно узкий и перечислен явно. Класть сюда весь репозиторий значило
бы получить второй SHA коммита; класть один рендерер — пропустить смену темы
или профиля, от которой витрина меняется целиком.

Отпечаток воспроизводим: та же ревизия даёт то же значение на любой машине.
Порядок файлов фиксирован сортировкой, содержимое читается байтами, имя файла
входит в хеш — переименование обязано менять отпечаток.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from factory.paths import PATHS

#: Файлы и каталоги, определяющие шаблонный слой. Пути относительны корня.
TEMPLATE_SOURCES: tuple[str, ...] = (
    "blueprints/lords/blueprint.yaml",
    "blueprints/lords/profiles",
    "factory/lords/render.py",
    "factory/lords/theme.py",
    "factory/lords/player.py",
    "factory/lords/pagination.py",
    "factory/templates",
    "schemas/template-manifest.schema.json",
    "tests/e2e-lords/visual-baseline.json",
)


def _files(root: Path) -> list[Path]:
    found: list[Path] = []
    for entry in TEMPLATE_SOURCES:
        target = root / entry
        if target.is_dir():
            found.extend(
                p for p in target.rglob("*")
                if p.is_file() and p.suffix in (".py", ".yaml", ".yml", ".json")
                and "__pycache__" not in p.parts
            )
        elif target.is_file():
            found.append(target)
    return sorted(found)


def compute(root: Path | None = None) -> dict:
    """Отпечаток и состав, по которому он посчитан."""
    base = root or PATHS.root
    digest = hashlib.sha256()
    members: list[dict] = []
    for path in _files(base):
        relative = path.relative_to(base).as_posix()
        body = path.read_bytes()
        one = hashlib.sha256(body).hexdigest()
        # Имя входит в хеш вместе с содержимым: иначе переименование файла
        # осталось бы незамеченным, хотя сборка от него зависит.
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(body)
        members.append({"path": relative, "sha256": one, "bytes": len(body)})
    return {
        "algorithm": "sha256",
        "template_digest": digest.hexdigest(),
        "files": len(members),
        "members": members,
    }


def short(root: Path | None = None) -> str:
    return compute(root)["template_digest"][:16]
