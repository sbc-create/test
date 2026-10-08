"""Где витрина живёт на самом деле — один ответ для всех, кто её трогает.

Зачем
-----

Производители содержимого знали про службы по собственным спискам: таблица в
`content-pipeline/refresh.py`, массив `SITES` в `nova-daily-refresh.sh`. После
переноса сайта в свою ячейку эти списки продолжали звать прежний unit по имени
и писать снимок каталога по прежнему пути. Снаружи это выглядело как сайт,
который «перестал пополняться», и никакой ошибки нигде не появлялось.

Здесь один ответ на три вопроса, которые производитель обязан задать перед
доставкой:

1. **куда** класть снимок — каталог данных ячейки или прежний общий путь;
2. **кого** уведомлять — и нужно ли уведомлять вообще;
3. **чем** уведомлять — перезапуском службы или ничем.

Третий вопрос не косметический. Витрина Zona перечитывает снимок сама, по
mtime, на ближайшем запросе: перезапуск ей не нужен, а стоит он минут — она
читает каталог 16.7 МБ и detail 78.3 МБ. Производитель, ходящий раз в пять
минут, превращал бы это в постоянную недоступность. Остальные семейства такого
перечитывания не умеют, и для них перезапуск обязателен. Разницу нельзя
угадывать — она объявлена в реестре полем `runtime.reload`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory.cell import registry

#: Режим, который производитель обязан принять, если сайт про себя молчит.
#: Осторожный по построению: лишний перезапуск заметен и дорог, пропущенный —
#: незаметен и оставляет витрину на вчерашнем каталоге.
РЕЖИМ_ПО_УМОЛЧАНИЮ = "restart"


class RuntimeUnknown(Exception):
    """Про размещение витрины в реестре ничего не записано."""


@dataclass(frozen=True)
class Размещение:
    """Ответ производителю. Ровно то, что ему нужно, и ничего больше."""

    site_id: str
    domain: str
    #: Каталог, куда класть снимки. None — писать по прежнему общему пути.
    data_dir: str | None
    #: Служба, которую можно уведомлять. None — уведомлять некого.
    unit: str | None
    #: Служба до переноса. Её звать нельзя: она закрыта от ручного запуска.
    previous_unit: str | None
    port: int | None
    account: str | None
    reload: str
    managed_by: str

    @property
    def нужен_перезапуск(self) -> bool:
        """Перезапуск нужен только там, где витрина не перечитывает сама."""
        return self.reload != "mtime"

    def as_dict(self) -> dict[str, Any]:
        return {"site_id": self.site_id, "domain": self.domain,
                "data_dir": self.data_dir, "unit": self.unit,
                "previous_unit": self.previous_unit, "port": self.port,
                "account": self.account,
                "reload": self.reload, "managed_by": self.managed_by,
                "restart_required": self.нужен_перезапуск}


def размещение(site_id: str, *, path: Path | None = None) -> Размещение:
    """Размещение зарегистрированной витрины."""
    cell = registry.resolve(site_id, path) if path else registry.resolve(site_id)
    блок = cell.runtime or {}
    if not блок:
        raise RuntimeUnknown(
            f"{site_id}: в реестре нет блока runtime. Производитель не должен "
            "догадываться, куда доставлять и кого перезапускать: отсутствие "
            "записи — повод остановиться, а не выбрать прежний путь по привычке")
    return Размещение(
        site_id=cell.site_id, domain=cell.domain,
        data_dir=блок.get("data_dir"), unit=блок.get("unit"),
        previous_unit=блок.get("previous_unit"), port=блок.get("port"),
        account=блок.get("account"),
        reload=блок.get("reload") or РЕЖИМ_ПО_УМОЛЧАНИЮ,
        managed_by=блок.get("managed_by") or "monolith",
    )


def все_размещения(path: Path | None = None) -> dict[str, Размещение]:
    итог = {}
    for cell in registry.all_cells(path):
        try:
            итог[cell.site_id] = размещение(cell.site_id, path=path)
        except (RuntimeUnknown, registry.RegistryError):
            continue
    return итог


def для_производителя(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Плоский словарь для тех, кто не может импортировать фабрику.

    Производители — отдельные процессы с собственными зависимостями; тянуть в
    них весь пакет ради трёх полей неправильно. Они читают этот же реестр
    файлом, а формат ответа задан здесь, чтобы он был один.
    """
    return {s: р.as_dict() for s, р in все_размещения(path).items()}


def прочитать_реестр_файлом(путь: str | Path) -> dict[str, dict[str, Any]]:
    """Тот же ответ, но без импорта фабрики — для сторонних процессов.

    Намеренно повторяет минимум логики и ничего не проверяет сверх формата:
    производитель, не сумевший прочитать реестр, обязан остановиться, а не
    чинить его на ходу.
    """
    данные = json.loads(Path(путь).read_text(encoding="utf-8"))
    итог: dict[str, dict[str, Any]] = {}
    for c in данные.get("cells") or []:
        блок = c.get("runtime") or {}
        if not блок:
            continue
        режим = блок.get("reload") or РЕЖИМ_ПО_УМОЛЧАНИЮ
        итог[c["site_id"]] = {
            "site_id": c["site_id"], "domain": c.get("domain"),
            "data_dir": блок.get("data_dir"), "unit": блок.get("unit"),
            "previous_unit": блок.get("previous_unit"), "port": блок.get("port"),
            "account": блок.get("account"), "reload": режим, "managed_by": блок.get("managed_by") or "monolith",
            "restart_required": режим != "mtime",
        }
    return итог


#: Где systemd держит ссылки включённых юнитов. Факт включения читается здесь,
#: а не у `systemctl`: операция обязана работать и там, где обращаться к шине
#: нечем, а ссылка в каталоге — то же самое утверждение в файловом виде.
ВКЛЮЧЁННЫЕ = Path("/etc/systemd/system/multi-user.target.wants")
ЮНИТЫ = Path("/etc/systemd/system")


def каталог_данных_юнита(unit: str, *, корень: Path | None = None) -> str | None:
    """`--data-dir` из ExecStart юнита. None — в команде его нет.

    Читается именно ExecStart, потому что это единственное место, где путь
    назван той строкой, которую systemd передаёт процессу. Переменные
    окружения витрины сюда не годятся: у zona-02 рядом лежит `ZONA02_DATA`
    выключенного юнита предыдущего размещения, и поверить ему значило бы
    принять намерение за факт.
    """
    файл = (корень or ЮНИТЫ) / unit
    if not файл.is_file():
        return None
    for строка in файл.read_text(encoding="utf-8", errors="replace").splitlines():
        if not строка.strip().startswith("ExecStart"):
            continue
        части = строка.split()
        for н, кусок in enumerate(части):
            if кусок == "--data-dir" and н + 1 < len(части):
                return части[н + 1]
            if кусок.startswith("--data-dir="):
                return кусок.split("=", 1)[1]
    return None


def завершить_переезд(site_id: str, *, dry_run: bool = True,
                      path: Path | None = None,
                      корень_юнитов: Path | None = None,
                      корень_включённых: Path | None = None) -> dict[str, Any]:
    """Перенести `data_dir_after_relocation` в `data_dir` — ПО ИЗМЕРЕНИЮ.

    Зачем отдельная операция. Переезд витрины в свою ячейку состоит из двух
    шагов: включить новый юнит и сказать об этом реестру. Второй шаг
    пропускается незаметно, и тогда реестр описывает НАМЕРЕНИЕ: производитель
    кладёт снимок по `data_dir`, а витрина читает другой каталог. Снаружи это
    выглядит как сайт, который перестал пополняться, и ошибки нет нигде.

    Измерено 2026-10-08 на zona-02 (zonafilm.cc): издатель кладёт свежий
    каталог в `/srv/lords/.frontend/sites/zona-02/data` (60 699 позиций,
    04:01), а включённый юнит `nova-zonafilm-cc.service` запускает витрину с
    `--data-dir /srv/zonafilm-cc/data`, где лежал снимок от 2026-09-28 на
    53 908 позиций. Разница — 6 791 произведение, и `sitemap-1.xml` показывал
    самый свежий `lastmod` 2026-09-27 при 2026-10-08 у соседей.

    Почему именно по измерению. Запись в реестр здесь делается ТОЛЬКО если
    включённый юнит действительно запускает витрину с объявленным каталогом:
    реестр описывает факт, а не намерение (`docs/PORTABLE_SITE_CELL.md`).
    Иначе операция отказывает и называет оба пути — тот, что в юните, и тот,
    что собирались записать. Иначе эта операция стала бы вторым способом
    соврать о размещении, только автоматическим.
    """
    cell = registry.resolve(site_id, path)
    # Блок размещения берётся СЫРЫМ из реестра, а не из разобранной записи:
    # `Размещение` отдаёт только нужные производителю поля, а перенести надо
    # весь блок целиком, не потеряв ни заметок, ни служебных отметок.
    сырой = next((c for c in registry.load(path).get("cells") or []
                  if c.get("site_id") == cell.site_id), {})
    блок = dict(сырой.get("runtime") or {})
    if not блок:
        raise RuntimeUnknown(
            f"{cell.site_id}: размещение в реестре не объявлено — переносить нечего")

    цель = (блок.get("data_dir_after_relocation") or "").strip()
    текущий = (блок.get("data_dir") or "").strip()
    unit = (блок.get("unit") or "").strip()
    итог: dict[str, Any] = {
        "operation": "relocate_data", "site_id": cell.site_id,
        "domain": cell.domain, "unit": unit,
        "data_dir_now": текущий or None, "data_dir_target": цель or None,
        "dry_run": bool(dry_run),
    }
    if not цель:
        итог.update(status="nothing-to-do",
                    reason="в размещении нет data_dir_after_relocation: "
                           "переезд не объявлен")
        return итог
    if цель == текущий:
        итог.update(status="nothing-to-do",
                    reason="data_dir уже равен объявленному после переезда")
        return итог
    if not unit:
        итог.update(status="refused", reason="в размещении не назван юнит: "
                                             "измерять нечего")
        return итог

    ссылка = (корень_включённых or ВКЛЮЧЁННЫЕ) / unit
    итог["unit_enabled"] = ссылка.exists()
    измерен = каталог_данных_юнита(unit, корень=корень_юнитов)
    итог["data_dir_in_unit"] = измерен
    if not итог["unit_enabled"]:
        итог.update(status="refused",
                    reason=f"юнит {unit} не включён ({ссылка}): переезд не "
                           "состоялся, и записывать его в реестр нельзя")
        return итог
    if измерен is None:
        итог.update(status="refused",
                    reason=f"в ExecStart юнита {unit} нет --data-dir: "
                           "каталог данных витрины не назван командой запуска")
        return итог
    if измерен.rstrip("/") != цель.rstrip("/"):
        итог.update(status="refused",
                    reason=f"юнит {unit} запускает витрину с --data-dir "
                           f"{измерен}, а в реестр собирались записать {цель}: "
                           "реестр описывает факт, а не намерение")
        return итог

    итог["measured"] = (f"ExecStart юнита {unit} передаёт --data-dir {измерен}; "
                        f"юнит включён ссылкой {ссылка}")
    if dry_run:
        итог.update(status="dry-run", reason="записал бы data_dir из измерения")
        return итог

    новый = dict(блок)
    новый["data_dir"] = цель
    новый["data_dir_before_relocation"] = текущий or None
    новый.pop("data_dir_after_relocation", None)
    новый["data_dir_note"] = (
        "Каталог назван ПО ИЗМЕРЕНИЮ включённого юнита: " + итог["measured"]
        + ". Перенос выполнен операцией factory cell relocate-data.")
    registry.update(cell.site_id, {"runtime": новый}, path=path)
    итог.update(status="relocated",
                reason="data_dir приведён к тому, что читает витрина")
    return итог

