#!/usr/bin/env python3
"""Проверка честности форка: рендер изолированного рантайма Animedia против прежнего.

Изоляция обязана быть переносом, а не переписыванием. Поэтому обе версии
поднимаются на служебных портах с ОДНИМ манифестом, снимком каталога и
подробностями, и HTML каждого маршрута сравнивается побайтно. Расхождение
допускается только там, где оно объявлено намеренно, и тогда печатается
построчный дифф, а не «в целом совпало».

Мутаций нет: оба процесса слушают localhost и по завершении снимаются.

    .venv/bin/python automation/host/animedia_render_equivalence.py \\
        --out artifacts/evidence/animedia-original-parity-01/01-isolation
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
РАНТАЙМ = Path(os.environ.get("ANIMEDIA_RUNTIME_ROOT", "/srv/lords/.frontend"))
ПРЕЖНИЙ = КОРЕНЬ / "automation/host/lords-frontend.py"
НОВЫЙ = КОРЕНЬ / "automation/host/animedia-frontend.py"

МАРШРУТЫ = (
    "/", "/catalog/", "/catalog/?page=2", "/new/", "/collections/",
    "/collection/recently_added/", "/search/?q=%D0%B0%D0%BD%D0%B8%D0%BC%D0%B5",
    "/search/?q=%D1%8A%D1%8B%D1%8C%D1%89", "/schedule/",
    "/title/nelyud-film-2-stolknovenie/",
    "/title/master-lda-i-plameni-2/season-2/episode-104/",
    "/genre/action/", "/year/2024/", "/definitely-absent-route-xyz/",
    "/__template_version",
)


def свободный_порт() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def поднять(файл: Path, лог: Path) -> tuple[subprocess.Popen, int]:
    порт = свободный_порт()
    окр = dict(os.environ)
    окр.update({
        "LORDS_TEMPLATE_MANIFEST": str(РАНТАЙМ / "template-manifest-animedia-01.json"),
        "LORDS_CATALOG": str(РАНТАЙМ / "animedia-01-catalog.json"),
        "LORDS_LEGACY_ROOT": "/srv/lords/animedia-01/current/site",
        "LORDS_SITE_NAME": "Animedia",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    ф = лог.open("w", encoding="utf-8")
    p = subprocess.Popen(["/usr/bin/python3", str(файл), "--port", str(порт)],
                         stdout=ф, stderr=subprocess.STDOUT, env=окр, cwd=str(КОРЕНЬ))
    for _ in range(600):
        time.sleep(0.5)
        if p.poll() is not None:
            raise SystemExit(f"{файл.name} не поднялся, см. {лог}")
        try:
            with socket.create_connection(("127.0.0.1", порт), timeout=0.5):
                return p, порт
        except OSError:
            continue
    raise SystemExit(f"{файл.name}: порт не открылся")


def получить(порт: int, путь: str) -> tuple[int, bytes]:
    зпр = urllib.request.Request(f"http://127.0.0.1:{порт}{путь}",
                                 headers={"Host": "animedia.icu"})
    try:
        with urllib.request.urlopen(зпр, timeout=60) as о:
            return о.status, о.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--out", required=True)
    a = р.parse_args()
    вывод = Path(a.out)
    вывод.mkdir(parents=True, exist_ok=True)

    старый_p, старый_порт = поднять(ПРЕЖНИЙ, вывод / "equiv-previous.log")
    новый_p, новый_порт = поднять(НОВЫЙ, вывод / "equiv-isolated.log")
    итог = {"task": "ANIMEDIA-RENDER-EQUIVALENCE", "tenant": "animedia",
            "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "previous_runtime": str(ПРЕЖНИЙ.relative_to(КОРЕНЬ)),
            "isolated_runtime": str(НОВЫЙ.relative_to(КОРЕНЬ)),
            "previous_sha256": hashlib.sha256(ПРЕЖНИЙ.read_bytes()).hexdigest(),
            "isolated_sha256": hashlib.sha256(НОВЫЙ.read_bytes()).hexdigest(),
            "routes": []}
    try:
        for путь in МАРШРУТЫ:
            к1, т1 = получить(старый_порт, путь)
            к2, т2 = получить(новый_порт, путь)
            равно = т1 == т2
            запись = {"path": путь, "http_previous": к1, "http_isolated": к2,
                      "bytes_previous": len(т1), "bytes_isolated": len(т2),
                      "sha_previous": hashlib.sha256(т1).hexdigest()[:16],
                      "sha_isolated": hashlib.sha256(т2).hexdigest()[:16],
                      "identical": равно, "code_match": к1 == к2}
            if not равно:
                d = list(difflib.unified_diff(
                    т1.decode("utf-8", "replace").splitlines(),
                    т2.decode("utf-8", "replace").splitlines(),
                    "previous", "isolated", lineterm="", n=1))
                запись["diff_lines"] = len(d)
                запись["diff_sample"] = d[:40]
            итог["routes"].append(запись)
            print(f"  {путь:<52} {к1}/{к2} "
                  f"{'идентично' if равно else f'РАСХОЖДЕНИЕ {len(т1)}→{len(т2)} байт'}",
                  flush=True)
    finally:
        for p in (старый_p, новый_p):
            p.terminate()
            try:
                p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                p.kill()
    итог["all_identical"] = all(r["identical"] for r in итог["routes"])
    итог["all_codes_match"] = all(r["code_match"] for r in итог["routes"])
    (вывод / "RENDER_EQUIVALENCE.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
    print("маршрутов:", len(итог["routes"]),
          "| идентичны все:", итог["all_identical"],
          "| коды совпадают:", итог["all_codes_match"])
    return 0 if итог["all_identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
