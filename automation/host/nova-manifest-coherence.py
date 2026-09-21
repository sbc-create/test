#!/usr/bin/env python3
"""Сторож когерентности: объявленное витриной против фактически исполняемого.

## Что сверяется

Для каждой витрины из exact-domain реестра берутся три независимые величины:

* `artifact_sha256` из манифеста витрины — что она ОБЪЯВЛЯЕТ;
* путь исполняемого файла из `/proc/<pid>/cmdline` — что она ЗАПУСТИЛА;
* sha256 этого файла — что она ИСПОЛНЯЕТ.

Путь берётся из cmdline, а не из ExecStart юнита, и это принципиально: после
`execv` в загрузчике cmdline показывает настоящий путь релиза, тогда как
ExecStart остаётся общим для всех витрин. Сверять ExecStart значило бы сверять
намерение вместо результата.

## Откуда берётся список витрин

Из `nova-runtime-registry.py`, который собирает его из `config/site-profiles`
и юнитов systemd. Жёсткого списка доменов внутри этого файла нет и быть не
должно: прежняя редакция держала три витрины прямо в коде, и любое изменение
парка делало сторож тихо неполным — он возвращал «всё хорошо» про витрины, о
которых не знал.

## Коды возврата

0 — когерентно; 2 — расхождение; 3 — измерить нельзя.

Сторож только читает. Выбор между переоформлением манифеста, перепривязкой и
откатом принадлежит владельцу.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import importlib.util
import json
import os
import pathlib
import sys

FRONT = pathlib.Path("/srv/lords/.frontend")
RUNTIME_NAME = "lords-frontend.py"

COHERENT = 0
DIVERGED = 2
UNMEASURABLE = 3


def _загрузить_реестр_модуль():
    путь = pathlib.Path(__file__).resolve().parent / "nova-runtime-registry.py"
    spec = importlib.util.spec_from_file_location("nova_runtime_registry", путь)
    модуль = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(модуль)
    return модуль


def digest(path: pathlib.Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def процессы_по_портам(порты: set[int]) -> dict[int, dict]:
    """Порт → живой процесс: PID, исполняемый путь и время старта.

    Исполняемый путь — второй аргумент командной строки (после интерпретатора).
    Именно он меняется при `execv`, и именно он доказывает, какой релиз поднят.
    """
    hz = os.sysconf("SC_CLK_TCK")
    btime = 0.0
    for line in pathlib.Path("/proc/stat").read_text().splitlines():
        if line.startswith("btime"):
            btime = float(line.split()[1])
            break

    найдено: dict[int, dict] = {}
    for запись in pathlib.Path("/proc").iterdir():
        if not запись.name.isdigit():
            continue
        try:
            сырое = (запись / "cmdline").read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        части = [ч for ч in сырое.split("\0") if ч]
        if not части or RUNTIME_NAME not in сырое:
            continue
        порт = None
        for i, ч in enumerate(части):
            if ч == "--port" and i + 1 < len(части) and части[i + 1].isdigit():
                порт = int(части[i + 1])
        if порт is None or порт not in порты:
            continue
        скрипт = next((ч for ч in части[1:] if ч.endswith(".py")), "")
        try:
            поля = (запись / "stat").read_text().rsplit(")", 1)[1].split()
            начало = btime + int(поля[19]) / hz
            начало_iso = (
                _dt.datetime.fromtimestamp(начало, _dt.timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
            rss_mb = int(поля[21]) * os.sysconf("SC_PAGE_SIZE") // (1024 * 1024)
        except (OSError, IndexError, ValueError):
            начало_iso, rss_mb = "NOT_MEASURABLE", None
        найдено[порт] = {
            "pid": int(запись.name),
            "exec_script": скрипт,
            "started_utc": начало_iso,
            "rss_mb": rss_mb,
        }
    return найдено


def check(front: pathlib.Path = FRONT, registry: dict | None = None,
          процессы: dict[int, dict] | None = None) -> tuple[int, dict]:
    """Сверка. `registry` и `процессы` принимаются извне ради проверок на фикстуре."""
    if registry is None:
        registry = _загрузить_реестр_модуль().build(front=front)

    витрины = {
        s: v for s, v in (registry.get("sites") or {}).items()
        if v.get("scope") == "exact-domain-registry"
    }
    if not витрины:
        return UNMEASURABLE, {"error": "в реестре нет ни одной витрины с точным доменом"}

    порты = {int(v["port"]) for v in витрины.values()}
    if процессы is None:
        процессы = процессы_по_портам(порты)

    общий = front / RUNTIME_NAME
    загрузчик_по_общему_пути = (
        общий.is_file() and b"LORDS_RUNTIME_DISPATCHED" in общий.read_bytes()
    )
    сведения = {}
    расхождения = []
    общие_пути = []

    for site_id, запись in sorted(витрины.items()):
        порт = int(запись["port"])
        манифест_путь = pathlib.Path(запись["manifest_path"])
        try:
            манифест = json.loads(манифест_путь.read_text())
        except (OSError, ValueError):
            манифест = {}
        объявлено = манифест.get("artifact_sha256", "")

        ссылка = pathlib.Path(запись["release_link"])
        привязка = ссылка.resolve(strict=False) if ссылка.is_symlink() else None
        привязан_sha = digest(привязка / RUNTIME_NAME) if привязка else ""

        процесс = процессы.get(порт)
        исполняемый = pathlib.Path(процесс["exec_script"]) if процесс and процесс["exec_script"] else None
        исполняемый_sha = digest(исполняемый) if исполняемый else ""

        общий_путь = bool(исполняемый and исполняемый.resolve(strict=False) == общий.resolve(strict=False))
        if общий_путь:
            общие_пути.append(site_id)

        # Процесс, поднятый по общему пути, на котором СЕЙЧАС лежит загрузчик,
        # исполняет не загрузчик: он прочитал прежний файл при старте и держит
        # его в памяти. Хешировать путь в этом случае значит измерить чужие
        # байты и объявить расхождение, которого нет. Такое состояние — ожидание
        # перезапуска, и называть его надо так.
        до_загрузчика = общий_путь and загрузчик_по_общему_пути
        if до_загрузчика:
            исполняемый_sha = ""

        # Путь релиза сверяется отдельно от байтов. Два разных каталога могут
        # содержать одинаковые байты — так и вышло, когда замороженный снимок и
        # чистая сборка совпали побайтово. Тогда сверка одних digest'ов
        # объявляет когерентность, хотя витрина исполняет не тот релиз, который
        # объявлен, и перепривязка ещё не вступила в силу.
        объявленный_каталог = манифест.get("release_dir", "")
        фактический_каталог = str(исполняемый.parent) if исполняемый else ""
        путь_совпал = bool(объявленный_каталог) and фактический_каталог == объявленный_каталог

        if not процесс:
            вердикт = "NOT_RUNNING"
        elif до_загрузчика:
            вердикт = "PENDING_RESTART_PROCESS_PREDATES_LOADER"
        elif not объявлено:
            вердикт = "UNMEASURABLE_NO_MANIFEST"
        elif not исполняемый_sha:
            вердикт = "UNMEASURABLE_NO_EXEC_PATH"
        elif объявлено != исполняемый_sha:
            вердикт = "DIVERGED_RUNTIME_DIFFERS_FROM_MANIFEST"
            расхождения.append(site_id)
        elif объявленный_каталог and not путь_совпал:
            вердикт = "RELEASE_PATH_MISMATCH_PENDING_RESTART"
            расхождения.append(site_id)
        else:
            вердикт = "COHERENT"

        сведения[site_id] = {
            "exact_domain": запись.get("exact_domain"),
            "canonical_host": запись.get("canonical_host"),
            "unit": запись.get("unit"),
            "port": порт,
            "manifest_path": str(манифест_путь),
            "declared_artifact_sha256": объявлено,
            "declared_build_id": манифест.get("build_id", ""),
            "declared_source_commit": манифест.get("source_commit", ""),
            "declared_source_dirty": манифест.get("source_dirty", "ABSENT"),
            "declared_profile": манифест.get("profile", ""),
            "bound_release": str(привязка) if привязка else "",
            "bound_artifact_sha256": привязан_sha,
            "running_exec_path": str(исполняемый) if исполняемый else "",
            "declared_release_dir": объявленный_каталог,
            "running_release_dir": фактический_каталог,
            "release_path_matches_manifest": путь_совпал,
            "running_artifact_sha256": исполняемый_sha,
            "runs_shared_mutable_path": общий_путь,
            "indexing_enabled": запись.get("indexing_enabled"),
            "process": процесс or {"pid": None, "started_utc": "NOT_RUNNING"},
            "verdict": вердикт,
        }

    отчёт = {
        "checked_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "registry_scope": sorted(витрины),
        "out_of_registry": registry.get("out_of_registry", []),
        "shared_mutable_path": str(общий),
        "shared_path_is_loader": загрузчик_по_общему_пути,
        "sites_running_shared_mutable_path": общие_пути,
        "sites": сведения,
        "diverged_sites": расхождения,
        "verdict": "DIVERGED" if расхождения else "COHERENT",
    }
    return (DIVERGED if расхождения else COHERENT), отчёт


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--front", default=str(FRONT))
    parser.add_argument("--record", help="куда записать отчёт JSON")
    args = parser.parse_args()

    код, отчёт = check(pathlib.Path(args.front))
    текст = json.dumps(отчёт, ensure_ascii=False, indent=2)
    if args.record:
        pathlib.Path(args.record).write_text(текст, encoding="utf-8")
    print(текст)
    if код == DIVERGED:
        print(
            "РАСХОЖДЕНИЕ: " + ", ".join(отчёт["diverged_sites"])
            + " исполняют артефакт, которого не объявляют.",
            file=sys.stderr,
        )
    return код


if __name__ == "__main__":
    raise SystemExit(main())
