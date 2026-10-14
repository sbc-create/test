"""Паспорт ячейки: куда именно адресована задача.

Реестр отвечает на один вопрос — «этот домен, этот site_id: какой репозиторий,
какой шаблон, какие закреплённые версии, какой сервер». Ошибка в этом ответе
дороже всех прочих: задача про поиск на одном домене, выполненная в соседнем
проекте, обнаруживается уже на живом сайте.

Поэтому разрешение имени здесь нарочито негибкое:

* совпадение только точное — ни по префиксу, ни по похожести;
* неоднозначность — отказ, а не выбор первого подходящего;
* отсутствие записи — отказ, а не создание записи на лету.

Реестр не заводит вторую правду о сайте. Идентичность (site_id, домены) живёт в
`config/site-profiles/*.json`; здесь добавлено только то, чего там нет:
репозиторий, закреплённые версии, цель выката и последний известный релиз.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.cell import ledger
from factory.paths import PATHS

SCHEMA_VERSION = "1.0"
REGISTRY_PATH = "config/site-cells.json"

#: Ветки, с которых выпуск разрешён. Список живёт здесь, а не в триггере:
#: триггер работает от непривилегированной стороны, и его представление о
#: разрешённой ветке ничего не доказывает исполнителю. Эксперименты и форки
#: сюда не попадают по построению — они не разрешённая ветка.
ВЕТКИ_ВЫПУСКА = ("main", "claude/extract-*", "release/*")


def ветка_разрешена(ref: str) -> bool:
    from fnmatch import fnmatch
    return any(fnmatch(ref or "", шаблон) for шаблон in ВЕТКИ_ВЫПУСКА)


#: Куда установщик записывает абсолютные пути, которые нельзя вывести из места
#: установки. Файл принадлежит root и лежит рядом с корневой копией пакета.
ФАЙЛ_УСТАНОВКИ = "cell-install.json"

#: Переменная окружения того же назначения — для стенда и тестов.
СРЕДА_РЕПОЗИТОРИЕВ = "CELL_SITE_REPOS_ROOT"


def корень_репозиториев() -> Path:
    """Основание для относительных `repo.path` из реестра.

    Корневая копия исполнителя и рабочие копии репозиториев сайтов лежат в
    разных местах, и вывести второе из первого нельзя: это разные сущности с
    разными владельцами. Значение записывает root при установке.

    Почему это не расширяет доверие. Репозиторий доступен на запись обычной
    учётной записи, но КОРЕНЬ берётся отсюда, а не из заявки, и записан root'ом.
    Код репозитория root не исполняет ни разу: сборка идёт под учётной записью
    сайта (`privileged.собрать_без_прав`), root получает готовый файл и сверяет
    у него коммит и digest. Размещение, учётная запись, юнит и порт по-прежнему
    берутся только из корневой копии реестра.
    """
    из_среды = os.environ.get(СРЕДА_РЕПОЗИТОРИЕВ)
    if из_среды:
        return Path(из_среды).resolve()
    запись = PATHS.root / ФАЙЛ_УСТАНОВКИ
    if запись.is_file():
        try:
            значение = json.loads(запись.read_text(encoding="utf-8")).get("site_repos_root")
        except (OSError, ValueError):
            значение = None
        if значение:
            return Path(значение).resolve()
    return PATHS.root.resolve()

#: Идентификаторы издателя, отозванные поставщиком. Подставить такой в плеер
#: значит получить пустой плеер на живом сайте, поэтому запрет проверяется, а не
#: описывается в документации.
#:
#: 2026-10-01: из набора исключён 10332 — владелец назначил его домену
#: animedia.icu отдельным заданием (D137).
#:
#: 2026-10-14: из набора исключены 10331 и 10333 — владелец назначил их
#: доменам zonafilm.space и animedia.space заданием, которое прямо называет это
#: разрешением на замену (D213). Набор стал пустым, и это не отмена проверки:
#: она сработает, как только в набор впишут новое значение.
#:
#: Самостоятельно, «чтобы выпуск прошёл», набор сокращать нельзя: проверить
#: снаружи, работает ли идентификатор, нечем — плейлист провайдера отвечает
#: одинаково и на действующий, и на несуществующий номер. Поэтому основание
#: всегда одно — названное и датированное указание владельца, а страховка —
#: снимок прежних значений и проверка воспроизведения после выпуска.
RETIRED_PUBLISHER_IDS = frozenset()

SITE_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
DOMAIN_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")


class RegistryError(RuntimeError):
    pass


class UnknownCell(RegistryError):
    """Записи нет. Догадка по похожему имени здесь запрещена намеренно."""


class AmbiguousCell(RegistryError):
    """Под запрос подходит больше одной ячейки — значит останавливаемся."""


class RetiredPublisherId(RegistryError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def registry_path() -> Path:
    """Путь к реестру ячеек.

    Переменная `SITE_CELLS_REGISTRY` нужна изолированному стенду и
    производителям содержимого: у стенда свой реестр, и подменять боевой файл
    ради проверки нельзя. В обычном прогоне переменной нет и путь обычный.
    """
    из_среды = os.environ.get("SITE_CELLS_REGISTRY")
    if из_среды:
        return Path(из_среды)
    return PATHS.root / REGISTRY_PATH


@dataclass(frozen=True)
class Cell:
    """Паспорт одного сайта."""

    site_id: str
    domain: str
    aliases: tuple[str, ...]
    repo: dict[str, Any]
    template: dict[str, Any]
    pins: dict[str, Any]
    deploy_target: dict[str, Any]
    publisher: dict[str, Any]
    data: dict[str, Any]
    deployed: dict[str, Any] = field(default_factory=dict)
    content_revision: str | None = None
    last_update: str | None = None
    backup: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)
    #: Фактическое размещение на хосте: служба, порт, каталог данных, режим
    #: подхвата снимка. Читают производители содержимого — до этого поля они
    #: знали про службы по собственным спискам и после переноса сайта звали
    #: прежний unit по имени.
    runtime: dict[str, Any] = field(default_factory=dict)
    #: Правила выпуска: удержание, если сайтом занят кто-то другой.
    release: dict[str, Any] = field(default_factory=dict)
    #: Режим индексации, объявленный владельцем: `desired_state` — какой режим
    #: объявлен, `open_authorized` — разрешено ли открытие ВООБЩЕ. Поле читает
    #: исполнитель: разрешение на снятие запрета спрашивается там, где запрет
    #: снимается, а не только в вызывающей операции.
    indexing: dict[str, Any] = field(default_factory=dict)
    #: Подключённая аналитика действующего сайта: счётчик и его состояние.
    #: Поле появилось в файле раньше, чем в этой модели, и записью паспорта
    #: снималось — измерено 2026-10-13: блок есть у 15 ячеек из 33.
    analytics: dict[str, Any] = field(default_factory=dict)
    #: Исключение из общего продвижения, объявленное владельцем: `excluded` —
    #: исключён ли сайт, `scopes` — из чего именно, `keeps` — что продолжает
    #: работать, `reason`/`authority` — почему и чьим решением.
    #:
    #: Отсутствие блока означает «не исключён»: так поведение действующих
    #: сайтов не меняется от появления поля. Обратное (отсутствие = исключён)
    #: выключило бы продвижение всей сети одной правкой кода.
    promotion: dict[str, Any] = field(default_factory=dict)
    status: str = "planned"

    @property
    def domains(self) -> tuple[str, ...]:
        return (self.domain, *self.aliases)

    @property
    def repo_path(self) -> Path:
        """Рабочая копия репозитория сайта — одна на всю фабрику.

        Раньше каждый вызывающий выводил путь сам, и выводили по-разному:
        исполнитель — от PATHS.root, триггер — вообще без основания. Для
        установленной корневой копии PATHS.root это /usr/local/lib/site-factory-cell,
        репозиториев сайтов там нет, и первая же настоящая заявка была отвергнута
        с «в репозитории нет …/tools/build_release.py». Основание теперь одно.
        """
        path = self.repo.get("path")
        if not path:
            raise RegistryError(f"{self.site_id}: у ячейки не записан путь репозитория")
        p = Path(path)
        if p.is_absolute():
            return p.resolve()
        корень = корень_репозиториев()
        полный = (корень / p).resolve()
        # Реестр — файл; запись вида `../../etc` в нём не должна уводить наружу.
        if not str(полный).startswith(str(корень) + os.sep):
            raise RegistryError(
                f"{self.site_id}: repo.path уводит за пределы {корень}: {полный}")
        return полный

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "domain": self.domain,
            "aliases": list(self.aliases),
            "status": self.status,
            "repo": dict(self.repo),
            "template": dict(self.template),
            "pins": dict(self.pins),
            "deploy_target": dict(self.deploy_target),
            "publisher": dict(self.publisher),
            "data": dict(self.data),
            "deployed": dict(self.deployed),
            "content_revision": self.content_revision,
            "last_update": self.last_update,
            "backup": dict(self.backup),
            "resources": dict(self.resources),
            "runtime": dict(self.runtime),
            "release": dict(self.release),
            # `indexing` и `promotion` перечислены здесь не для полноты.
            # Измерено 2026-10-13 на копии действующего реестра: блок indexing
            # есть у 19 ячеек из 33, а `register(replace=True)` его снимал —
            # печать паспорта его не перечисляла. Для indexing потеря ведёт в
            # безопасную сторону (режим без файла состояния вычисляется
            # закрытым), но записанная причина пропадала вместе с блоком; для
            # promotion потеря отменяла бы само исключение из продвижения, то
            # есть следующая общая выкладка подключила бы домен обратно.
            "indexing": dict(self.indexing),
            "analytics": dict(self.analytics),
            "promotion": dict(self.promotion),
        }


def _cell(raw: dict[str, Any]) -> Cell:
    return Cell(
        site_id=raw["site_id"],
        domain=raw["domain"],
        aliases=tuple(raw.get("aliases") or ()),
        repo=raw.get("repo") or {},
        template=raw.get("template") or {},
        pins=raw.get("pins") or {},
        deploy_target=raw.get("deploy_target") or {},
        publisher=raw.get("publisher") or {},
        data=raw.get("data") or {},
        deployed=raw.get("deployed") or {},
        content_revision=raw.get("content_revision"),
        last_update=raw.get("last_update"),
        backup=raw.get("backup") or {},
        resources=raw.get("resources") or {},
        runtime=raw.get("runtime") or {},
        release=raw.get("release") or {},
        indexing=raw.get("indexing") or {},
        analytics=raw.get("analytics") or {},
        promotion=raw.get("promotion") or {},
        status=raw.get("status", "planned"),
    )


#: Из чего именно исключается сайт. Названия здесь — не ярлыки: каждое читает
#: свой обработчик, и проверка `tests/unit/test_promotion_exclusion.py` падает,
#: если обработчик перестал его читать.
ОБЛАСТИ_ПРОДВИЖЕНИЯ = (
    "editorial_queue",        # общая редакционная очередь
    "seo_queue",              # общая SEO-очередь
    "description_generation",  # генерация описаний
    "comment_generation",     # генерация комментариев
    "periodic_seo_edits",     # периодические автоматические SEO-правки
    "promotion_blocks",       # блоки продвижения на странице
    "cross_site_links",       # межсайтовая перелинковка
    "traffic_plan",           # план выхода на целевой трафик
)


def исключён_из_продвижения(cell: Cell, область: str | None = None) -> bool:
    """Исключён ли сайт из общего продвижения (целиком или в одной области).

    Отсутствие блока — «не исключён»: действующие сайты поля не имеют, и
    появление поля их поведение не меняет. Если область названа, но в `scopes`
    её нет, ответ — «не исключён в этой области»: исключение, записанное
    наполовину, не должно читаться как полное.
    """
    блок = cell.promotion or {}
    if not блок.get("excluded"):
        return False
    if область is None:
        return True
    области = блок.get("scopes") or ()
    return область in области


def исключённые_домены(path: Path | None = None,
                       область: str | None = None) -> frozenset[str]:
    """Домены (и псевдонимы) всех исключённых ячеек — одним множеством.

    Обработчикам нужен именно такой ответ: не «список сайтов продвижения», а
    «кого в него не брать». Разница важна, потому что общий прогон строит свой
    список сам, из реестра, и запрет должен быть проверкой на его пути, а не
    отсутствием имени в чьём-то перечне.
    """
    итог: set[str] = set()
    for cell in all_cells(path):
        if исключён_из_продвижения(cell, область):
            итог.update(d.lower() for d in cell.domains)
    return frozenset(итог)


def без_аналитики_по_решению(запись: dict[str, Any]) -> str:
    """Причина, по которой домену не нужны ни счётчик, ни проект позиций.

    Отвечает на вопрос покрытия: общие проверки требуют, чтобы КАЖДАЯ ячейка
    значилась в реестре аналитики и в манифесте Topvisor, потому что «нет
    записи» неотличимо от «всё сделано» — так однажды и пропали zonafilm.space
    и zonafilm.cc. Освобождение от этого требования даётся только за
    ПОЛОЖИТЕЛЬНУЮ и составную запись:

      * сайт исключён владельцем из общего продвижения (`promotion.excluded`);
      * счётчика у него нет (`analytics.metrika_counter_id` — null);
      * в паспорте СКАЗАНО, что аналитика не ставится.

    Как только счётчик появится, освобождение само перестанет действовать и
    запись в реестре аналитики снова станет обязательной. Домен, забытый без
    всякой записи, не освобождается ничем.

    Принимает сырую запись реестра, а не `Cell`: обе проверки покрытия читают
    JSON напрямую, и правило должно быть одно для них обеих — два написания
    разошлись бы на первой же правке.
    """
    аналитика = запись.get("analytics") or {}
    if not (запись.get("promotion") or {}).get("excluded"):
        return ""
    if аналитика.get("metrika_counter_id") is not None:
        return ""
    примечание = str(аналитика.get("note") or "")
    return примечание if "не устанавливается" in примечание.lower() else ""


def объявить_исключение(site_id_или_домен: str, *, excluded: bool,
                        reason: str, authority: str,
                        scopes: tuple[str, ...] = ОБЛАСТИ_ПРОДВИЖЕНИЯ,
                        keeps: tuple[str, ...] = (),
                        path: Path | None = None) -> Cell:
    """Записать исключение в паспорт ячейки.

    Причина и основание обязательны: исключение без них через месяц
    неотличимо от случайной правки, а снять его будет некому и незачем.
    Неизвестная область — отказ, а не молчаливое добавление: обработчика у
    придуманного имени нет, и запись обещала бы запрет, которого никто не
    исполняет.
    """
    reason = (reason or "").strip()
    authority = (authority or "").strip()
    if not reason or not authority:
        raise RegistryError(
            "BLOCKED_INPUT: исключению из продвижения нужны и reason, и authority")
    чужие = [s for s in scopes if s not in ОБЛАСТИ_ПРОДВИЖЕНИЯ]
    if чужие:
        raise RegistryError(
            f"неизвестные области продвижения {чужие}; известны: "
            f"{list(ОБЛАСТИ_ПРОДВИЖЕНИЯ)}")
    from dataclasses import replace as _replace

    было = resolve(site_id_или_домен, path)
    блок: dict[str, Any] = {
        "excluded": bool(excluded),
        "scopes": list(scopes),
        "keeps": list(keeps),
        "reason": reason,
        "authority": authority,
        "recorded_at": utc_now(),
    }
    return register(_replace(было, promotion=блок), path=path, replace=True)


def load(path: Path | None = None) -> dict[str, Any]:
    target = path or registry_path()
    return ledger.read(target, default={"schema_version": SCHEMA_VERSION, "cells": []})


def all_cells(path: Path | None = None) -> tuple[Cell, ...]:
    return tuple(_cell(raw) for raw in load(path).get("cells", []))


def resolve(query: str, path: Path | None = None) -> Cell:
    """Ячейка по домену или site_id. Только точное совпадение.

    Отдельно ловится случай, когда запрос похож на существующую запись: сказать
    «не найдено» и промолчать о похожем — значит заставить человека угадывать,
    а подставить похожее — значит выполнить задачу не на том сайте.
    """
    if not query or not query.strip():
        raise RegistryError("пустой запрос к реестру ячеек")
    needle = query.strip().lower()
    cells = all_cells(path)
    matches = [c for c in cells
               if c.site_id.lower() == needle or needle in {d.lower() for d in c.domains}]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise AmbiguousCell(
            f"под «{query}» подходит несколько ячеек: "
            f"{sorted(c.site_id for c in matches)}; уточните site_id"
        )
    similar = sorted(
        c.site_id for c in cells
        if needle in c.site_id.lower() or any(needle in d.lower() for d in c.domains)
    )
    hint = f"; похожие записи: {similar} — выбирать за вас реестр не будет" if similar else ""
    raise UnknownCell(f"в реестре ячеек нет записи «{query}»{hint}")


def check_publisher_id(value: str) -> str:
    """Отозванный идентификатор издателя не проходит дальше этой функции."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise RegistryError("publisher_id пуст: подставлять значение по умолчанию нельзя")
    if cleaned in RETIRED_PUBLISHER_IDS:
        raise RetiredPublisherId(
            f"publisher_id {cleaned} отозван поставщиком "
            f"(отозваны: {sorted(RETIRED_PUBLISHER_IDS)}); плеер с ним не заработает"
        )
    return cleaned


def register(cell: Cell, *, path: Path | None = None, replace: bool = False) -> Cell:
    """Записать паспорт ячейки.

    Домен принадлежит ровно одной ячейке: это то самое «один домен — один сайт»,
    и проверяется оно здесь, а не в обещании.
    """
    if not SITE_ID_RE.match(cell.site_id):
        raise RegistryError(f"недопустимый site_id: {cell.site_id!r}")
    for domain in cell.domains:
        if not DOMAIN_RE.match(domain):
            raise RegistryError(f"{cell.site_id}: недопустимый домен {domain!r}")
    publisher_id = (cell.publisher or {}).get("publisher_id")
    if publisher_id:
        check_publisher_id(str(publisher_id))

    target = path or registry_path()

    def change(data: dict[str, Any]) -> dict[str, Any]:
        cells = data.setdefault("cells", [])
        data.setdefault("schema_version", SCHEMA_VERSION)
        existing = [i for i, raw in enumerate(cells) if raw["site_id"] == cell.site_id]
        mine = {d.lower() for d in cell.domains}
        for i, raw in enumerate(cells):
            if i in existing:
                continue
            theirs = {raw["domain"].lower(), *(d.lower() for d in raw.get("aliases") or ())}
            clash = mine & theirs
            if clash:
                raise RegistryError(
                    f"домен(ы) {sorted(clash)} уже принадлежат ячейке {raw['site_id']}; "
                    "один домен — один сайт"
                )
        if existing:
            if not replace:
                raise RegistryError(
                    f"ячейка {cell.site_id} уже зарегистрирована; "
                    "для изменения используйте update() или replace=True"
                )
            cells[existing[0]] = cell.to_dict()
        else:
            cells.append(cell.to_dict())
        cells.sort(key=lambda raw: raw["site_id"])
        return data

    ledger.mutate(target, change, default={"schema_version": SCHEMA_VERSION, "cells": []})
    return cell


def update(site_id: str, changes: dict[str, Any], *, path: Path | None = None) -> Cell:
    """Точечно обновить поля паспорта: релиз, ревизию содержимого, бэкап."""
    target = path or registry_path()
    result: dict[str, Any] = {}
    # `runtime` — размещение витрины: учётная запись, юнит, порт, каталоги.
    # Правка через этот путь, а не руками, потому что размещение единственное,
    # чему доверяет привилегированный исполнитель: пути он берёт отсюда и
    # никогда из заявки. Ручная правка JSON обходит и проверку формы, и отметку
    # времени, по которой потом видно, когда витрина стала управляемой ячейкой.
    # `release` держит удержание выпуска и его причину. До сих пор оно только
    # читалось триггером, а ставилось правкой JSON руками — то есть в обход
    # проверок этого модуля. Причина удержания устаревает быстрее всего
    # остального в паспорте: она называет чужую ветку, чужой релиз или чужой
    # дефект, и неверная причина хуже отсутствующей — по ней решают, можно ли
    # уже выкладывать.
    allowed = {"status", "deployed", "content_revision", "last_update", "backup",
               "resources", "pins", "deploy_target", "repo", "data", "publisher",
               "template", "aliases", "release", "runtime"}
    unknown = set(changes) - allowed
    if unknown:
        raise RegistryError(f"эти поля паспорта не обновляются точечно: {sorted(unknown)}")
    if "publisher" in changes:
        pid = (changes["publisher"] or {}).get("publisher_id")
        if pid:
            check_publisher_id(str(pid))

    def change(data: dict[str, Any]) -> dict[str, Any]:
        for raw in data.get("cells", []):
            if raw["site_id"] != site_id:
                continue
            raw.update(changes)
            raw["last_update"] = changes.get("last_update") or utc_now()
            result["cell"] = raw
            return data
        raise UnknownCell(f"в реестре ячеек нет записи {site_id}")

    ledger.mutate(target, change, default={"schema_version": SCHEMA_VERSION, "cells": []})
    return _cell(result["cell"])


def route(query: str, path: Path | None = None) -> dict[str, Any]:
    """Маршрут задачи: куда её нести. Ровно то, что нужно исполнителю."""
    cell = resolve(query, path)
    return {
        "site_id": cell.site_id,
        "domain": cell.domain,
        "repo": cell.repo.get("path") or cell.repo.get("remote"),
        "template_id": cell.template.get("template_id"),
        "pins": cell.pins,
        "deploy_target": cell.deploy_target.get("ref"),
        "server": cell.deploy_target.get("server"),
        "deployed_digest": cell.deployed.get("release_digest"),
        "content_revision": cell.content_revision,
    }


def consistency_report(path: Path | None = None) -> list[str]:
    """Расхождения между реестром ячеек и профилями сайтов.

    Реестр не владеет идентичностью — он на неё ссылается. Если ссылка
    разъехалась с профилем, это должно быть видно отсюда, а не с домена.
    """
    problems: list[str] = []
    known: dict[str, set[str]] = {}

    # Профиль движка витрин есть не у каждого сайта: направления на DLE
    # описываются пакетом, а не профилем. Поэтому источников два, и отсутствие
    # одного из них расхождением не является — расхождением является
    # противоречие между ними.
    profiles_dir = PATHS.root / "config" / "site-profiles"
    for profile in sorted(profiles_dir.glob("*.json")):
        data = json.loads(profile.read_text(encoding="utf-8"))
        known.setdefault(data["site_id"], set()).update(data.get("domains") or ())

    for package in sorted(PATHS.sites.glob("*/package.yaml")):
        try:
            import yaml

            data = yaml.safe_load(package.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001 — нечитаемый пакет разбирает валидатор пакета
            continue
        site_id = data.get("site_id")
        domain = data.get("domain")
        if site_id and domain:
            known.setdefault(site_id, set()).add(domain)

    # Третий источник — пакет самой ячейки. Переносимая ячейка живёт в
    # собственном репозитории и несёт идентичность там (`config/site.json`),
    # а не в `config/site-profiles` и не в `sites/`. Без него сверка шумела на
    # две трети записей одной и той же неверной фразой — 23 замечания из 33
    # ячеек, измерено 2026-10-14, — и в этом шуме тонуло настоящее
    # расхождение.
    for cell in all_cells(path):
        try:
            пакет = cell.repo_path / "config" / "site.json"
        except RegistryError:
            # Путь уводит за пределы корня репозиториев: читать оттуда нельзя,
            # и послабления тут быть не может. Ячейка останется неизвестной.
            continue
        if not пакет.is_file():
            continue
        try:
            данные = json.loads(пакет.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        site_id = данные.get("site_id")
        domain = данные.get("domain")
        if site_id and domain:
            known.setdefault(site_id, set()).add(domain)

    # Обратный указатель: он отличает «фабрика не знает такой витрины» от
    # «знает тот же домен под другим именем». Второе — расхождение
    # идентичности, и называть его надо прямо.
    по_домену: dict[str, set[str]] = {}
    for site_id, домены in known.items():
        for домен in домены:
            по_домену.setdefault(домен, set()).add(site_id)

    for cell in all_cells(path):
        declared = known.get(cell.site_id)
        if not declared:
            другие = sorted(по_домену.get(cell.domain, set()))
            if другие:
                problems.append(
                    f"{cell.site_id}: источник идентичности знает домен "
                    f"{cell.domain} под именем {другие} — одна витрина под двумя "
                    "именами, и выкладка пойдёт не тем site_id"
                )
            else:
                problems.append(
                    f"{cell.site_id}: ни профиля, ни пакета сайта, ни пакета самой "
                    "ячейки — реестр ссылается на сайт, которого фабрика не знает"
                )
            continue
        if cell.domain not in declared:
            problems.append(
                f"{cell.site_id}: реестр называет домен {cell.domain}, "
                f"источники идентичности — {sorted(declared)}"
            )
    return problems


class OwnRepositoryMissing(RegistryError):
    """У сайта нет собственного репозитория, а выкладка требует именно его."""


def require_own_repo(cell: Cell) -> str:
    """Убедиться, что сайт публикуется из своего репозитория, а не из монорепо.

    Существует ради одного сценария: создание репозитория сорвалось (не хватило
    прав, кончилась квота, оборвалась сеть), а конвейер пошёл дальше и выложил
    сайт из монорепозитория. Снаружи это неотличимо от нормального выпуска —
    ровно до первой правки, когда выясняется, что менять нечего и откатывать
    некуда.

    Поэтому отсутствие `repo.remote` — отказ, а не предупреждение. Локальный
    путь без remote тоже не годится: он не переживёт машину, на которой лежит.
    """
    remote = (cell.repo or {}).get("remote")
    if not remote or not str(remote).strip():
        raise OwnRepositoryMissing(
            f"{cell.site_id}: не записан собственный репозиторий (repo.remote пуст). "
            "Выкладка из монорепозитория запрещена: у сайта не будет ни своей "
            "истории, ни отката. Сначала создайте репозиторий сайта."
        )
    # Монорепозиторий фабрики опознаётся по имени и не принимается никогда.
    низкий = str(remote).lower()
    for признак in ("/test.git", "/test", "site-factory"):
        if низкий.rstrip("/").endswith(признак):
            raise OwnRepositoryMissing(
                f"{cell.site_id}: repo.remote указывает на монорепозиторий "
                f"({remote}); у сайта обязан быть собственный проект"
            )
    return str(remote)


class SiteAlreadyExtracted(RegistryError):
    """Сайт выделен в собственный репозиторий: публиковать его отсюда нельзя."""


def extracted_sites(path: Path | None = None) -> dict[str, str]:
    """Сайты, у которых уже есть собственный репозиторий: site_id -> remote.

    Единственный источник истины для вопроса «кому принадлежит публикация
    этого домена». Раньше ответ приходилось собирать по фактам — есть ли
    каталог, отвечает ли служба, лежит ли где-то артефакт, — и каждый такой
    признак врал хотя бы в одном состоянии.
    """
    выделенные = {}
    for cell in all_cells(path):
        remote = (cell.repo or {}).get("remote")
        if not remote or not str(remote).strip():
            continue
        try:
            выделенные[cell.site_id] = require_own_repo(cell)
        except OwnRepositoryMissing:
            # remote есть, но это монорепо — сайт не выделен.
            continue
    return выделенные


def require_not_extracted(site_id: str, *, action: str,
                          path: Path | None = None) -> None:
    """Отказать старому пути публикации ДО первой мутации.

    Проверка стоит именно перед действием, а не после: «выложили, потом
    заметили» для живого домена означает, что чужой выпуск уже отдан
    посетителям, а откатывать его нужно из другого репозитория.
    """
    выделенные = extracted_sites(path)
    remote = выделенные.get(site_id)
    if remote is None:
        return
    raise SiteAlreadyExtracted(
        f"{site_id}: {action} через общий путь запрещена — сайт выделен в "
        f"собственный репозиторий {remote}. Правьте и выкладывайте его там; "
        "два источника изменений для одного домена дают гонку, а не запас."
    )
