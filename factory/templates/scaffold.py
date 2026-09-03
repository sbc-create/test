"""Scaffold шаблона: новый шаблон получается из манифеста, а не из копии.

Что scaffold делает — ровно четыре записи, каждая в существующий реестр:

1. `blueprints/lords/profiles/<profile>.yaml` — сам шаблон;
2. `blueprints/lords/blueprint.yaml` → `profiles` — перечень шаблонов направления;
3. `blueprints/lords/blueprint.yaml` → `themes` — если тема новая. Этот список
   читает `factory/validation.py`, и пакет с неизвестной темой отклоняется;
4. `schemas/site-package.schema.json` → перечисления `tenant.seo_profile` и
   `tenant.theme`. Без этой записи пакет сайта не проходит собственную схему,
   и именно она — причина, по которой раньше шаблон нельзя было добавить одним
   файлом.

Чего scaffold **не** делает и делать не должен:

* не копирует ingestion, Content API, плеер, аналитику и приёмку — они не
  принадлежат шаблону и одинаковы у всех витрин направления;
* не создаёт `sites/<id>/package.yaml`: пакет сайта — это решение владельца о
  домене, правах и индексации, а не следствие появления шаблона;
* не трогает рендерер. Если шаблону нужен блок, которого в `_home()` нет,
  scaffold отказывается: обещать блок, которого никто не рисует, хуже, чем
  не иметь шаблона.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from factory.templates import contract

HEADER = (
    "# Шаблон направления Lords. Файл создан `python3 -m factory template-new`\n"
    "# из манифеста и проверяется `python3 -m factory template-check`.\n"
    "# Форма — schemas/template-manifest.schema.json, смысловые правила —\n"
    "# factory/templates/contract.py.\n"
)

#: Порядок ключей в файле шаблона. Совпадает с порядком в существующих
#: профилях: diff между шаблонами должен читаться, а не разъезжаться.
KEY_ORDER = (
    "schema_version", "profile", "label", "purpose",
    "owns_title_page", "owns", "theme", "layout", "sections", "title_page",
)


@dataclass
class ScaffoldResult:
    profile: str
    changes: list[tuple[str, str]] = field(default_factory=list)
    problems: list[contract.Problem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def as_dict(self) -> dict:
        return {
            "profile": self.profile,
            "changes": [{"path": p, "action": a} for p, a in self.changes],
            "problems": [str(p) for p in self.problems],
        }


def _ordered(manifest: dict) -> dict:
    out = {k: manifest[k] for k in KEY_ORDER if k in manifest}
    for key in manifest:
        if key not in out:
            out[key] = manifest[key]
    return out


def render_profile(manifest: dict) -> str:
    body = yaml.safe_dump(
        _ordered(manifest), allow_unicode=True, sort_keys=False,
        default_flow_style=False, width=96,
    )
    return HEADER + body


def _insert_into_yaml_list(text: str, key: str, value: str) -> tuple[str, bool]:
    """Добавляет `- value` в список верхнего уровня `key:` YAML-файла."""
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.startswith(f"{key}:")), None)
    if start is None:
        raise ValueError(f"список «{key}» в файле не найден")
    last = None
    for i in range(start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("- "):
            if stripped[2:].strip() == value:
                return text, False
            last = i
            continue
        if stripped and not stripped.startswith("#"):
            break
    if last is None:
        raise ValueError(f"список «{key}» пуст — вставлять некуда")
    lines.insert(last + 1, f"  - {value}\n")
    return "".join(lines), True


def _insert_into_json_enum(text: str, key: str, value: str) -> tuple[str, bool]:
    """Добавляет строковое значение в перечисление `"<key>": {"enum": [...]}`.

    Правка текстовая, а не через `json.dumps`: пересборка файла целиком
    переставила бы отступы и переносы во всей схеме пакета, и коммит перестал бы
    читаться — при том что меняется одна строка.
    """
    anchor = text.find(f'"{key}": {{')
    if anchor < 0:
        raise ValueError(f"ключ «{key}» в схеме не найден")
    enum_at = text.find('"enum": [', anchor)
    if enum_at < 0:
        raise ValueError(f"у ключа «{key}» нет перечисления")
    close = text.find("]", enum_at)
    body = text[enum_at:close]
    if f'"{value}"' in body:
        return text, False
    lines = body.splitlines()
    last = lines[-1] if len(lines) > 1 else ""
    indent = last[: len(last) - len(last.lstrip())] or "            "
    head = text[:close].rstrip()
    return f'{head},\n{indent}"{value}"\n{text[close:]}', True


def scaffold(manifest: dict, *, root: Path | None = None, force: bool = False,
             dry_run: bool = False) -> ScaffoldResult:
    """Создаёт шаблон из манифеста. Невалидный манифест ничего не пишет."""
    base = Path(root) if root else contract.PATHS.root
    name = str(manifest.get("profile") or "")
    result = ScaffoldResult(profile=name)

    result.problems = contract.validate_manifest(manifest, root=base, where="манифест")
    if result.problems:
        return result

    target = base / contract.PROFILE_DIR / f"{name}.yaml"
    if target.exists() and not force:
        result.problems.append(contract.Problem(
            "манифест", f"шаблон «{name}» уже существует: {target}. "
                        "Правь файл или передай --force"))
        return result

    writes: list[tuple[Path, str, str]] = [
        (target, render_profile(manifest), "создан" if not target.exists() else "перезаписан"),
    ]

    blueprint_path = base / contract.BLUEPRINT_FILE
    blueprint_text = blueprint_path.read_text(encoding="utf-8")
    theme_name = str((manifest.get("theme") or {}).get("name") or "")

    updated, changed = _insert_into_yaml_list(blueprint_text, "profiles", name)
    actions = ["profiles += " + name] if changed else []
    if theme_name:
        updated, theme_changed = _insert_into_yaml_list(updated, "themes", theme_name)
        if theme_changed:
            actions.append("themes += " + theme_name)
    if actions:
        writes.append((blueprint_path, updated, ", ".join(actions)))

    schema_path = base / "schemas" / contract.PACKAGE_SCHEMA_FILE
    schema_text = schema_path.read_text(encoding="utf-8")
    schema_updated, profile_changed = _insert_into_json_enum(schema_text, "seo_profile", name)
    schema_actions = ["tenant.seo_profile += " + name] if profile_changed else []
    if theme_name:
        schema_updated, theme_changed = _insert_into_json_enum(
            schema_updated, "theme", theme_name)
        if theme_changed:
            schema_actions.append("tenant.theme += " + theme_name)
    if schema_actions:
        json.loads(schema_updated)  # правка обязана оставить схему разбираемой
        writes.append((schema_path, schema_updated, ", ".join(schema_actions)))

    for path, _text, action in writes:
        result.changes.append((str(path.relative_to(base)), action))
    if dry_run:
        return result
    for path, text, _action in writes:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return result


def example_manifest(profile: str = "lords-example") -> dict:
    """Заготовка манифеста: минимальный шаблон, который проходит контракт."""
    return {
        "schema_version": 1,
        "profile": profile,
        "label": profile.replace("-", " ").title(),
        "purpose": "Зачем эта витрина отличается от соседних. Заполни одним абзацем.",
        "owns_title_page": False,
        "owns": [],
        "theme": {
            "name": "lords_dark",
            "tokens": {
                "bg": "#111111",
                "surface": "#1c1c1c",
                "surface_alt": "#252525",
                "text": "#e6e6e6",
                "muted": "#9a9a9a",
                "accent": "#79c142",
                "accent_text": "#0d0d0d",
                "border": "#333333",
                "radius": "4px",
                "container": "1240px",
                "heading_font": "'Open Sans', 'Segoe UI', Roboto, Arial, sans-serif",
            },
        },
        "layout": {
            "density": "comfortable",
            "hero": "catalog",
            "card_ratio": "2 / 3",
            "columns": {"mobile": 2, "tablet": 4, "desktop": 6},
            "facet_position": "sidebar",
            "home_blocks": ["hero_search", "latest_grid", "genre_chips"],
            "show_calendar": False,
            "show_collection_cards": False,
        },
        "sections": {
            "home": {
                "title": "Заголовок главной",
                "h1": "Заголовок первого экрана",
                "description": "Описание главной для выдачи, одно предложение.",
                "intro": "",
            },
            "search": {
                "title": "Поиск по каталогу",
                "h1": "Поиск",
                "description": "Поиск по названиям каталога. Страница закрыта от индексации.",
                "intro": "",
            },
        },
    }
