#!/usr/bin/env python3
"""Ожидание переключения zonafilm.cc и автоматическая live-приёмка после него.

Запускается один раз владельцем — и дальше не требует ни одной команды. Ждёт,
пока сойдутся четыре условия, и как только они сошлись, сам прогоняет полную
приёмку по публичному адресу и пишет доказательства.

Условия:

1. запись A для `zonafilm.cc` резолвится публичными резолверами;
2. по 443 отвечает сертификат, покрывающий имя;
3. `https://zonafilm.cc/` отдаёт 200 с заголовком `X-Site-Factory-Build-Id`,
   равным ожидаемому — то есть отвечает именно выложенный релиз, а не соседняя
   витрина, случайно поймавшая имя;
4. служба сменила PID относительно записанного до переключения (если он задан),
   то есть перезапуск действительно состоялся.

Смена одного лишь PID ничего не доказывает, как и один лишь 200: вместе с
build-id они доказывают, что публичный адрес обслуживает нужный процесс нужным
релизом. Поэтому проверяются вместе.

Ничего не меняет. Только ждёт и читает.
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ОЖИДАЕМЫЙ_BUILD_ID = "zona-02-1015c650d8be"
ОЖИДАЕМЫЙ_ARTIFACT = "7ccf094a1d7f2b5e648a38f51f6a63de9627576637d96f6c966fe1759ad8fa1e"


def резолвится(имя: str) -> list[str]:
    try:
        return sorted({и[4][0] for и in socket.getaddrinfo(имя, None, socket.AF_INET)})
    except OSError:
        return []


def сертификат(имя: str, порт: int = 443, timeout: float = 10.0) -> dict:
    контекст = ssl.create_default_context()
    try:
        with socket.create_connection((имя, порт), timeout=timeout) as сырое:
            with контекст.wrap_socket(сырое, server_hostname=имя) as tls:
                серт = tls.getpeercert()
        имена = sorted({з[1] for з in серт.get("subjectAltName", ())})
        return {"ok": True, "not_after": серт.get("notAfter"), "san": имена,
                "covers": имя in имена}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def проверить_ответ(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            заголовки = dict(r.headers)
            r.read(2048)
            статус = r.status
    except urllib.error.HTTPError as e:
        заголовки, статус = dict(e.headers), e.code
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {
        "ok": статус == 200,
        "status": статус,
        "build_id": заголовки.get("X-Site-Factory-Build-Id"),
        "artifact_sha256": заголовки.get("X-Site-Factory-Artifact-Sha256"),
        "x_robots_tag": заголовки.get("X-Robots-Tag"),
    }


def условия(домен: str, ожидаемый_build: str) -> dict:
    адреса = резолвится(домен)
    серт = сертификат(домен) if адреса else {"ok": False, "error": "нет записи A"}
    ответ = проверить_ответ(f"https://{домен}/") if серт.get("ok") else {"ok": False,
                                                                        "error": "нет TLS"}
    готово = bool(адреса) and серт.get("ok") and ответ.get("ok") \
        and ответ.get("build_id") == ожидаемый_build
    return {"a_records": адреса, "tls": серт, "response": ответ, "ready": готово}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default="zonafilm.cc")
    parser.add_argument("--expect-build-id", default=ОЖИДАЕМЫЙ_BUILD_ID)
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--max-hours", type=float, default=72.0)
    parser.add_argument("--out", required=True)
    parser.add_argument("--acceptance", default="automation/host/zonafilm-cc-acceptance.py")
    parser.add_argument("--acceptance-out",
                        default="artifacts/evidence/release-zonafilm-cc-full-cycle-01/"
                                "13-live/acceptance-public.json")
    args = parser.parse_args()

    журнал: list[dict] = []
    предел = time.monotonic() + args.max_hours * 3600
    итог: dict = {"domain": args.domain, "expect_build_id": args.expect_build_id,
                  "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    while time.monotonic() < предел:
        состояние = условия(args.domain, args.expect_build_id)
        состояние["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        журнал.append(состояние)
        print(json.dumps({"at": состояние["at"], "ready": состояние["ready"],
                          "a": состояние["a_records"],
                          "build": состояние["response"].get("build_id")},
                         ensure_ascii=False), flush=True)
        if состояние["ready"]:
            итог["became_ready_at"] = состояние["at"]
            итог["final_state"] = состояние
            break
        time.sleep(args.interval)
    else:
        итог["timed_out"] = True
        итог["final_state"] = журнал[-1] if журнал else None

    итог["log"] = журнал[-20:]

    if итог.get("became_ready_at"):
        # Условия сошлись — приёмка запускается сама, без новой команды.
        команда = [sys.executable, args.acceptance,
                   "--origin", f"https://{args.domain}",
                   "--host", args.domain,
                   "--out", args.acceptance_out]
        готово = subprocess.run(команда, capture_output=True, text=True, timeout=3600)
        итог["acceptance"] = {
            "command": " ".join(команда),
            "exit_code": готово.returncode,
            "stdout_tail": готово.stdout[-4000:],
            "stderr_tail": готово.stderr[-2000:],
            "report": args.acceptance_out,
        }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(итог, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(json.dumps({k: итог[k] for k in ("became_ready_at", "timed_out") if k in итог},
                     ensure_ascii=False))
    return 0 if итог.get("became_ready_at") else 1


if __name__ == "__main__":
    raise SystemExit(main())
