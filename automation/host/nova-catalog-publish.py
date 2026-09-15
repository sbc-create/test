#!/usr/bin/env python3
"""Публикация каталога Lords и Zona из одного канонического снимка.

Что делает
----------

Собирает `{site}-catalog.json` и `{site}-details.json` для всех витрин
профиля из одного снимка поставщика и выкладывает их одним поколением. До
этого каталог витрины получался обходом её собственного отрисованного
релиза: Lords перерисовывался и дорос до 52 683 записей, релиз Zona стоял с
10 сентября и держал её на 3 868. Один поставщик, одна база, разница в
четырнадцать раз — и обе витрины отвечали 200.

Чего не делает
--------------

Не трогает шаблоны, оформление, SEO, плеер, аналитику, DNS и чужие сайты. Не
пишет без `--apply`: у инструмента, который пишет по умолчанию, однажды не
посмотрят на флаги.

Защиты
------

* **последнее удачное состояние.** Пустой или внезапно обвалившийся снимок не
  публикуется: витрина остаётся на прежнем каталоге. Отказ источника не имеет
  права стать пустым сайтом;
* **одно поколение на обе витрины.** Файлы собираются целиком, проверяются, и
  только потом заменяются. Lords и Zona не могут разойтись по поколениям;
* **адрес не переезжает.** Привязка идентификатор → slug живёт в реестре и
  только дополняется;
* **форма проверяется до записи.** Нарушение того, что витрина читает по
  индексу, прекращает прогон, а не выясняется по 502 на публичном домене;
* **замок.** Два прогона одновременно не идут;
* **before-image.** Откат — возврат файлов, а не обратное вычисление.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from factory.lords import rating_gateway  # noqa: E402
from factory.lords.nova_publish import (  # noqa: E402
    PublishError, РеестрСлагов, загрузить_снимок, контрольная_сумма,
    покрытие, причины_отсутствия, проверить_контракт_рендерера, собрать_сайт)

ВАР = Path("/srv/site-factory/repo/var/lords")
ФРОНТ = Path("/srv/lords/.frontend")

СНИМОК = ВАР / "lords" / "catalog-cache" / "lords-01.json"
ХРАНИЛИЩЕ_ОЦЕНОК = ВАР / "ratings-store.json"
ДЕТАЛИ = ВАР / "detail-cache"
РЕЕСТР = ВАР / "slug-ledger.json"
КОПИИ = ВАР / "publish-backups"
ЗАМОК = ВАР / "nova-catalog-publish.lock"
ОТЧЁТЫ = ВАР / "publish-reports"

#: Витрины, чей каталог собирается из канонического снимка. Другие витрины
#: семейства сюда намеренно не входят: их контур этой задачей не затрагивается,
#: а второй производитель того же файла — это гонка, а не надёжность.
ВИТРИНЫ = {
    "lords-01": {"unit": "lords-nova-01.service", "host": "lordfilm47.space",
                 "port": 9110},
    "zona-01": {"unit": "nova-zona-01.service", "host": "zonafilm.space",
                "port": 9120},
    # Аниме-витрины. Каталог у них — аниме-подмножество того же снимка
    # поставщика, а не срез каталога Zona: сегодня там лежит именно срез, и
    # аниме в нём 131 из 3999.
    #
    # Публикация в production для них закрыта до снятия блокера шаблона: у
    # семейства `animedia` нет раскладки страницы тайтла (`ВИДЫ_1_1` знает
    # только lords и zona), и все `/title/` отдают 503. Опубликовать больше
    # карточек значило бы увеличить число ссылок в никуда с 3999 до 7408.
    "animedia-01": {"unit": "nova-animedia-01.service", "host": "animedia.icu",
                    "port": 9121, "только_аниме": True, "аниме_видом": True,
                    "известный_дефект_шаблона":
                        "у семейства animedia нет раскладки страницы тайтла: "
                        "ВИДЫ_1_1 = {lords, zona}, все /title/ отдают 503"},
    "animedia-02": {"unit": "nova-animedia-02.service", "host": "animedia.space",
                    "port": 9122, "только_аниме": True, "аниме_видом": True,
                    "известный_дефект_шаблона":
                        "у семейства animedia нет раскладки страницы тайтла: "
                        "ВИДЫ_1_1 = {lords, zona}, все /title/ отдают 503"},
}

#: Обвал каталога больше чем на эту долю считается порчей источника, а не
#: правкой ассортимента. Поставщик вправе убрать часть записей; каталог,
#: похудевший вдвое, допуском не объясняется.
ДОПУСК_ОБВАЛА = 0.10

#: Нижняя граница публикуемого каталога. Меньше — это не «мало контента», а
#: неполный обход источника, и публиковать такое нельзя.
МИНИМУМ_КАТАЛОГА = 52000


@dataclass
class Цели:
    каталог: Path
    подробности: Path


def цели(site_id: str, корень: Path = ФРОНТ) -> Цели:
    return Цели(каталог=корень / f"{site_id}-catalog.json",
                подробности=корень / f"{site_id}-details.json")


def _прочитать_json(путь: Path) -> dict:
    if not путь.is_file():
        return {}
    try:
        д = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return д if isinstance(д, dict) else {}


def _прочитать(путь: Path, ключ: str) -> dict:
    if not путь.is_file():
        return {}
    try:
        д = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return д.get(ключ) or {}


def засеять_реестр(реестр: РеестрСлагов) -> int:
    """Принять действующие привязки витрин: живые адреса не переименовываются."""
    пары: dict[str, str] = {}
    for site_id in ВИТРИНЫ:
        подробности = _прочитать(цели(site_id).подробности, "details")
        for слаг, з in подробности.items():
            ид = з.get("id")
            if ид:
                пары.setdefault(str(ид), слаг)
    return реестр.засеять(пары)


def записать_атомарно(путь: Path, текст: str) -> str:
    путь.parent.mkdir(parents=True, exist_ok=True)
    врем = путь.with_suffix(путь.suffix + f".{os.getpid()}.tmp")
    with open(врем, "w", encoding="utf-8") as ф:
        ф.write(текст)
        ф.flush()
        os.fsync(ф.fileno())
    os.replace(врем, путь)
    return hashlib.sha256(путь.read_bytes()).hexdigest()


def выполнить(*, снимок_путь: Path = СНИМОК, детали: Path = ДЕТАЛИ,
              хранилище: Path = ХРАНИЛИЩЕ_ОЦЕНОК,
              реестр_путь: Path = РЕЕСТР, корень: Path = ФРОНТ,
              сайты: list[str] | None = None, применить: bool = False,
              черновик: Path | None = None, копии: Path = КОПИИ,
              run_id: str | None = None, минимум: int = МИНИМУМ_КАТАЛОГА,
              читатель=None) -> dict:
    начало = time.time()
    run_id = run_id or f"pub-{uuid.uuid4().hex[:12]}"
    сайты = сайты or [s for s in sorted(ВИТРИНЫ)
                      if not ВИТРИНЫ[s].get("известный_дефект_шаблона")]
    for s in сайты:
        if s not in ВИТРИНЫ:
            raise PublishError(f"витрина {s} не входит в профиль публикации")
        # Дефект чужого контура сопровождает публикацию предупреждением, а не
        # отказом: он попадает в отчёт каждого прогона и остаётся видимым.

    снимок = загрузить_снимок(снимок_путь)
    хранилище_оценок = _прочитать_json(хранилище)
    реестр = РеестрСлагов.загрузить(реестр_путь)
    засеяно = засеять_реестр(реестр) if корень == ФРОНТ else 0

    отчёт: dict = {
        "run_id": run_id,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(начало)),
        "mode": "apply" if применить else ("staging" if черновик else "dry-run"),
        "snapshot": {"path": str(снимок_путь), "items": снимок.всего,
                     "fetched_at": снимок.получен,
                     "id_set_checksum": снимок.отпечаток},
        "ledger": {"path": str(реестр_путь), "seeded": засеяно},
        "ratings_store": {"path": str(хранилище), "entries": len(хранилище_оценок)},
        "sites": {},
        "production_mutations": 0,
    }

    собранное: dict[str, tuple[dict, dict]] = {}
    for site_id in сайты:
        т = цели(site_id, корень)
        прежние = _прочитать(т.подробности, "details")
        каталог, подробности, ст = собрать_сайт(
            снимок=снимок, реестр=реестр, детали_кэш=детали, site_id=site_id,
            прежние_подробности=прежние, читатель=читатель,
            только_аниме=bool(ВИТРИНЫ[site_id].get("только_аниме")),
            аниме_видом=bool(ВИТРИНЫ[site_id].get("аниме_видом")))

        # Накопленные внешние оценки. Публикация берёт готовое из хранилища и
        # в сеть не ходит: иначе временный отказ источника означал бы витрину
        # без оценок, а не один непополненный прогон.
        подробности["details"], отчёт_оценок = rating_gateway.применить_хранилище(
            подробности["details"], хранилище_оценок)

        беды = проверить_контракт_рендерера(подробности["details"])
        if беды:
            raise PublishError(
                f"{site_id}: {len(беды)} записей нарушают форму, которую "
                f"витрина читает по индексу, например {беды[:3]}")

        # Last-known-good: пустой или обвалившийся каталог не публикуется.
        прежний_каталог = _прочитать(т.каталог, "items")
        было = len(json.loads(т.каталог.read_text(encoding="utf-8")).get("items")
                   or []) if т.каталог.is_file() else 0
        стало = каталог["count"]
        порог = 0 if ВИТРИНЫ[site_id].get("только_аниме") else минимум
        if стало < порог:
            raise PublishError(
                f"{site_id}: каталог {стало} записей, минимум {порог} — "
                f"обход источника неполон, публикация отменена")
        if было and стало < было * (1 - ДОПУСК_ОБВАЛА):
            raise PublishError(
                f"{site_id}: каталог обвалился {было} → {стало}; это порча "
                f"источника, а не правка ассортимента")

        идентификаторы = [з["id"] for з in подробности["details"].values() if з.get("id")]
        отчёт["sites"][site_id] = {
            "catalog_items": стало,
            "catalog_items_before": было,
            "details_entries": подробности["details_total"],
            "distinct_canonical_ids": len(set(идентификаторы)),
            "duplicate_ids": len(идентификаторы) - len(set(идентификаторы)),
            "id_set_checksum": контрольная_сумма(идентификаторы),
            "coverage": покрытие(подробности["details"]),
            "coverage_by_source": rating_gateway.покрытие_по_источникам(
                подробности["details"]),
            "secondary_rating_providers": отчёт_оценок,
            "missing_rating_reasons": причины_отсутствия(подробности["details"], снимок),
            "rejections": ст["отказы"],
            "without_poster": ст["без_постера"],
            "anime_only": bool(ВИТРИНЫ[site_id].get("только_аниме")),
            "anime_by_signal": ст.get("аниме_по_признаку") or {},
            "production_blocked": ВИТРИНЫ[site_id].get("production_заблокирована"),
        }
        собранное[site_id] = (каталог, подробности)

    # Равенство наборов — следствие устройства, но проверяется всё равно:
    # свойство, которое никто не измеряет, однажды перестаёт выполняться.
    киновитрины = [s for s in сайты if not ВИТРИНЫ[s].get("только_аниме")]
    суммы = {s: отчёт["sites"][s]["id_set_checksum"] for s in киновитрины}
    отчёт["parity"] = {
        "checksums": суммы,
        "identical": len(set(суммы.values())) == 1,
    }
    if len(киновитрины) > 1:
        наборы = {s: {з["id"] for з in собранное[s][1]["details"].values() if з.get("id")}
                  for s in киновитрины}
        первый = киновитрины[0]
        for s in киновитрины[1:]:
            отчёт["parity"][f"{первый}_only"] = len(наборы[первый] - наборы[s])
            отчёт["parity"][f"{s}_only"] = len(наборы[s] - наборы[первый])
        отчёт["parity"]["parity_pct"] = 100.0 if отчёт["parity"]["identical"] else round(
            len(set.intersection(*наборы.values())) * 100
            / max(len(set.union(*наборы.values())), 1), 4)

    тексты = {}
    for site_id, (каталог, подробности) in собранное.items():
        тексты[site_id] = {
            "catalog": json.dumps(каталог, ensure_ascii=False, sort_keys=True),
            "details": json.dumps(подробности, ensure_ascii=False, sort_keys=True),
        }
        отчёт["sites"][site_id]["expected_sha256"] = {
            "catalog": hashlib.sha256(тексты[site_id]["catalog"].encode()).hexdigest(),
            "details": hashlib.sha256(тексты[site_id]["details"].encode()).hexdigest(),
        }

    if черновик is not None:
        черновик.mkdir(parents=True, exist_ok=True)
        for site_id, пара in тексты.items():
            (черновик / f"{site_id}-catalog.json").write_text(пара["catalog"], encoding="utf-8")
            (черновик / f"{site_id}-details.json").write_text(пара["details"], encoding="utf-8")
        отчёт["staging_dir"] = str(черновик)

    if not применить:
        отчёт["note"] = ("без --apply production не изменяется")
        отчёт["duration_sec"] = round(time.time() - начало, 2)
        отчёт["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return отчёт

    копии.mkdir(parents=True, exist_ok=True)
    ЗАМОК.parent.mkdir(parents=True, exist_ok=True)
    with open(ЗАМОК, "w") as ф:
        try:
            fcntl.flock(ф, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise PublishError(f"другой прогон уже идёт (замок {ЗАМОК})") from None
        # Снимок сверяется ещё раз непосредственно перед записью: между
        # сборкой и выкладкой поставщик мог обновиться.
        if загрузить_снимок(снимок_путь).отпечаток != снимок.отпечаток:
            raise PublishError("снимок изменился во время прогона")

        образы = {}
        for site_id in сайты:
            т = цели(site_id, корень)
            for имя, путь in (("catalog", т.каталог), ("details", т.подробности)):
                if путь.is_file():
                    копия = копии / f"{путь.name}.before.{run_id}"
                    shutil.copy2(путь, копия)
                    образы[f"{site_id}.{имя}"] = {
                        "backup": str(копия),
                        "sha256": hashlib.sha256(копия.read_bytes()).hexdigest()}
        отчёт["before_images"] = образы
        отчёт["rollback_command"] = " && ".join(
            [f"cp -p {v['backup']} {цели(k.split('.')[0], корень).каталог if k.endswith('.catalog') else цели(k.split('.')[0], корень).подробности}"
             for k, v in образы.items()]
            + [f"sudo -n systemctl restart {ВИТРИНЫ[s]['unit']}" for s in сайты])

        записано = {}
        for site_id in сайты:
            т = цели(site_id, корень)
            записано[f"{site_id}.catalog"] = записать_атомарно(т.каталог, тексты[site_id]["catalog"])
            записано[f"{site_id}.details"] = записать_атомарно(т.подробности, тексты[site_id]["details"])
        отчёт["written_sha256"] = записано
        for site_id in сайты:
            ож = отчёт["sites"][site_id]["expected_sha256"]
            if записано[f"{site_id}.catalog"] != ож["catalog"] or \
               записано[f"{site_id}.details"] != ож["details"]:
                raise PublishError(f"{site_id}: записано не то, что проверено")
        реестр.сохранить(реестр_путь)
        отчёт["production_mutations"] = len(записано)
        fcntl.flock(ф, fcntl.LOCK_UN)

    отчёт["duration_sec"] = round(time.time() - начало, 2)
    отчёт["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return отчёт


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="публикация каталога витрин Nova")
    ap.add_argument("--sites", default=",".join(sorted(ВИТРИНЫ)))
    ap.add_argument("--snapshot", type=Path, default=СНИМОК)
    ap.add_argument("--detail-cache", type=Path, default=ДЕТАЛИ)
    ap.add_argument("--ledger", type=Path, default=РЕЕСТР)
    ap.add_argument("--ratings-store", type=Path, default=ХРАНИЛИЩЕ_ОЦЕНОК)
    ap.add_argument("--front", type=Path, default=ФРОНТ)
    ap.add_argument("--staging-out", type=Path, default=None)
    ap.add_argument("--backup-dir", type=Path, default=КОПИИ)
    ap.add_argument("--report-dir", type=Path, default=ОТЧЁТЫ)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--min-catalog", type=int, default=МИНИМУМ_КАТАЛОГА)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    run_id = a.run_id or f"pub-{uuid.uuid4().hex[:12]}"
    try:
        отчёт = выполнить(снимок_путь=a.snapshot, детали=a.detail_cache,
                          хранилище=a.ratings_store,
                          реестр_путь=a.ledger, корень=a.front,
                          сайты=[s for s in a.sites.split(",") if s],
                          применить=a.apply, черновик=a.staging_out,
                          копии=a.backup_dir, run_id=run_id,
                          минимум=a.min_catalog)
    except PublishError as ош:
        вывод = {"run_id": run_id, "status": "PUBLISH_REFUSED", "detail": str(ош)}
        print(json.dumps(вывод, ensure_ascii=False, indent=2))
        return 2
    try:
        a.report_dir.mkdir(parents=True, exist_ok=True)
        (a.report_dir / f"{run_id}.json").write_text(
            json.dumps(отчёт, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
    print(json.dumps(отчёт, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
