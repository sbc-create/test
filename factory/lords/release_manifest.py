"""Манифест релиза витрины: что именно выложено и чем оно собрано.

Инцидент, ради которого этот модуль написан. На `lords-02` канареечный релиз
был переключён и работал. Через сорок восемь минут очередное обновление
каталога заменило его релизом, собранным из развёрнутого checkout: шаблон
вернулся к прежнему, изменения канарейки исчезли с публичной витрины, а
переключение при этом считалось успешным.

Причина не в таймере. Обновление каталога **пересобирало витрину заново** из
того, что лежит в рабочем дереве, и переносило старый `bundle-manifest.json` в
новый релиз. Манифест утверждал одно, содержимое было другим, и расхождение
никто не проверял: в манифесте не было ни отпечатка шаблона, ни ссылки на
артефакт, которым он собран.

Отсюда правило, на котором стоит весь модуль: **релиз обязан позволять
восстановить точный шаблон, которым собран**. Манифест без отпечатка артефакта
не описывает релиз — он его пересказывает.

Разделение простое:

    закреплённый артефакт шаблона + новый снимок каталога → новый релиз

При обновлении каталога меняются снимок, страницы, идентификатор релиза и
время. Не меняются ссылка на артефакт, отпечаток шаблона, ревизия отрисовщика,
витрина, тема, источник содержимого и происхождение.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ВЕРСИЯ = "lords-release-manifest/1.0.0"

#: Отпечаток пустого массива. Встречался в поле версии шаблона на витрине,
#: которая при этом обслуживала 4 316 страниц: считалось не то, что называлось.
#: Поэтому значение запрещено явно, а не «маловероятно».
ПУСТОЙ_МАССИВ = hashlib.sha256(b"[]").hexdigest()

#: Происхождения, которые не имеют права оказаться на боевой витрине. Строка
#: ищется вхождением: `fixture/test`, `fixture:...`, `test-fixture` — одно и то
#: же по смыслу.
ЗАПРЕЩЁННОЕ_ПРОИСХОЖДЕНИЕ = ("fixture", "test", "synthetic", "sample")

ОБЯЗАТЕЛЬНЫЕ: tuple[str, ...] = (
    "tenant_id",
    "domain",
    "theme",
    "template_package_ref",
    "template_artifact_ref",
    "template_digest",
    "renderer_revision",
    "content_snapshot_id",
    "content_source",
    "content_count",
    "created_at",
    "created_by",
    "previous_release",
    "rollback_target",
    "release_reason",
    "production_authorized",
)

#: Поля, которые описывают именно шаблон. Сменить их вправе только
#: канареечная выкладка, и только назвав их явно.
ШАБЛОННЫЕ: tuple[str, ...] = (
    "template_package_ref",
    "template_artifact_ref",
    "template_digest",
    "renderer_revision",
)

#: Поля, которые обновление каталога менять не вправе. Список — договор между
#: обновлением данных и выкладкой шаблона: всё, чего здесь нет, обновляемо.
НЕИЗМЕНЯЕМЫЕ: tuple[str, ...] = (
    "tenant_id",
    "domain",
    "theme",
    "template_package_ref",
    "template_artifact_ref",
    "template_digest",
    "renderer_revision",
    "content_source",
    "production_authorized",
)

#: Поля, которые обновление каталога обязано обновить. Релиз, у которого не
#: изменился ни снимок, ни счёт записей, ни время, — это тот же релиз под новым
#: именем.
ОБНОВЛЯЕМЫЕ: tuple[str, ...] = (
    "content_snapshot_id",
    "content_count",
    "created_at",
    "release_reason",
    "previous_release",
)


class ManifestError(Exception):
    """Манифест не описывает релиз. Переключение не выполняется."""


def прочитать(путь: Path | str) -> dict[str, Any]:
    п = Path(путь)
    try:
        данные = json.loads(п.read_text(encoding="utf-8"))
    except FileNotFoundError as ошибка:
        raise ManifestError(f"манифеста релиза нет: {п}") from ошибка
    except (OSError, ValueError) as ошибка:
        raise ManifestError(f"манифест релиза не читается: {п}: {ошибка}") from ошибка
    if not isinstance(данные, dict):
        raise ManifestError(f"манифест релиза не объект: {п}")
    return данные


def нарушения(манифест: dict[str, Any], *, artifact_root: Path | str | None = None) -> list[str]:
    """Список нарушений инвариантов. Пустой список — релиз пригоден.

    Возвращается список, а не первое нарушение: отказ, называющий одну причину
    из четырёх, заставляет чинить по кругу.
    """
    из: list[str] = []

    for поле in ОБЯЗАТЕЛЬНЫЕ:
        if поле not in манифест:
            из.append(f"нет поля {поле}")
        elif манифест[поле] is None and поле not in ("previous_release", "rollback_target"):
            из.append(f"поле {поле} пустое")

    # Первый релиз витрины откатывать некуда, и требовать цель отката от него
    # значило бы требовать выдумать её. Но у релиза, за которым есть история,
    # пустая цель отката — это отказ от отката, а не его отсутствие.
    if манифест.get("rollback_target") is None and манифест.get("previous_release") is not None:
        из.append("цель отката пуста при существующем предыдущем релизе")

    отпечаток = str(манифест.get("template_digest") or "")
    if not отпечаток:
        из.append("отпечаток шаблона пуст: восстановить шаблон релиза нечем")
    elif отпечаток == ПУСТОЙ_МАССИВ:
        из.append(
            "отпечаток шаблона равен отпечатку пустого массива: "
            "считалось не то, что называлось"
        )
    elif len(отпечаток) != 64 or not all(с in "0123456789abcdef" for с in отпечаток.lower()):
        из.append(f"отпечаток шаблона не sha256: {отпечаток[:16]}…")

    for поле in ("content_source", "template_package_ref", "release_reason"):
        значение = str(манифест.get(поле) or "").lower()
        for запрет in ЗАПРЕЩЁННОЕ_ПРОИСХОЖДЕНИЕ:
            if запрет in значение:
                из.append(f"происхождение {поле}={значение!r} не боевое ({запрет})")
                break

    if манифест.get("production_authorized") is not True:
        из.append("витрина не объявлена разрешённой к боевой выкладке")

    счёт = манифест.get("content_count")
    if not isinstance(счёт, int) or isinstance(счёт, bool) or счёт <= 0:
        из.append(f"счёт записей каталога негоден: {счёт!r}")

    ссылка = str(манифест.get("template_artifact_ref") or "")
    if ссылка and artifact_root is not None:
        путь = Path(artifact_root) / ссылка if not Path(ссылка).is_absolute() else Path(ссылка)
        if not путь.is_file():
            из.append(f"артефакт шаблона недоступен: {ссылка}")
        else:
            фактический = отпечаток_файла(путь)
            if отпечаток and фактический != отпечаток:
                из.append(
                    f"артефакт шаблона изменён: {фактический[:12]}… вместо {отпечаток[:12]}…"
                )

    return из


def проверить(манифест: dict[str, Any], *, artifact_root: Path | str | None = None) -> None:
    беды = нарушения(манифест, artifact_root=artifact_root)
    if беды:
        raise ManifestError("; ".join(беды))


def отпечаток_файла(путь: Path | str) -> str:
    ш = hashlib.sha256()
    with open(путь, "rb") as ф:
        for кусок in iter(lambda: ф.read(1024 * 1024), b""):
            ш.update(кусок)
    return ш.hexdigest()


def следующий(
    текущий: dict[str, Any],
    *,
    content_snapshot_id: str,
    content_count: int,
    created_at: str,
    created_by: str,
    previous_release: str,
    release_reason: str = "content-refresh",
    template: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Манифест следующего релиза.

    Шаблонные поля переносятся ссылкой на прежние значения, а не пересчитываются
    заново: пересчёт из рабочего дерева и есть та подмена, из-за которой
    канарейка исчезала.

    `template` — единственный способ сменить шаблон, и он именной. Смена
    шаблона происходит по отдельному решению (канареечная выкладка), под своей
    причиной и с записью прежних значений в самом манифесте. Молчаливая смена
    невозможна: обновление каталога `template` не передаёт, а без него поля
    только переносятся.
    """
    проверить(текущий)
    новый = {поле: текущий[поле] for поле in НЕИЗМЕНЯЕМЫЕ}
    if template:
        лишние = set(template) - set(ШАБЛОННЫЕ)
        if лишние:
            raise ManifestError(
                f"смена шаблона несёт поля, к шаблону не относящиеся: {sorted(лишние)}")
        новый["superseded_template"] = {поле: текущий.get(поле) for поле in ШАБЛОННЫЕ}
        новый.update(template)
    новый.update(
        {
            "content_snapshot_id": content_snapshot_id,
            "content_count": int(content_count),
            "created_at": created_at,
            "created_by": created_by,
            "previous_release": previous_release,
            "rollback_target": previous_release or текущий.get("rollback_target"),
            "release_reason": release_reason,
            "manifest_version": ВЕРСИЯ,
        }
    )
    return новый


def шаблон_сохранён(до: dict[str, Any], после: dict[str, Any]) -> list[str]:
    """Чем новый релиз отличается от прежнего в шаблонной части.

    Пустой список — шаблон пережил обновление каталога. Именно это и требуется
    доказать после каждого обновления.
    """
    разошлось = []
    for поле in НЕИЗМЕНЯЕМЫЕ:
        if до.get(поле) != после.get(поле):
            разошлось.append(f"{поле}: {до.get(поле)!r} -> {после.get(поле)!r}")
    return разошлось


def каталог_обновлён(до: dict[str, Any], после: dict[str, Any]) -> list[str]:
    """Чего не хватает, чтобы считать каталог обновившимся.

    Обратная проверка к `шаблон_сохранён`: сохранить шаблон, ничего не обновив,
    — это остановка обновления, а не решение задачи.
    """
    беды = []
    if до.get("content_snapshot_id") == после.get("content_snapshot_id"):
        беды.append("снимок каталога не изменился")
    if до.get("created_at") == после.get("created_at"):
        беды.append("время создания не изменилось")
    return беды
