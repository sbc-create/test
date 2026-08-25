"""Направления и их потребители — из конфигурации, не из кода.

Требование задания: «в будущем направления должны добавляться конфигурацией без
переписывания приложения». Поэтому здесь нет ни списка `yami/lords/amedia`, ни
`if portfolio == ...`. Есть загрузчик `config/secret-hub.json`, проверка по
схеме и две реализации доставки (`file_mount`, `systemd_credential`), которые
выбираются по полю `kind`. Новое направление — новая запись в конфигурации.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from factory.errors import BlockedInput

#: Путь к реестру. Переопределяется переменной — в тестах и при переносе стенда.
CONFIG_ENV = "SECRET_HUB_CONFIG"
DEFAULT_CONFIG = "config/secret-hub.json"
SCHEMA_NAME = "secret-hub.schema.json"


@dataclass(frozen=True)
class Reload:
    kind: str
    note: str = ""

    @property
    def restarts_unit(self) -> bool:
        return self.kind == "systemd"


@dataclass(frozen=True)
class Consumer:
    """Куда именно направление кладёт credentials.

    Значений здесь нет и не появится: `files` — имена файлов, а не содержимое.
    """

    id: str
    kind: str
    title: str
    directory: Path
    files: dict[str, str]
    owner: str
    group: str
    file_mode: int
    directory_mode: int
    reload: Reload
    unit: str | None = None
    dropin: Path | None = None
    credential_names: dict[str, str] = field(default_factory=dict)
    compose_file: Path | None = None
    expect_mount_target: str | None = None

    def path_for(self, field_name: str) -> Path:
        return self.directory / self.files[field_name]

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "directory": str(self.directory),
            "unit": self.unit,
            "reload": self.reload.kind,
        }


@dataclass(frozen=True)
class BlockedTarget:
    status: str
    reason: str
    required_input: str

    def as_dict(self) -> dict:
        return {"status": self.status, "reason": self.reason, "required_input": self.required_input}


@dataclass(frozen=True)
class Portfolio:
    id: str
    title: str
    enabled: bool
    consumers: tuple[Consumer, ...]
    blocked_target: BlockedTarget | None = None

    @property
    def deployable(self) -> bool:
        return self.enabled and self.blocked_target is None and bool(self.consumers)

    def consumer(self, consumer_id: str) -> Consumer:
        for item in self.consumers:
            if item.id == consumer_id:
                return item
        raise BlockedInput(
            f"Потребитель «{consumer_id}» не описан в направлении «{self.id}».",
            field="config/secret-hub.json",
            required_input="Запись consumers[] с этим id",
            blocks_stage="VALIDATING",
        )

    def units(self) -> tuple[str, ...]:
        """Unit'ы, которые apply этого направления имеет право перезапускать.

        Перечень нужен проверке изоляции: «Yami не должен затрагивать Lords»
        доказывается сравнением этих множеств, а не обещанием в документации.
        """
        return tuple(c.unit for c in self.consumers if c.unit and c.reload.restarts_unit)

    def directories(self) -> tuple[Path, ...]:
        return tuple(c.directory for c in self.consumers)


@dataclass(frozen=True)
class VerifyContract:
    base_url: str
    path: str
    method: str
    auth_header: str
    auth_scheme: str
    timeout_ms: int
    provenance: str
    note: str = ""

    @property
    def url(self) -> str:
        return self.base_url.rstrip("/") + "/" + self.path.lstrip("/")


@dataclass(frozen=True)
class HubConfig:
    source: Path
    store_dir: Path
    socket_path: Path
    control_group: str | None
    provider_name: str
    verify: VerifyContract
    portfolios: tuple[Portfolio, ...]

    def portfolio(self, portfolio_id: str) -> Portfolio:
        for item in self.portfolios:
            if item.id == portfolio_id:
                return item
        known = ", ".join(p.id for p in self.portfolios) or "—"
        raise BlockedInput(
            f"Направление «{portfolio_id}» не описано в реестре. Известные: {known}.",
            field="config/secret-hub.json",
            required_input="Запись portfolios[] с этим id",
            blocks_stage="VALIDATING",
        )

    def ids(self) -> tuple[str, ...]:
        return tuple(p.id for p in self.portfolios)

    @property
    def db_path(self) -> Path:
        return self.store_dir / "store.sqlite3"

    @property
    def backup_dir(self) -> Path:
        return self.store_dir / "backups"


def config_path(root: Path | None = None) -> Path:
    override = os.environ.get(CONFIG_ENV)
    if override:
        return Path(override).expanduser()
    from factory.paths import PATHS

    return (root or PATHS.root) / DEFAULT_CONFIG


def _mode(raw: str) -> int:
    return int(raw, 8)


def _consumer(raw: dict) -> Consumer:
    reload_raw = raw.get("reload") or {"kind": "none"}
    return Consumer(
        id=raw["id"],
        kind=raw["kind"],
        title=raw["title"],
        directory=Path(raw["directory"]),
        files=dict(raw["files"]),
        owner=raw["owner"],
        group=raw["group"],
        file_mode=_mode(raw["file_mode"]),
        directory_mode=_mode(raw["directory_mode"]),
        reload=Reload(kind=reload_raw["kind"], note=reload_raw.get("note", "")),
        unit=raw.get("unit"),
        dropin=Path(raw["dropin"]) if raw.get("dropin") else None,
        credential_names=dict(raw.get("credential_names") or {}),
        compose_file=Path(raw["compose_file"]) if raw.get("compose_file") else None,
        expect_mount_target=raw.get("expect_mount_target"),
    )


def _portfolio(raw: dict) -> Portfolio:
    blocked_raw = raw.get("blocked_target")
    return Portfolio(
        id=raw["id"],
        title=raw["title"],
        enabled=bool(raw["enabled"]),
        consumers=tuple(_consumer(c) for c in raw.get("consumers") or ()),
        blocked_target=BlockedTarget(**blocked_raw) if blocked_raw else None,
    )


def _validate(document: dict, source: Path) -> None:
    """Проверка по схеме. Схема — источник правды, а не документация к ней."""
    from factory.paths import PATHS

    schema_file = PATHS.schemas / SCHEMA_NAME
    try:
        import jsonschema
    except ModuleNotFoundError:  # pragma: no cover - в боевом окружении есть
        return
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        where = "/".join(str(p) for p in first.path) or "<корень>"
        raise BlockedInput(
            f"Реестр {source} не соответствует схеме: {where}: {first.message}",
            field=str(source),
            required_input="Исправить реестр по schemas/secret-hub.schema.json",
            blocks_stage="VALIDATING",
        )


def load(path: Path | None = None) -> HubConfig:
    source = path or config_path()
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BlockedInput(
            f"Реестр направлений {source} не найден.",
            field=str(source),
            required_input="config/secret-hub.json по schemas/secret-hub.schema.json",
            blocks_stage="VALIDATING",
        ) from None
    except json.JSONDecodeError as exc:
        raise BlockedInput(
            f"Реестр направлений {source} не разобран: {exc.msg} (строка {exc.lineno}).",
            field=str(source),
            required_input="Корректный JSON",
            blocks_stage="VALIDATING",
        ) from None

    _validate(document, source)

    store_dir = Path(document["store_dir"])
    _reject_repository_path(store_dir, source)

    verify_raw = document["provider"]["verify"]
    verify = VerifyContract(
        base_url=verify_raw["base_url"],
        path=verify_raw["path"],
        method=verify_raw["method"],
        auth_header=verify_raw["auth_header"],
        auth_scheme=verify_raw["auth_scheme"],
        timeout_ms=int(verify_raw.get("timeout_ms", 15000)),
        provenance=verify_raw["provenance"],
        note=verify_raw.get("note", ""),
    )

    portfolios = tuple(_portfolio(p) for p in document["portfolios"])
    _reject_duplicate_targets(portfolios, source)

    return HubConfig(
        source=source,
        store_dir=store_dir,
        socket_path=Path(document["socket_path"]),
        control_group=document.get("control_group"),
        provider_name=document["provider"]["name"],
        verify=verify,
        portfolios=portfolios,
    )


def _reject_repository_path(store_dir: Path, source: Path) -> None:
    from factory.paths import PATHS

    root = PATHS.root.resolve()
    try:
        candidate = store_dir.resolve()
    except OSError:  # pragma: no cover - каталог может ещё не существовать
        candidate = store_dir
    if candidate == root or str(candidate).startswith(str(root) + os.sep):
        raise BlockedInput(
            f"store_dir {store_dir} указывает внутрь репозитория. Хранилище живёт только снаружи.",
            field=str(source),
            required_input="Путь вне репозитория, например /var/lib/site-factory-secret-hub",
            blocks_stage="VALIDATING",
        )


def _reject_duplicate_targets(portfolios: tuple[Portfolio, ...], source: Path) -> None:
    """Один каталог или unit не может принадлежать двум направлениям.

    Иначе изоляция направлений превращается в пожелание: apply одного
    направления молча переписал бы файлы другого, а откат вернул бы чужую
    версию. Дешевле запретить это на загрузке реестра.
    """
    seen_dirs: dict[Path, str] = {}
    seen_units: dict[str, str] = {}
    seen_ids: set[str] = set()
    for portfolio in portfolios:
        if portfolio.id in seen_ids:
            raise BlockedInput(
                f"Направление «{portfolio.id}» описано дважды.",
                field=str(source),
                required_input="Уникальные id направлений",
                blocks_stage="VALIDATING",
            )
        seen_ids.add(portfolio.id)
        for consumer in portfolio.consumers:
            owner = seen_dirs.get(consumer.directory)
            if owner and owner != portfolio.id:
                raise BlockedInput(
                    f"Каталог {consumer.directory} назначен направлениям «{owner}» и "
                    f"«{portfolio.id}». Общий каталог ломает изоляцию направлений.",
                    field=str(source),
                    required_input="Отдельный каталог на каждое направление",
                    blocks_stage="VALIDATING",
                )
            seen_dirs[consumer.directory] = portfolio.id
            if consumer.unit:
                unit_owner = seen_units.get(consumer.unit)
                if unit_owner and unit_owner != portfolio.id:
                    raise BlockedInput(
                        f"Unit {consumer.unit} назначен направлениям «{unit_owner}» и "
                        f"«{portfolio.id}».",
                        field=str(source),
                        required_input="Отдельный unit на каждое направление",
                        blocks_stage="VALIDATING",
                    )
                seen_units[consumer.unit] = portfolio.id
