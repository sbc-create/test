#!/usr/bin/env python3
"""Релиз витрины zona-02 (zonafilm.cc) из закреплённого шаблона Zona.

Раскладка повторяет ту, что уже держит шесть витрин, и ничего не изобретает:
неизменяемый каталог `releases/<id>`, ссылка `sites/<витрина>/current`, свой
манифест, свой каталог, свой порт. Отличие от соседей ровно одно — всё это
принадлежит zona-02 и никому больше.

Что делает
----------

1. сверяет исходный релиз с закреплённым sha256 и отказывается при расхождении;
2. считает идентификатор релиза от содержимого И домена;
3. раскладывает неизменяемую копию в `releases/<id>`;
4. пишет `template-manifest-zona-02.json`;
5. переставляет `sites/zona-02/current` атомарно, сохранив предыдущую цель;
6. добавляет ключ `zona-02` в реестр диспетчера — и ничего кроме него.

Чего не делает: не ставит юнит, не пишет vhost, не трогает DNS, не выпускает
сертификаты и не перезапускает ни одну чужую службу. Всё это требует root и
остаётся решением владельца.

Идемпотентность: одинаковый вход даёт тот же идентификатор релиза, повторный
запуск не плодит каталоги и не меняет ссылку.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

ФРОНТ = Path("/srv/lords/.frontend")
РЕЛИЗЫ = ФРОНТ / "releases"
ВИТРИНЫ = ФРОНТ / "sites"
РЕЕСТР_ДИСПЕТЧЕРА = ФРОНТ / "lords-runtime-registry.json"

SITE_ID = "zona-02"
FAMILY = "zona"
DOMAIN = "zonafilm.cc"
PORT = 9123
UNIT = "nova-zona-02.service"

#: Закреплённый шаблон. Значения взяты из RELEASE.json назначенного релиза
#: zona-01 и подтверждены живой выдачей — см.
#: artifacts/evidence/release-zonafilm-cc-full-cycle-01/02-start-point/template-pin.md
ИСТОЧНИК = РЕЛИЗЫ / "zona-slider-2650fad6"
ЗАКРЕПЛЁННЫЙ_SHA256 = "7ccf094a1d7f2b5e648a38f51f6a63de9627576637d96f6c966fe1759ad8fa1e"
ИСХОДНЫЙ_КОММИТ = "5863d296264867f85138bd771f1b90a86ac9c599"

#: Версия оформления, которую витрина объявляет.
#:
#: Не 1.3.0. Манифест zona-01 объявляет 1.3.0, но артефакт `7ccf094a…`
#: исполняет только `ОФОРМЛЕНИЕ_ВЕРСИИ = {1.1.0, 1.2.0, 1.2.1}`, и значение
#: вне набора не вызывает отказа: `ОФОРМЛЕНИЕ_НОВОЕ` просто становится False, а
#: витрина уходит на дореформенные ветки. Маршруты 1.1+ (`/title/`,
#: `/collection/`, `/genre/`, `/country/`, `/year/`) при этом обслуживаются
#: `старое()` — отдачей из ранее отрисованного статического релиза.
#:
#: У zona-01 такой релиз есть, и деградация не видна. У новой витрины его нет,
#: и первый же прогон приёмки дал 404 на всех сорока проверенных карточках.
#:
#: 1.2.0 — единственная версия, при которой это семейство исполняет
#: переработанное оформление: `ПЕРЕРАБОТАНО_С["zona"] = {1.2.0}`. Значение не
#: подобрано на глаз: `проверить_версию_оформления()` ниже читает оба набора из
#: самого артефакта и отказывается выкладывать несовпадение.
ВЕРСИЯ_ОФОРМЛЕНИЯ = "1.2.0"
ПРОФИЛЬ = "zona-general"
РАНТАЙМ = "lords-frontend.py"

_НАБОР_ВЕРСИЙ = re.compile(r"^ОФОРМЛЕНИЕ_ВЕРСИИ\s*=\s*\{(?P<body>[^}]*)\}", re.M)
_КОНСТАНТА_ВЕРСИИ = re.compile(
    r"^(?P<name>ОФОРМЛЕНИЕ_1_[0-9_]+)\s*=\s*\"(?P<value>[^\"]+)\"", re.M)
_ПЕРЕРАБОТАНО = re.compile(r"^ПЕРЕРАБОТАНО_С\s*=\s*\{(?P<body>.*?)^\}", re.M | re.S)


class ОшибкаРелиза(RuntimeError):
    pass


def sha256(путь: Path) -> str:
    h = hashlib.sha256()
    with путь.open("rb") as f:
        for кусок in iter(lambda: f.read(1 << 20), b""):
            h.update(кусок)
    return h.hexdigest()


def идентификатор(файлы: dict[str, Path], домен: str) -> str:
    """От содержимого И домена.

    Домен входит в отпечаток не для красоты: манифест витрины содержит её
    домен, и два релиза одного кода для разных доменов — это разные релизы.
    Считать им один идентификатор значит объявить одинаковым то, что
    различается.
    """
    h = hashlib.sha256()
    h.update(домен.encode("utf-8") + b"\0")
    for имя in sorted(файлы):
        h.update(имя.encode("utf-8") + b"\0")
        h.update(bytes.fromhex(sha256(файлы[имя])))
    return f"{SITE_ID}-{h.hexdigest()[:12]}"


def собрать_файлы() -> dict[str, Path]:
    if not ИСТОЧНИК.is_dir():
        raise ОшибкаРелиза(f"нет исходного релиза {ИСТОЧНИК}")
    рантайм = ИСТОЧНИК / РАНТАЙМ
    фактический = sha256(рантайм)
    if фактический != ЗАКРЕПЛЁННЫЙ_SHA256:
        raise ОшибкаРелиза(
            f"шаблон не тот, что закреплён: {рантайм} имеет sha256 {фактический}, "
            f"закреплён {ЗАКРЕПЛЁННЫЙ_SHA256}. Выкладка прекращена — собрать сайт "
            "на неизвестном коде хуже, чем не собрать его вовсе"
        )
    файлы = {p.name: p for p in sorted(ИСТОЧНИК.iterdir())
             if p.is_file() and p.suffix == ".py"}
    if РАНТАЙМ not in файлы:
        raise ОшибкаРелиза(f"в исходном релизе нет {РАНТАЙМ}")
    return файлы


def проверить_версию_оформления(рантайм: Path) -> dict:
    """Объявляемая версия обязана исполняться этим артефактом.

    Артефакт не отказывается от неизвестной версии — он молча уходит на
    дореформенные ветки. Значит отказаться должна выкладка: манифест, который
    обещает оформление, которого в коде нет, — это ложь витрины о самой себе,
    и обнаруживается она через 404 на каждой карточке.
    """
    исходник = рантайм.read_text(encoding="utf-8")
    константы = {m.group("name"): m.group("value")
                 for m in _КОНСТАНТА_ВЕРСИИ.finditer(исходник)}
    совпало = _НАБОР_ВЕРСИЙ.search(исходник)
    if not совпало:
        raise ОшибкаРелиза(
            f"в {рантайм} нет ОФОРМЛЕНИЕ_ВЕРСИИ: проверить объявляемую версию нечем, "
            "а выкладывать непроверенным — тот самый случай, ради которого проверка и есть"
        )
    имена = [ч.strip() for ч in совпало.group("body").split(",") if ч.strip()]
    набор = {константы[и] for и in имена if и in константы}
    if ВЕРСИЯ_ОФОРМЛЕНИЯ not in набор:
        raise ОшибкаРелиза(
            f"артефакт исполняет оформление {sorted(набор)}, а манифест объявил бы "
            f"{ВЕРСИЯ_ОФОРМЛЕНИЯ}. Витрина ушла бы на дореформенные ветки без единого "
            "сообщения, и все маршруты /title/ отдавали бы 404"
        )
    карта: dict[str, set[str]] = {}
    блок = _ПЕРЕРАБОТАНО.search(исходник)
    if блок:
        for семейство, тело in re.findall(
                r'"([a-z0-9-]+)"\s*:\s*frozenset\(\{([^}]*)\}\)', блок.group("body")):
            карта[семейство] = {константы[ч.strip()] for ч in тело.split(",")
                                if ч.strip() in константы}
    if FAMILY in карта and ВЕРСИЯ_ОФОРМЛЕНИЯ not in карта[FAMILY]:
        raise ОшибкаРелиза(
            f"семейство {FAMILY} получает переработанное оформление только на "
            f"{sorted(карта[FAMILY])}, а объявлено {ВЕРСИЯ_ОФОРМЛЕНИЯ}"
        )
    return {"artifact_supports": sorted(набор),
            "family_reworked_on": sorted(карта.get(FAMILY, ())),
            "declared": ВЕРСИЯ_ОФОРМЛЕНИЯ}


def манифест(release_id: str, артефакт_sha: str) -> dict:
    return {
        "schema_version": 1,
        "site_id": SITE_ID,
        "domain": DOMAIN,
        "template_family": FAMILY,
        "profile": ПРОФИЛЬ,
        "design_version": ВЕРСИЯ_ОФОРМЛЕНИЯ,
        "build_id": release_id,
        "source_commit": ИСХОДНЫЙ_КОММИТ,
        "runtime_commit": ИСХОДНЫЙ_КОММИТ,
        "artifact_sha256": артефакт_sha,
        "code_file_sha256": ЗАКРЕПЛЁННЫЙ_SHA256,
        "artifact_path": str(РЕЛИЗЫ / release_id / РАНТАЙМ),
        "service_name": UNIT,
        "port": PORT,
        "expected_indexability": "noindex,nofollow",
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pinned_from": {
            "release": ИСТОЧНИК.name,
            "code_sha256": ЗАКРЕПЛЁННЫЙ_SHA256,
            "why": "назначенный и исполняемый релиз zona-01, подтверждён живой выдачей",
        },
        "assignment_scope": "ZONA_02_ONLY",
        "note": (
            "Манифест витрины zonafilm.cc. Ничего не наследует от zona-01, кроме "
            "байтов шаблона: домен, canonical, счётчики, идентификаторы аналитики "
            "и имя службы свои."
        ),
    }


def записать_атомарно(путь: Path, данные: bytes) -> str:
    временный = путь.with_name(путь.name + f".tmp.{os.getpid()}")
    временный.write_bytes(данные)
    os.replace(временный, путь)
    return hashlib.sha256(данные).hexdigest()


def переставить_ссылку(ссылка: Path, цель: str) -> str | None:
    прежняя = os.readlink(ссылка) if ссылка.is_symlink() else None
    if прежняя == цель:
        return прежняя
    временная = ссылка.with_name(ссылка.name + f".tmp.{os.getpid()}")
    if временная.is_symlink() or временная.exists():
        временная.unlink()
    os.symlink(цель, временная)
    os.replace(временная, ссылка)
    return прежняя


def обновить_реестр(порт: int, применить: bool) -> dict:
    """Добавить ключ zona-02. Байты остальных записей обязаны совпасть.

    Общий файл читают шесть юнитов при старте. Добавление ключа для работающих
    процессов инертно — они прочли реестр однажды. А вот молча изменить чужую
    запись здесь означало бы переселить чужую витрину при её следующем
    перезапуске, и заметили бы это через недели.
    """
    было = json.loads(РЕЕСТР_ДИСПЕТЧЕРА.read_text(encoding="utf-8"))
    стало = json.loads(json.dumps(было))
    стало.setdefault("sites", {})[SITE_ID] = {
        "site_id": SITE_ID,
        "family": FAMILY,
        "port": порт,
        "unit": UNIT,
        "unit_path": f"/etc/systemd/system/{UNIT}",
        "exec_path": str(ФРОНТ / РАНТАЙМ),
        "manifest_path": str(ФРОНТ / f"template-manifest-{SITE_ID}.json"),
        "exact_domain": DOMAIN,
        "canonical_host": DOMAIN,
        "indexing_enabled": False,
        "scope": "exact-domain-registry",
        "release_link": str(ВИТРИНЫ / SITE_ID / "current"),
    }
    if SITE_ID not in (было.get("out_of_registry") or []) and \
       SITE_ID not in (было.get("in_registry") or []):
        стало.setdefault("in_registry", []).append(SITE_ID)

    чужие_до = {k: v for k, v in (было.get("sites") or {}).items() if k != SITE_ID}
    чужие_после = {k: v for k, v in (стало.get("sites") or {}).items() if k != SITE_ID}
    if чужие_до != чужие_после:
        raise ОшибкаРелиза("правка реестра задела чужие записи — выкладка прекращена")

    результат = {
        "neighbours_unchanged": True,
        "added_key": SITE_ID,
        "before_sha256": hashlib.sha256(
            РЕЕСТР_ДИСПЕТЧЕРА.read_bytes()).hexdigest(),
    }
    if применить:
        данные = (json.dumps(стало, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        резерв = РЕЕСТР_ДИСПЕТЧЕРА.with_name(
            РЕЕСТР_ДИСПЕТЧЕРА.name + f".before-{SITE_ID}."
            + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
        shutil.copy2(РЕЕСТР_ДИСПЕТЧЕРА, резерв)
        результат["backup"] = str(резерв)
        результат["after_sha256"] = записать_атомарно(РЕЕСТР_ДИСПЕТЧЕРА, данные)
    return результат


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="без него не пишется ничего")
    args = parser.parse_args()

    файлы = собрать_файлы()
    версия = проверить_версию_оформления(файлы[РАНТАЙМ])
    release_id = идентификатор(файлы, DOMAIN)
    каталог_релиза = РЕЛИЗЫ / release_id
    отчёт: dict = {
        "site_id": SITE_ID,
        "domain": DOMAIN,
        "release_id": release_id,
        "release_dir": str(каталог_релиза),
        "pinned_source": str(ИСТОЧНИК),
        "pinned_code_sha256": ЗАКРЕПЛЁННЫЙ_SHA256,
        "files": sorted(файлы),
        "design_version_gate": версия,
        "mode": "apply" if args.apply else "dry-run",
        "mutations": 0,
    }

    if not args.apply:
        print(json.dumps(отчёт, ensure_ascii=False, indent=2))
        return 0

    каталог_релиза.mkdir(parents=True, exist_ok=True)
    записанные = {}
    for имя, источник in файлы.items():
        цель = каталог_релиза / имя
        if not цель.exists() or sha256(цель) != sha256(источник):
            shutil.copy2(источник, цель)
        записанные[имя] = sha256(цель)
    отчёт["release_files_sha256"] = записанные
    отчёт["mutations"] += len(записанные)

    артефакт_sha = записанные[РАНТАЙМ]
    м = манифест(release_id, артефакт_sha)
    путь_манифеста = ФРОНТ / f"template-manifest-{SITE_ID}.json"
    отчёт["manifest_path"] = str(путь_манифеста)
    отчёт["manifest_sha256"] = записать_атомарно(
        путь_манифеста, (json.dumps(м, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    отчёт["mutations"] += 1

    (каталог_релиза / "RELEASE.json").write_text(
        json.dumps({
            "release": release_id,
            "site": SITE_ID,
            "domain": DOMAIN,
            "artifact_sha256": артефакт_sha,
            "code_sha256": ЗАКРЕПЛЁННЫЙ_SHA256,
            "source_commit": ИСХОДНЫЙ_КОММИТ,
            "pinned_from": ИСТОЧНИК.name,
            "built_at": м["built_at"],
            "modules": sorted(n for n in файлы if n != РАНТАЙМ),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    каталог_витрины = ВИТРИНЫ / SITE_ID
    каталог_витрины.mkdir(parents=True, exist_ok=True)
    ссылка = каталог_витрины / "current"
    прежняя = переставить_ссылку(ссылка, f"../../releases/{release_id}")
    if прежняя and прежняя != f"../../releases/{release_id}":
        (каталог_витрины / "PREVIOUS_TARGET.txt").write_text(прежняя + "\n", encoding="utf-8")
    отчёт["current_link"] = str(ссылка)
    отчёт["current_target"] = os.readlink(ссылка)
    отчёт["previous_target"] = прежняя
    отчёт["mutations"] += 1

    отчёт["dispatcher_registry"] = обновить_реестр(PORT, применить=True)
    отчёт["mutations"] += 1

    print(json.dumps(отчёт, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
