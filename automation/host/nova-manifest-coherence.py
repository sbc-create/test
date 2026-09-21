#!/usr/bin/env python3
"""Сторож когерентности: объявленная версия витрины против исполняемых байтов.

Все витрины Lords исполняют ОДИН файл — `/srv/lords/.frontend/lords-frontend.py`.
Различаются они только переменными окружения юнита и своим манифестом
`template-manifest-<site>.json`. Из этого следует свойство, которое легко
упустить: установка нового артефакта ради одной витрины немедленно меняет байты
для всех трёх. Пока соседние витрины не перезапущены, они продолжают исполнять
прежний код и расхождения не видно. После первого же перезапуска — суточным
refresh'ем, перезагрузкой, чем угодно — сосед начинает исполнять новый код,
продолжая объявлять в `/__template_version` прежние build_id и source_commit.

Ответ становится внутренне противоречивым: `runtime_sha256` считается по
фактическому файлу, а `build_id` и `source_commit` берутся из манифеста. Это
ровно тот дефект, который запрещён правилом «live-заголовки не должны заявлять
сборку, не совпадающую с байтами и рантаймом».

Сторож измеряет три независимые величины и сравнивает их:

* sha256 исполняемого файла на диске;
* artifact_sha256, объявленный манифестом каждой витрины;
* время старта процесса витрины против времени подмены файла.

Последнее и отличает «ещё не подхватил» от «уже лжёт»: процесс, поднятый
раньше подмены, честно исполняет старое; поднятый позже — исполняет новое.

Скрипт только читает. Он ничего не переписывает и не перезапускает: выбор между
переоформлением манифестов и откатом принадлежит владельцу.

Коды возврата: 0 — когерентно, 2 — расхождение, 3 — измерить нельзя.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import pathlib
import sys

FRONT = pathlib.Path("/srv/lords/.frontend")
RUNTIME = FRONT / "lords-frontend.py"

#: Порт → (витрина, домен, юнит). Источник — ExecStart юнитов systemd.
SITES: dict[str, tuple[str, str, str]] = {
    "9110": ("lords-01", "lordfilm47.space", "lords-nova-01.service"),
    "9111": ("lords-02", "lordserial33.biz", "nova-lords-02.service"),
    "9112": ("lords-03", "1lordserials1.online", "nova-lords-03.service"),
}

COHERENT = 0
DIVERGED = 2
UNMEASURABLE = 3


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_path(site: str, front: pathlib.Path) -> pathlib.Path:
    """Манифест витрины; lords-01 исторически обслуживается манифестом по умолчанию."""
    specific = front / f"template-manifest-{site}.json"
    return specific if specific.is_file() else front / "template-manifest.json"


def process_starts(front: pathlib.Path) -> dict[str, float]:
    """Порт → epoch старта процесса, который исполняет общий файл рантайма."""
    runtime = str(front / "lords-frontend.py")
    hz = os.sysconf("SC_CLK_TCK")
    btime = 0.0
    for line in pathlib.Path("/proc/stat").read_text().splitlines():
        if line.startswith("btime"):
            btime = float(line.split()[1])
            break

    starts: dict[str, float] = {}
    for entry in pathlib.Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().decode("utf-8", "replace").replace("\0", " ")
        except OSError:
            continue
        if runtime not in cmd:
            continue
        for port in SITES:
            if f"--port {port}" in cmd:
                try:
                    fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                    starts[port] = btime + int(fields[19]) / hz
                except (OSError, IndexError, ValueError):
                    continue
    return starts


def check(front: pathlib.Path = FRONT, starts: dict[str, float] | None = None) -> tuple[int, dict]:
    """Сверяет объявленное с исполняемым.

    `starts` принимается извне, чтобы проверку можно было прогнать на фикстуре:
    на живом хосте времена старта берутся из /proc, в тесте — задаются.
    """
    runtime = front / "lords-frontend.py"
    if not runtime.is_file():
        return UNMEASURABLE, {"error": f"нет исполняемого файла {runtime}"}

    runtime_sha = digest(runtime)
    runtime_mtime = runtime.stat().st_mtime
    starts = process_starts(front) if starts is None else starts

    sites = {}
    diverged = []
    for port, (site, domain, unit) in SITES.items():
        mpath = manifest_path(site, front)
        try:
            manifest = json.loads(mpath.read_text())
        except (OSError, ValueError):
            manifest = {}
        declared = manifest.get("artifact_sha256", "")
        started = starts.get(port)

        if not declared:
            verdict = "UNMEASURABLE_NO_MANIFEST"
        elif declared == runtime_sha:
            verdict = "COHERENT"
        elif started is None:
            verdict = "STALE_MANIFEST_PROCESS_DOWN"
        elif started < runtime_mtime:
            # Процесс старше подмены: он честно исполняет то, что объявляет.
            verdict = "PENDING_RESTART"
        else:
            verdict = "DIVERGED_RUNTIME_AHEAD_OF_MANIFEST"
            diverged.append(site)

        sites[site] = {
            "domain": domain,
            "unit": unit,
            "port": int(port),
            "manifest_path": str(mpath),
            "declared_artifact_sha256": declared,
            "declared_build_id": manifest.get("build_id", ""),
            "runtime_artifact_sha256": runtime_sha,
            "process_started_utc": _dt.datetime.fromtimestamp(started, _dt.timezone.utc).isoformat()
            if started
            else "NOT_RUNNING",
            "verdict": verdict,
        }

    report = {
        "checked_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "runtime_executable": str(runtime),
        "runtime_artifact_sha256": runtime_sha,
        "runtime_mtime_utc": _dt.datetime.fromtimestamp(
            runtime_mtime, _dt.timezone.utc
        ).isoformat(),
        "sites": sites,
        "diverged_sites": diverged,
        "verdict": "DIVERGED" if diverged else "COHERENT",
    }
    return (DIVERGED if diverged else COHERENT), report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--front", default=str(FRONT), help="каталог рантайма витрин")
    parser.add_argument("--record", help="куда записать отчёт JSON")
    args = parser.parse_args()

    code, report = check(pathlib.Path(args.front))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.record:
        pathlib.Path(args.record).write_text(text, encoding="utf-8")
    print(text)
    if code == DIVERGED:
        print(
            "РАСХОЖДЕНИЕ: витрины "
            + ", ".join(report["diverged_sites"])
            + " исполняют артефакт, которого не объявляют.",
            file=sys.stderr,
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
