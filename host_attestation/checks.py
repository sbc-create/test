"""Проверки живого флота. Каждая возвращает результат, а не бросает исключение.

Одно правило действует во всех без исключения: **недоступность — это BLOCKED**.
Не PASS, не пропуск, не «0 нарушений». Файла нет, базы нет, права не те,
служба не отвечает — всё это означает, что о флоте ничего не узнали, и так и
записывается. Проверка, которая при отсутствии доступа отчитывается успехом,
опаснее отсутствующей: отсутствующую хотя бы видно.

Секреты в результат не попадают. Проверки отчитываются числами, именами и
вердиктами; там, где ищется утечка, в отчёт идёт факт совпадения, а не то, что
совпало.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from factory.site_engine.attestation import contract as C
from factory.site_engine.attestation import credential_boundary as CB

КОРЕНЬ = Path(__file__).resolve().parent
БАЗОВАЯ_ЛИНИЯ = json.loads((КОРЕНЬ / "fleet-baseline.json").read_text(encoding="utf-8"))


def корень_флота() -> Path:
    """Корень боевых данных. Задаётся host-контрактом, а не зашит в код.

    Умолчание — объявленное в базовой линии. Переменная нужна не ради гибкости,
    а ради честности: контур, у которого путь зашит намертво, невозможно
    выполнить против стенда, и его никто никогда не проверяет целиком.
    """
    return Path(os.environ.get("FLEET_ROOT") or БАЗОВАЯ_ЛИНИЯ["fleet_root"])


def _журнал() -> Path:
    return корень_флота() / "audit-ledger/audit_ledger.sqlite3"


def _реестр() -> Path:
    return корень_флота() / "registry-core/registry.sqlite3"


def _ро(путь: Path) -> sqlite3.Connection:
    """Только чтение. Host-контур измеряет флот и не меняет его."""
    return sqlite3.connect(f"file:{путь}?mode=ro", uri=True)


def _результат(
    check_id: str, status: str, detail: str, observed: dict[str, Any] | None = None
) -> C.Результат:
    return C.Результат(
        check_id=check_id,
        status=status,
        detail=detail,
        measured_at=C.сейчас(),
        observed=observed or {},
    )


def _заблокировано(check_id: str, причина: str) -> C.Результат:
    return _результат(check_id, "BLOCKED", причина)


# ------------------------------------------------------------------- перепись


def перепись_флота() -> C.Результат:
    cid = "fleet.census"
    реестр = _реестр()
    if not реестр.is_file():
        return _заблокировано(cid, f"реестра {реестр} на этом хосте нет")
    try:
        c = _ро(реестр)
        всего = c.execute("SELECT count(*) FROM site").fetchone()[0]
        prod = c.execute(
            "SELECT count(*) FROM site WHERE environment='production' "
            "AND lifecycle_state='ACTIVE'"
        ).fetchone()[0]
        c.close()
    except sqlite3.Error as ош:
        return _заблокировано(cid, f"реестр не читается: {ош}")

    ждали_всего = БАЗОВАЯ_ЛИНИЯ["registry_sites_total"]
    ждали_prod = БАЗОВАЯ_ЛИНИЯ["registry_sites_production_active"]
    наблюдение = {
        "sites_total": всего,
        "sites_production_active": prod,
        "expected_total": ждали_всего,
        "expected_production": ждали_prod,
    }
    if (всего, prod) != (ждали_всего, ждали_prod):
        return _результат(
            cid,
            "FAIL",
            f"перепись разошлась с базовой линией: "
            f"{всего}/{prod} против {ждали_всего}/{ждали_prod}",
            наблюдение,
        )
    return _результат(cid, "PASS", f"{всего} сайтов, из них {prod} production ACTIVE", наблюдение)


def версия_реестра() -> C.Результат:
    cid = "registry.version"
    реестр = _реестр()
    if not реестр.is_file():
        return _заблокировано(cid, f"реестра {реестр} на этом хосте нет")
    try:
        c = _ро(реестр)
        версия = c.execute("SELECT max(version) FROM registry_version").fetchone()[0]
        c.close()
    except sqlite3.Error as ош:
        return _заблокировано(cid, f"версия реестра не читается: {ош}")
    ждали = БАЗОВАЯ_ЛИНИЯ["registry_version"]
    наблюдение = {"registry_version": версия, "expected": ждали}
    if версия != ждали:
        return _результат(cid, "FAIL", f"registry_version={версия}, ожидалась {ждали}", наблюдение)
    return _результат(cid, "PASS", f"registry_version={версия}", наблюдение)


def синтетические_записи() -> C.Результат:
    """Синтетические записи — зафиксированный долг, а не мусор: их не трогают."""
    cid = "registry.synthetic_records"
    реестр, журнал = _реестр(), _журнал()
    if not реестр.is_file() or not журнал.is_file():
        return _заблокировано(cid, "реестр или канонический журнал на этом хосте недоступны")
    try:
        ж = _ро(журнал)
        генезис = ж.execute("SELECT occurred_at FROM ledger_event WHERE ledger_seq=1").fetchone()
        долг = ж.execute(
            "SELECT count(*) FROM ledger_event WHERE "
            "event_type='technical.debt.observed.v1' AND "
            "resource_id LIKE 'synthetic%'"
        ).fetchone()[0]
        ж.close()
        if генезис is None:
            return _заблокировано(cid, "в журнале нет события генезиса")
        c = _ро(реестр)
        идентификаторы = [
            r[0]
            for r in c.execute(
                "SELECT site_id FROM site WHERE site_id LIKE 'synthetic%' " "ORDER BY site_id"
            )
        ]
        правки = list(
            c.execute(
                "SELECT event_id FROM outbox WHERE site_id LIKE 'synthetic%' "
                "AND occurred_at > ?",
                (генезис[0],),
            )
        )
        c.close()
    except sqlite3.Error as ош:
        return _заблокировано(cid, f"измерение не выполнено: {ош}")

    ждали = БАЗОВАЯ_ЛИНИЯ["synthetic_site_ids"]
    ждали_долг = БАЗОВАЯ_ЛИНИЯ["technical_debt_events_expected"]
    наблюдение = {
        "synthetic_site_ids": идентификаторы,
        "post_genesis_outbox_events": len(правки),
        "technical_debt_events": долг,
    }
    if идентификаторы != ждали:
        return _результат(
            cid, "FAIL", f"состав синтетических записей изменился: {идентификаторы}", наблюдение
        )
    if правки:
        return _результат(
            cid,
            "FAIL",
            f"после генезиса синтетические записи правились " f"({len(правки)} событий outbox)",
            наблюдение,
        )
    if долг != ждали_долг:
        return _результат(
            cid, "FAIL", f"событий о долге {долг}, ожидалось {ждали_долг}", наблюдение
        )
    return _результат(cid, "PASS", "три синтетические записи на месте и не изменялись", наблюдение)


# ------------------------------------------------------------ публичные домены


def публичные_домены() -> C.Результат:
    """Домены отвечают, и обращаемся к ним только на чтение."""
    cid = "fleet.public_domains"
    домены = БАЗОВАЯ_ЛИНИЯ["public_domains"]
    отказы, ответившие = [], []
    for домен in домены:
        запрос = urllib.request.Request(
            f"https://{домен}/",
            method="GET",
            headers={"User-Agent": "fleet-host-attestation", "Cache-Control": "no-cache"},
        )
        последняя: Exception | None = None
        for _ in range(3):
            try:
                with urllib.request.urlopen(запрос, timeout=40) as о:
                    if о.status != 200:
                        последняя = RuntimeError(f"статус {о.status}")
                        continue
                    if not о.read(4096):
                        последняя = RuntimeError("пустой ответ")
                        continue
                последняя = None
                break
            except (urllib.error.URLError, TimeoutError, OSError) as ош:
                последняя = ош
        if последняя is None:
            ответившие.append(домен)
        else:
            отказы.append(f"{домен}: {последняя}")

    наблюдение = {"methods_used": ["GET"], "responded": ответившие, "failed": отказы}
    if отказы:
        # Недоступность публичного домена — это факт о флоте, а не о доступе к
        # нему: сеть у контура есть, ответа нет. Поэтому FAIL, а не BLOCKED.
        return _результат(
            cid, "FAIL", "домены не ответили после трёх попыток: " + "; ".join(отказы), наблюдение
        )
    return _результат(cid, "PASS", f"{len(ответившие)} домена ответили 200 на GET", наблюдение)


# -------------------------------------------------------------- журнал и копии


def резервная_копия() -> C.Результат:
    """Копия создаётся и восстанавливается в изоляции, с совпадением снимков."""
    cid = "ledger.backup"
    if not _журнал().is_file():
        return _заблокировано(cid, f"канонического журнала {_журнал()} нет")
    try:
        from factory.site_engine.audit import ledger_backup as bk
    except ImportError as ош:  # pragma: no cover - модуль в репозитории есть
        return _заблокировано(cid, f"модуль резервного копирования недоступен: {ош}")
    try:
        манифест = bk.создать()
        итог = bk.восстановить(Path(bk.КАТАЛОГ) / манифест["backup_file"])
    except (OSError, sqlite3.Error, RuntimeError) as ош:
        return _заблокировано(cid, f"копия не создана или не восстановлена: {ош}")

    исход = итог["restored_snapshot"]
    источник = манифест["source_snapshot"]
    расхождения = [
        к for к in ("count", "last_seq", "chain_root") if исход.get(к) != источник.get(к)
    ]
    триггеры = set(итог.get("immutability_triggers") or ())
    наблюдение = {
        "restore_verdict": итог["restore_verdict"],
        "source_count": источник.get("count"),
        "restored_count": исход.get("count"),
        "immutability_triggers": sorted(триггеры),
    }
    if итог["restore_verdict"] != "PASS":
        return _результат(cid, "FAIL", f"восстановление: {итог.get('mismatches')}", наблюдение)
    if расхождения:
        return _результат(
            cid, "FAIL", f"снимок после восстановления разошёлся: {расхождения}", наблюдение
        )
    if not {"le_no_update", "le_no_delete"} <= триггеры:
        return _результат(
            cid, "FAIL", "у восстановленной копии нет триггеров неизменяемости", наблюдение
        )
    return _результат(
        cid, "PASS", f"копия восстановлена, {исход.get('count')} событий совпали", наблюдение
    )


ОПАСНЫЙ_ОБРАЗЕЦ = re.compile(
    r"(?i)(bearer\s+[A-Za-z0-9._-]{16,}|(?:token|secret|password|api[_-]?key)"
    r"\s*[=:]\s*['\"]?[A-Za-z0-9._-]{16,})"
)


def секреты_не_раскрыты() -> C.Результат:
    """Ни в ленте, ни в манифестах, ни в самом журнале секретов нет."""
    cid = "ledger.secrets_not_exposed"
    журнал = _журнал()
    if not журнал.is_file():
        return _заблокировано(cid, f"канонического журнала {журнал} нет")
    корень = корень_флота()
    цели = [корень / "audit-ledger/feed/audit-events.jsonl"]
    цели += sorted((корень / "audit-ledger/backups").glob("*.manifest.json"))
    цели += sorted((корень / "control-plane-contracts/1.1.0").rglob("*.json"))
    живые = [v for k, v in os.environ.items() if k.startswith("AUDIT_TOKEN_") and v]

    утечки, просмотрено = [], 0
    for файл in цели:
        if not файл.exists():
            continue
        просмотрено += 1
        текст = файл.read_text(encoding="utf-8", errors="replace")
        if ОПАСНЫЙ_ОБРАЗЕЦ.search(текст):
            утечки.append(f"{файл.name}: образец секрета")
        утечки += [f"{файл.name}: живой токен" for t in живые if t in текст]
    try:
        c = _ро(журнал)
        c.row_factory = sqlite3.Row
        текст = json.dumps(
            [dict(r) for r in c.execute("SELECT * FROM ledger_event")], ensure_ascii=False
        )
        c.close()
    except sqlite3.Error as ош:
        return _заблокировано(cid, f"журнал не читается: {ош}")
    if ОПАСНЫЙ_ОБРАЗЕЦ.search(текст):
        утечки.append("ledger_event: образец секрета")
    утечки += ["ledger_event: живой токен" for t in живые if t in текст]

    # В отчёт идёт ГДЕ нашли, а не что: иначе свидетельство об утечке само
    # становится утечкой.
    наблюдение = {"files_scanned": просмотрено, "findings": sorted(set(утечки))}
    if утечки:
        return _результат(cid, "FAIL", f"найдено совпадений: {len(утечки)}", наблюдение)
    return _результат(
        cid,
        "PASS",
        f"просмотрено {просмотрено} файлов и весь журнал, " "совпадений нет",
        наблюдение,
    )


# ----------------------------------------------------------------- процессы


def _команда(аргументы: list[str]) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(аргументы, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None


def слушатели() -> C.Результат:
    """Control API слушает ровно один раз, и дублирующих слушателей нет."""
    cid = "systemd.listeners"
    п = _команда(["ss", "-lntp"])
    if п is None or п.returncode != 0:
        return _заблокировано(cid, "ss недоступен: слушателей не перечислить")
    порты: dict[str, int] = {}
    for строка in п.stdout.splitlines()[1:]:
        части = строка.split()
        if len(части) < 4:
            continue
        адрес = части[3]
        if ":" in адрес:
            порты[адрес] = порты.get(адрес, 0) + 1
    дубли = {k: v for k, v in порты.items() if v > 1}
    ожидаемый = БАЗОВАЯ_ЛИНИЯ["control_api_listener"]
    наблюдение = {"duplicates": дубли, "control_api_listeners": порты.get(ожидаемый, 0)}
    if дубли:
        return _результат(cid, "FAIL", f"дублирующие слушатели: {дубли}", наблюдение)
    if порты.get(ожидаемый, 0) != 1:
        return _результат(
            cid,
            "FAIL",
            f"{ожидаемый} слушает {порты.get(ожидаемый, 0)} раз, " "ожидался ровно один",
            наблюдение,
        )
    return _результат(cid, "PASS", f"{ожидаемый} слушает ровно один раз, дублей нет", наблюдение)


def осиротевших_нет() -> C.Результат:
    """Эфемерные экземпляры прошлых прогонов на хосте не остались."""
    cid = "systemd.no_orphan_processes"
    п = _команда(["ps", "-eo", "pid,ppid,args"])
    if п is None or п.returncode != 0:
        return _заблокировано(cid, "ps недоступен: процессов не перечислить")
    ожидаемый_порт = "--port " + БАЗОВАЯ_ЛИНИЯ["control_api_listener"].split(":")[-1]
    осиротевшие = [
        с
        for с in п.stdout.splitlines()
        if "site_engine.api.server" in с and "--port 879" in с and ожидаемый_порт not in с
    ]
    наблюдение = {"orphans": len(осиротевшие)}
    if осиротевшие:
        return _результат(cid, "FAIL", f"осиротевших экземпляров: {len(осиротевшие)}", наблюдение)
    return _результат(cid, "PASS", "осиротевших экземпляров нет", наблюдение)


# ------------------------------------------------------- граница Templates


def граница_учётных_данных() -> C.Результат:
    """Снимок живого юнита и проверка его тем же правилом, что и в CI."""
    cid = "templates.credential_boundary"
    try:
        снимок = CB.снять()
    except CB.ДоступНедоступен as ош:
        return _заблокировано(cid, f"снимок не снят: {ош}")
    except CB.СнимокНевалиден as ош:
        return _результат(cid, "FAIL", f"снимок не соответствует контракту: {ош}")
    нарушения = CB.проверить(снимок)
    наблюдение = {
        "unit": снимок["unit"],
        "user": снимок["user"],
        "active_state": снимок["active_state"],
        "violations": нарушения,
    }
    if нарушения:
        return _результат(cid, "FAIL", f"нарушений границы: {len(нарушения)}", наблюдение)
    return _результат(cid, "PASS", f"граница юнита {снимок['unit']} не нарушена", наблюдение)


#: Порядок объявления = порядок выполнения. Держится рядом с контрактом:
#: проверка, объявленная в контракте, но не выполняемая здесь, сделала бы
#: каждое свидетельство неполным — и это заметят ворота, а не читатель.
ВСЕ: tuple[tuple[str, Callable[[], C.Результат]], ...] = (
    ("fleet.census", перепись_флота),
    ("registry.version", версия_реестра),
    ("registry.synthetic_records", синтетические_записи),
    ("fleet.public_domains", публичные_домены),
    ("ledger.backup", резервная_копия),
    ("ledger.secrets_not_exposed", секреты_не_раскрыты),
    ("systemd.listeners", слушатели),
    ("systemd.no_orphan_processes", осиротевших_нет),
    ("templates.credential_boundary", граница_учётных_данных),
)


def выполнить_все() -> list[C.Результат]:
    """Выполнить весь объявленный состав. Падение проверки — её BLOCKED.

    Исключение из проверки не должно обрывать измерение: остальные факты о
    флоте по-прежнему нужны, а необорванный прогон даёт полную картину того,
    что именно недоступно.
    """
    результаты = []
    for cid, функция in ВСЕ:
        try:
            результаты.append(функция())
        except Exception as ош:  # noqa: BLE001 - любой отказ это «не измерено»
            результаты.append(_заблокировано(cid, f"{type(ош).__name__}: {ош}"))
    return результаты
