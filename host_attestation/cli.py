"""`bin/host-attest` — единственный способ выпустить свидетельство о флоте.

Запускается только явно и только там, где флот живёт. Два условия допуска,
и оба обязаны выполниться:

* хост объявлен control host — переменной `HOST_ATTESTATION_CONTROL_HOST=1`
  или флагом `--control-host`. Объявление явное потому, что «похоже на боевой
  хост» — не то основание, по которому выпускают доказательство;
* корень флота существует и читается.

Без допуска команда не притворяется успешной: она выпускает свидетельство с
вердиктом BLOCKED и завершается ненулевым кодом. Такое свидетельство ворота
релиза не пропустят — и это правильный исход, потому что измерения не было.

Коды возврата: 0 — PASS, 1 — FAIL, 2 — BLOCKED, 3 — неверный вызов.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

from factory.site_engine.attestation import contract as C

from . import checks

КОДЫ = {"PASS": 0, "FAIL": 1, "BLOCKED": 2}


def текущий_sha(корень: Path) -> str | None:
    п = subprocess.run(
        ["git", "-C", str(корень), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30
    )
    значение = п.stdout.strip()
    return значение if п.returncode == 0 and len(значение) == 40 else None


def это_control_host(аргументы: argparse.Namespace) -> bool:
    if аргументы.control_host:
        return True
    return os.environ.get("HOST_ATTESTATION_CONTROL_HOST", "").strip() == "1"


def построить_разбор() -> argparse.ArgumentParser:
    р = argparse.ArgumentParser(
        prog="host-attest", description="Измерить живой флот и выпустить свидетельство для релиза."
    )
    р.add_argument(
        "--candidate-sha",
        help="SHA дерева, для которого снимается свидетельство. "
        "По умолчанию — HEAD рабочего дерева.",
    )
    р.add_argument(
        "--control-host",
        action="store_true",
        help="Объявить этот хост control host. То же делает " "HOST_ATTESTATION_CONTROL_HOST=1.",
    )
    р.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Куда положить свидетельство " "(по умолчанию artifacts/host-attestation).",
    )
    р.add_argument(
        "--print", dest="печатать", action="store_true", help="Вывести свидетельство в stdout."
    )
    return р


def main(argv: list[str] | None = None) -> int:
    аргументы = построить_разбор().parse_args(argv)
    корень = C.КОРЕНЬ

    sha = аргументы.candidate_sha or текущий_sha(корень)
    if not sha or len(sha) != 40 or any(с not in "0123456789abcdef" for с in sha):
        print("candidate SHA не определён: передай --candidate-sha <40 hex>", file=sys.stderr)
        return 3

    допущен = это_control_host(аргументы)
    корень_флота = checks.корень_флота()
    доступен = корень_флота.is_dir() and os.access(корень_флота, os.R_OK)

    if допущен and доступен:
        результаты = checks.выполнить_все()
    else:
        причина = (
            "хост не объявлен control host: ни --control-host, "
            "ни HOST_ATTESTATION_CONTROL_HOST=1"
            if not допущен
            else f"корень флота {корень_флота} недоступен для чтения"
        )
        # Ни одна проверка не выполнялась — и каждая объявленная это скажет.
        # Свидетельство остаётся полным по составу и честным по содержанию.
        результаты = [
            C.Результат(
                check_id=cid,
                status="BLOCKED",
                detail=f"измерение не выполнялось: {причина}",
                measured_at=C.сейчас(),
            )
            for cid, _ in checks.ВСЕ
        ]

    свидетельство = C.собрать(
        candidate_sha=sha,
        hostname=socket.gethostname(),
        control_host=допущен and доступен,
        evidence_root=str(корень_флота),
        результаты=результаты,
    )

    путь = C.записать(свидетельство, каталог=аргументы.output_dir)
    вердикт = свидетельство["verdict"]

    if аргументы.печатать:
        print(json.dumps(свидетельство, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"{вердикт}: {путь}")
        for проверка in свидетельство["checks"]:
            if проверка["status"] != "PASS":
                print(f"  {проверка['status']:<7} {проверка['check_id']}: " f"{проверка['detail']}")
    return КОДЫ[вердикт]


if __name__ == "__main__":  # pragma: no cover - точка входа
    raise SystemExit(main())
