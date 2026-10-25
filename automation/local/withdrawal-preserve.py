#!/usr/bin/env python3
"""Сохранение домена, выведенного из работы: что переносим и чем это доказано.

Повод. Распоряжение владельца 2026-10-25 выводит четыре домена из активной
работы и требует сохранить «код, настройки, данные каталога, опубликованные
тексты, черновики, источники, рецензии и соответствия старых URL», проверив
имеющуюся резервную копию. Измерено в тот же день: блок `backup` в паспортах
всех четырёх ячеек ПУСТ — резервной копии не записано ни у одной.

Что делает инструмент, по каждому домену:

* **копирует** малое и невосстановимое: хранилище накладок витрины
  (`drafts.json` — черновики, источники и рецензии; `published.json`;
  `title-overlays.json` — доставленные тексты; `history.jsonl` — журнал
  решений). Это десятки килобайт и единственный экземпляр;
* **описывает, но не копирует** данные каталога: `*-catalog.json` и
  `*-details.json` — от 60 до 155 МиБ на домен. Для них пишется отпечаток
  SHA-256, размер и время правки: копия на том же диске защищает слабо, а
  отпечаток позволяет доказать, что файл не изменился после вывода;
* **снимает состояние репозитория** витрины: HEAD, ветка, адрес и перечень
  НЕЗАКОММИЧЕННЫХ файлов. Незакоммиченная работа — главный способ потерять
  прогресс при остановке служб, и молчать о ней нельзя;
* **строит перечень адресов** из каталога (`items[].url`) — основу
  постраничных перенаправлений на домен замены. Соответствие строится ровно
  тогда, когда замена названа в паспорте (`withdrawal.replacement_domain`), и
  НЕ придумывается иначе.

Чего инструмент не делает: не останавливает службы, не удаляет данные и не
меняет паспорт. Он только читает и складывает доказательства.

    python3 automation/local/withdrawal-preserve.py --domain <домен> [--out <каталог>]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
#: Файлы накладок, которые существуют в одном экземпляре и копируются целиком.
НАКЛАДКИ = ("drafts.json", "published.json", "title-overlays.json",
            "delivered.json", "history.jsonl")


def отпечаток(п: pathlib.Path, блок: int = 1 << 20) -> str:
    """SHA-256 файла, либо причина, по которой отпечатка нет.

    Файл данных витрины может принадлежать root с режимом 0600 — измерено на
    `/srv/lordfilm47-space/data/lords-01-shelves-ledger.json`. Падать на этом
    нельзя: сохранение остальных файлов важнее, а «нет прав» — честный ответ,
    который должен попасть в свод, а не оборвать работу.
    """
    х = hashlib.sha256()
    try:
        with п.open("rb") as ф:
            while кусок := ф.read(блок):
                х.update(кусок)
    except OSError as ош:
        return f"НЕ ПРОЧИТАН: {type(ош).__name__} {ош.strerror or ''}".strip()
    return х.hexdigest()


def ячейка(домен: str) -> dict:
    """Запись паспорта по домену, из реестра ячеек."""
    д = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text(encoding="utf-8"))
    for з in д.get("cells") or []:
        if з.get("domain") == домен or домен in (з.get("aliases") or ()):
            return з
    return {}


def путь_репозитория(з: dict) -> pathlib.Path | None:
    п = str((з.get("repo") or {}).get("path") or "")
    if not п:
        return None
    путь = pathlib.Path(п)
    if путь.is_absolute():
        return путь
    for корень in (КОРЕНЬ, pathlib.Path("/home/claude/wt-portable-site-cell-01")):
        if (корень / путь).is_dir():
            return корень / путь
    return КОРЕНЬ / путь


def состояние_репозитория(путь: pathlib.Path | None) -> dict:
    """HEAD, ветка, адрес и НЕЗАКОММИЧЕННЫЕ файлы репозитория витрины."""
    if путь is None or not (путь / ".git").exists():
        return {"path": str(путь) if путь else None,
                "note": "репозитория нет на этом узле — сохранять нечего"}
    def г(*а: str) -> str:
        р = subprocess.run(["git", *а], cwd=str(путь), capture_output=True,
                           text=True, timeout=120)
        return р.stdout.strip() if р.returncode == 0 else ""
    грязные = [с for с in г("status", "--porcelain").splitlines() if с.strip()]
    return {"path": str(путь), "head": г("rev-parse", "HEAD"),
            "branch": г("rev-parse", "--abbrev-ref", "HEAD"),
            "remote": г("remote", "get-url", "origin"),
            "uncommitted": грязные,
            "note": ("незакоммиченных файлов нет" if not грязные else
                     f"НЕЗАКОММИЧЕНО файлов: {len(грязные)} — при остановке служб "
                     "этот прогресс теряется, если его не зафиксировать")}


#: Чем КАТАЛОГ отличается от ТЕКУЩЕГО СОСТОЯНИЯ, и почему это различение нужно.
#:
#: Измерено 25.10 на собственной ошибке: проверка сохранности пересчитала
#: отпечатки через полтора часа и объявила «данные разошлись, остановку не
#: выполнять» — разошлись девять файлов. Разбор показал, что каталог
#: (`*-catalog.json`, `*-details.json`) совпал у всех четырёх домéнов, а
#: менялись файлы, которые РАБОТАЮЩАЯ служба пишет на ходу: номера серий,
#: события и состояние эпизодов. Смешав их, проверка выдала живую работу за
#: порчу данных и предложила отменить остановку.
#:
#: Поэтому отпечаток каталога — доказательство сохранности, а отпечаток
#: состояния — лишь отметка времени: его окончательный снимок берётся ПОСЛЕ
#: остановки службы, иначе он устареет к моменту проверки.
ПРИЗНАКИ_КАТАЛОГА = ("-catalog.json", "-details.json", "-admission.json",
                     "editorial-overrides.json")


def вид_файла(имя: str) -> str:
    """«каталог» или «состояние» — по имени файла."""
    return "каталог" if any(имя.endswith(п) for п in ПРИЗНАКИ_КАТАЛОГА) else "состояние"


def данные_каталога(сид: str, каталоги: tuple[str, ...] = ()) -> list[dict]:
    """Описание файлов данных: отпечаток и размер, без копирования."""
    итог = []
    места = каталоги or (f"/srv/{сид}/data", f"/srv/{сид}-space/data")
    for место in места:
        к = pathlib.Path(место)
        if not к.is_dir():
            continue
        for ф in sorted(к.iterdir()):
            if not ф.is_file() or ф.name.startswith("."):
                continue
            итог.append({"path": str(ф), "bytes": ф.stat().st_size,
                         "kind": вид_файла(ф.name),
                         "sha256": отпечаток(ф),
                         "mtime": dt.datetime.fromtimestamp(
                             ф.stat().st_mtime, dt.timezone.utc).isoformat()})
    return итог


def адреса_каталога(путь: pathlib.Path) -> list[str]:
    """Адреса страниц из каталога витрины — основа перенаправлений."""
    try:
        д = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    итог = []
    for з in д.get("items") or []:
        а = str(з.get("url") or "").strip()
        if а:
            итог.append(а)
    return sorted(set(итог))


def сохранить(домен: str, куда: pathlib.Path) -> dict:
    з = ячейка(домен)
    сид = str(з.get("site_id") or "")
    цель = куда / домен
    цель.mkdir(parents=True, exist_ok=True)
    # 1. накладки — копией
    скопировано = []
    for хранилище in pathlib.Path("/srv/sites").glob(f"*/runtime/overlays/{домен}"):
        for имя in НАКЛАДКИ:
            ф = хранилище / имя
            if not ф.is_file():
                continue
            (цель / "overlays").mkdir(exist_ok=True)
            shutil.copy2(ф, цель / "overlays" / имя)
            скопировано.append({"path": str(ф), "bytes": ф.stat().st_size,
                                "sha256": отпечаток(ф)})
    # 2. данные каталога — описанием
    описано = данные_каталога(сид.replace("lords-01", "lordfilm47") if False else сид)
    if not описано:
        # Каталог данных витрины называется по домену, а не по site_id.
        имя_кат = домен.replace(".", "-")
        описано = данные_каталога(сид, (f"/srv/{имя_кат}/data",))
    # 3. репозиторий
    репо = состояние_репозитория(путь_репозитория(з))
    # 4. адреса
    каталоги = [pathlib.Path(о["path"]) for о in описано if "catalog.json" in о["path"]]
    адреса = адреса_каталога(каталоги[0]) if каталоги else []
    if адреса:
        (цель / "urls.txt").write_text("\n".join(адреса) + "\n", encoding="utf-8")
    замена = str((з.get("withdrawal") or {}).get("replacement_domain") or "")
    свод = {
        "domain": домен, "site_id": сид,
        "saved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "withdrawal": з.get("withdrawal") or {},
        "overlays_copied": скопировано,
        "catalog_data": описано,
        "repo": репо,
        "urls": {"count": len(адреса), "file": "urls.txt" if адреса else None,
                 "replacement_domain": замена or None,
                 "note": ("постраничное соответствие строится на домен замены"
                          if замена else
                          "замена не названа: соответствие адресов не строится")},
    }
    (цель / "manifest.json").write_text(
        json.dumps(свод, ensure_ascii=False, indent=1), encoding="utf-8")
    return свод


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--domain", action="append", required=True)
    р.add_argument("--out", type=pathlib.Path,
                   default=КОРЕНЬ / "artifacts" / "withdrawal-20261025")
    а = р.parse_args(аргв)
    for домен in а.domain:
        с = сохранить(домен, а.out)
        данных = sum(о["bytes"] for о in с["catalog_data"])
        без_отпечатка = [о for о in с["catalog_data"]
                         if str(о["sha256"]).startswith("НЕ ПРОЧИТАН")]
        print(f"{домен:22} накладок {len(с['overlays_copied'])},"
              f" файлов данных {len(с['catalog_data'])} ({данных/1048576:.1f} МиБ, описаны),"
              f" адресов {с['urls']['count']}"
              + (f", БЕЗ отпечатка {len(без_отпечатка)}" if без_отпечатка else ""))
        for о in без_отпечатка:
            print(f"{'':22} не прочитан: {о['path']} — {о['sha256']}")
        р_ = с["repo"]
        print(f"{'':22} репозиторий: {р_.get('branch') or '—'} {str(р_.get('head'))[:12]}"
              f" | {р_.get('note')}")
    print(f"\nсохранено в {а.out}")
    print("данные каталога НЕ копировались: для них записаны отпечатки SHA-256")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
