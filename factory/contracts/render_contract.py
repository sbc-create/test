"""Контракт отрисовки: `RenderSpec` на входе, `ArtifactManifest` на выходе.

Подготовка к отделению рендерера, а не само отделение. Ни нового процесса, ни
нового юнита здесь нет и не появится: физическое отделение разрешено только
после теневого прогона с побайтовым сравнением артефактов и отдельного
канареечного цикла.

Зачем контракт нужен раньше отделения. Сейчас `render_site` принимает семь
разнородных аргументов, из которых три необязательных меняют смысл
результата, а отдаёт объект с изменяемыми словарями. Отделить такое нельзя:
через границу процесса передаётся не объект, а описание, и пока описания нет,
неизвестно даже, что именно придётся передавать.

Оба вида описаны здесь, выведены из того, что рендерер действительно
принимает и производит, и снабжены версией. Версия не украшение: сторона,
получившая описание чужой версии, обязана отказать, а не догадываться.

Чего в контракте намеренно нет:

* самих страниц. Артефакт описывает результат — состав, отпечатки, счёт, — а
  не переносит гигабайты. Страницы остаются на диске, и манифест на них
  ссылается;
* объекта каталога. Через границу процесса он не проходит: передаётся ссылка
  на снимок и его отпечаток;
* умолчаний, меняющих смысл. `catalog=None` у `render_site` означает не
  «пустой сайт», а «источника нет», и в описании это отдельное поле, а не
  отсутствие значения.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any

#: Версия контракта. Меняется при любом изменении состава полей.
ВЕРСИЯ = "render-contract/1.0.0"


class ContractError(ValueError):
    """Описание не соответствует контракту."""


@dataclasses.dataclass(frozen=True)
class RenderSpec:
    """Что нужно отрисовать. Всё, что рендерер обязан знать, и ничего сверх.

    Передаётся ссылками, а не содержимым: пакет сайта и снимок каталога живут
    на диске, и переносить их через границу процесса незачем.
    """

    site_id: str
    #: Путь к пакету сайта относительно корня.
    package_ref: str
    #: Ссылка на снимок каталога и его отпечаток. `None` — источника нет, и это
    #: не то же самое, что пустой каталог: без источника разделов не возникает,
    #: а витрина честно отдаёт сайт без каталога.
    catalog_ref: str | None
    catalog_digest: str | None
    #: Ревизия шаблона, которым отрисовывать. Закрепление, а не пожелание.
    template_revision: str
    #: Подмножество адресов для частичной пересборки. Пустое множество —
    #: полная отрисовка; отличать его от `None` не требуется, потому что
    #: «пересобрать ничего» не имеет смысла.
    only_slugs: tuple[str, ...] = ()
    publisher_id: str | None = None
    contract_version: str = ВЕРСИЯ

    def __post_init__(self) -> None:
        if not self.site_id:
            raise ContractError("описание без витрины: отрисовывать нечего")
        if not self.package_ref:
            raise ContractError("описание без пакета сайта")
        if not self.template_revision:
            raise ContractError(
                "описание без ревизии шаблона: отрисовка из рабочего дерева и "
                "есть та подмена, из-за которой канарейка исчезала")
        if (self.catalog_ref is None) != (self.catalog_digest is None):
            raise ContractError(
                "снимок каталога назван наполовину: ссылка без отпечатка "
                "непроверяема, отпечаток без ссылки нечитаем")

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, данные: dict[str, Any]) -> RenderSpec:
        версия = данные.get("contract_version")
        if версия != ВЕРСИЯ:
            raise ContractError(
                f"описание версии {версия!r}, а эта сторона понимает {ВЕРСИЯ!r}: "
                f"догадываться о чужой версии нельзя")
        известные = {п.name for п in dataclasses.fields(cls)}
        лишние = sorted(set(данные) - известные)
        if лишние:
            raise ContractError(f"описание несёт неизвестные поля: {лишние}")
        значения = dict(данные)
        значения["only_slugs"] = tuple(значения.get("only_slugs") or ())
        return cls(**значения)


@dataclasses.dataclass(frozen=True)
class ArtifactManifest:
    """Что получилось. Состав результата, а не сам результат.

    Побайтовое сравнение теневого прогона делается по `pages_digest`: он
    считается от состава и отпечатков страниц, а не от времени сборки, поэтому
    два одинаковых прогона обязаны дать одинаковое значение.
    """

    site_id: str
    template_revision: str
    #: Отпечаток состава страниц: путь и отпечаток содержимого каждой.
    pages_digest: str
    pages_total: int
    html_total: int
    #: Отпечаток снимка каталога, которым отрисовано. Позволяет отличить
    #: «изменился шаблон» от «изменились данные», не сравнивая страницы.
    catalog_digest: str | None
    #: Состояния типов содержимого: почему раздела нет, если его нет.
    type_states: dict[str, str] = dataclasses.field(default_factory=dict)
    contract_version: str = ВЕРСИЯ

    def __post_init__(self) -> None:
        if self.pages_total < 0 or self.html_total < 0:
            raise ContractError("отрицательное число страниц")
        if self.html_total > self.pages_total:
            raise ContractError(
                f"документов {self.html_total} при {self.pages_total} страницах: "
                f"часть больше целого")
        if not self.pages_digest:
            raise ContractError(
                "манифест без отпечатка состава: сравнить теневой прогон нечем")

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, данные: dict[str, Any]) -> ArtifactManifest:
        версия = данные.get("contract_version")
        if версия != ВЕРСИЯ:
            raise ContractError(
                f"манифест версии {версия!r}, а эта сторона понимает {ВЕРСИЯ!r}")
        известные = {п.name for п in dataclasses.fields(cls)}
        лишние = sorted(set(данные) - известные)
        if лишние:
            raise ContractError(f"манифест несёт неизвестные поля: {лишние}")
        return cls(**данные)


def отпечаток_состава(страницы: dict[str, bytes | str]) -> str:
    """Отпечаток состава страниц: путь и содержимое каждой, время не входит.

    Два одинаковых прогона обязаны дать одинаковое значение — иначе теневое
    сравнение показывало бы расхождение там, где его нет.
    """
    ш = hashlib.sha256()
    for путь in sorted(страницы):
        тело = страницы[путь]
        ш.update(путь.encode("utf-8"))
        ш.update(b"\0")
        ш.update(тело if isinstance(тело, bytes) else тело.encode("utf-8"))
        ш.update(b"\0")
    return ш.hexdigest()


def сравнить(один: ArtifactManifest, другой: ArtifactManifest) -> list[str]:
    """Чем два манифеста отличаются. Пустой список — артефакты совпадают.

    Нужно для теневого прогона: отделение рендерера разрешено только после
    того, как старый и новый дадут одинаковый состав.
    """
    расхождения = []
    for поле in ("site_id", "template_revision", "pages_digest", "pages_total",
                 "html_total", "catalog_digest"):
        а, б = getattr(один, поле), getattr(другой, поле)
        if а != б:
            расхождения.append(f"{поле}: {а!r} против {б!r}")
    if один.type_states != другой.type_states:
        расхождения.append(
            f"состояния типов: {json.dumps(один.type_states, sort_keys=True, ensure_ascii=False)}"
            f" против {json.dumps(другой.type_states, sort_keys=True, ensure_ascii=False)}")
    return расхождения
