#!/usr/bin/env python3
"""Каким станет хост после транзакции — посчитано до того, как что-то тронуто.

Установщик проверяет результат у себя, но отчёт операции о самой себе —
слабейший вид доказательства, и получить его можно только выполнив операцию.
Этот модуль отвечает на тот же вопрос заранее и без единой мутации: он
собирает эффективные определения юнитов так, как их увидит systemd после
установки drop-in'ов из манифеста, и проверяет, остаётся ли хоть один путь
к КОДУ на территории агента.

Проверка структурная, а не файловая, и это осознанно. Закреплённого каталога
на диске ещё нет, спрашивать у файловой системы про его владельца бессмысленно;
зато можно доказать, что все пути к коду ведут под ``/opt`` (root на всём
пути), в ``/usr`` или в ``/bin`` — и ни один не ведёт в
``/srv/site-factory``, ``/srv/sites`` или ``/home``. Владельца самих
закреплённых файлов обеспечивает установщик (``chown -R root:root``) и
подтверждает его пост-аудит.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit_root_units as audit_mod  # noqa: E402

#: Территория агента: любой путь отсюда он может подменить. Владение каталогом
#: достаточно — переименует и подставит своё, права на файл роли не играют.
AGENT_ROOTS = ("/srv/site-factory", "/srv/sites", "/home/")

#: Белого списка каталогов здесь намеренно нет. Перечислять «разрешённые»
#: корни — значит угадывать: один забытый `/run/...` превращается в ложное
#: срабатывание, один лишний — в дыру, объявленную безопасной. Вместо этого
#: путь, который уже существует, проверяется по фактическому владельцу и
#: правам, а путь внутри будущего закреплённого каталога принимается по
#: построению: его создаёт установщик и сам же делает `chown root:root`.


def _expand(value: str, pinned_root: str, release_id: str) -> str:
    bundle = f"{pinned_root}/{release_id}/bundle"
    venv = f"{pinned_root}/{release_id}/venv"
    relocated = f"{pinned_root}/relocated"
    return (value.replace("{bundle}", bundle)
                 .replace("{venv}", venv)
                 .replace("{relocated}", relocated))


def simulate(manifest: dict, release_id: str, unit_dir: Path | None = None) -> dict:
    directory = unit_dir or audit_mod.UNIT_DIR
    pinned_root = manifest["release"]["pinned_root"]
    path_env = manifest["pinned_path_env"]
    by_unit = {u["unit"]: u for u in manifest["units"]}

    findings, rows = [], []
    for unit_path in sorted(p for p in directory.glob("*.service") if p.is_file()):
        view = audit_mod.read_unit(unit_path)
        if view is None or not view.runs_as_root:
            continue

        pin = by_unit.get(view.name)
        # Эффективное состояние после drop-in'а: он ЗАМЕНЯЕТ ExecStart
        # (`ExecStart=` сбрасывает список) и переопределяет переменные.
        if pin and pin.get("exec_start"):
            exec_starts = [_expand(pin["exec_start"], pinned_root, release_id)]
        else:
            exec_starts = list(view.exec_starts)

        environment = dict(view.environment)
        if pin:
            environment["PATH"] = path_env
            for key, value in (pin.get("environment") or {}).items():
                environment[key] = _expand(value, pinned_root, release_id)

        working = view.working_directory
        if pin and pin.get("working_directory"):
            working = _expand(pin["working_directory"], pinned_root, release_id)

        effective = audit_mod.UnitView(
            name=view.name, runs_as_root=True, exec_starts=exec_starts,
            environment=environment, env_files=view.env_files,
            working_directory=working, holds_credentials=view.holds_credentials)

        # Какие пути этот юнит будет считать кодом.
        code_paths: list[tuple[str, str]] = []
        for command in exec_starts:
            tokens = audit_mod._tokenize(command)
            if tokens:
                code_paths.append(("ExecStart", tokens[0]))
                for argument in tokens[1:]:
                    if argument.startswith("/"):
                        code_paths.append(("аргумент-скрипт", argument))
        for name in audit_mod.CODE_PATH_VARS:
            value = environment.get(name)
            if not value:
                continue
            separator = ":" if name in ("PYTHONPATH", "PATH") else None
            for candidate in (value.split(separator) if separator else [value]):
                if candidate:
                    code_paths.append((name, candidate))
        if working and audit_mod._cwd_is_code(effective):
            code_paths.append(("WorkingDirectory", working))
        for env_file in effective.env_files:
            code_paths.append(("EnvironmentFile", env_file))

        pinned_prefix = f"{pinned_root}/"
        unit_findings = []
        for kind, path in code_paths:
            if not path.startswith("/"):
                continue
            if path.startswith(AGENT_ROOTS):
                unit_findings.append({"unit": view.name, "kind": kind, "path": path,
                                      "reason": "путь к коду на территории агента"})
                continue
            if path.startswith(pinned_prefix):
                # Каталога ещё нет; его создаёт и делает root-owned установщик,
                # а подтверждает пост-аудит. Принимается по построению.
                continue
            # Всё остальное существует уже сейчас — спрашиваем файловую систему,
            # а не собственные представления о том, что «системное».
            for problem in audit_mod._check_path(view.name, path, kind=kind):
                unit_findings.append({"unit": view.name, "kind": kind,
                                      "path": problem.path, "reason": problem.reason})
        findings.extend(unit_findings)
        rows.append({
            "unit": view.name,
            "pinned": pin is not None,
            "credential_access": view.holds_credentials,
            "code_paths": [f"{k}={p}" for k, p in code_paths],
            "clean": not unit_findings,
        })

    return {
        "release_id": release_id,
        "root_units": len(rows),
        "pinned_units": sum(1 for r in rows if r["pinned"]),
        "finding_count": len(findings),
        "findings": findings,
        "global_clean": not findings,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="simulate_post_transaction",
        description="Состояние границы root после транзакции, посчитанное заранее.")
    parser.add_argument("--manifest", default=str(HERE / "manifest.json"))
    parser.add_argument("--release", default=str(HERE / "release" / "release.json"))
    parser.add_argument("--unit-dir", default=str(audit_mod.UNIT_DIR))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    release_id = json.loads(Path(args.release).read_text(encoding="utf-8"))["release_id"]
    report = simulate(manifest, release_id, Path(args.unit_dir))

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"root-юнитов:      {report['root_units']}")
        print(f"закрепляется:     {report['pinned_units']}")
        if report["global_clean"]:
            print("ГЛОБАЛЬНО ЧИСТО: после транзакции ни один root-юнит не берёт код "
                  "с территории агента")
        else:
            print(f"ОСТАНЕТСЯ НАРУШЕНИЙ: {report['finding_count']}")
            for item in report["findings"]:
                print(f"  {item['unit']}: {item['kind']}={item['path']} — {item['reason']}")
    return 0 if report["global_clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
