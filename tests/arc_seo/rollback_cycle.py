#!/usr/bin/env python3
"""Настоящий цикл отката поставки контракта на кандидатском рантайме.

до изменения → кандидат → проверка → откат → проверка → возврат вперёд →
повторная проверка.

Откат выполняется, а не объявляется: на каждом шаге поднимается экземпляр,
обслуживающий соответствующий набор, и у него спрашивают, существует ли
новый вид ресурса. Production не участвует.
"""
from __future__ import annotations

import ctypes, hashlib, json, os, signal, subprocess, sys, tempfile, time
import urllib.error, urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ВЫПУСК = Path(os.environ.get("ARC003_RELEASE",
                             "/srv/site-factory/control-api/current")).resolve()
ПОРТ = int(os.environ.get("ARC003_ROLLBACK_PORT", "8797"))
PR_SET_PDEATHSIG = 1


def _умереть_с_родителем() -> None:
    try:
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(
            PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0)
    except OSError:
        pass


def отпечаток(версия: str) -> str:
    п = КОРЕНЬ / "contracts/control-plane" / версия / "checksums.json"
    суммы = json.loads(п.read_text(encoding="utf-8"))["files"]
    return hashlib.sha256(json.dumps(суммы, sort_keys=True).encode()).hexdigest()


def наблюдать(версия: str, врем: Path) -> dict:
    """Поднять экземпляр на указанном наборе и спросить, что он объявляет."""
    окр = dict(os.environ, SITE_ENGINE_HTTP="1", SITE_ENGINE_API_ENABLED="1",
               SITE_ENGINE_CONTROL_WRITES="0",
               CONTROL_PLANE_BUNDLE_DIR=str(
                   КОРЕНЬ / "contracts/control-plane" / версия),
               PYTHONPATH=str(ВЫПУСК))
    лог = (врем / f"server-{версия}.log").open("w")
    сервер = subprocess.Popen(
        [str(ВЫПУСК / ".venv/bin/python"), "-m",
         "factory.site_engine.api.server", "--root", "/srv/site-factory/repo",
         "--host", "127.0.0.1", "--port", str(ПОРТ)],
        cwd=ВЫПУСК, env=окр, preexec_fn=_умереть_с_родителем,
        stdout=лог, stderr=subprocess.STDOUT)
    try:
        каталог = None
        for _ in range(80):
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{ПОРТ}/api/v1/capabilities",
                        timeout=5) as о:
                    каталог = json.loads(о.read())
                    if каталог.get("bundle_version") == версия:
                        break
            except (urllib.error.HTTPError, urllib.error.URLError, OSError):
                pass
            time.sleep(0.5)
        else:
            return {"version": версия, "up": False}
        имена = {c.get("capability_id") or c.get("id"): c.get("status")
                 for c in каталог["capabilities"]}
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{ПОРТ}"
                    "/api/v1/contracts/schemas/SeoContentProposal.v1",
                    timeout=5) as о:
                схема_есть = о.status == 200
        except urllib.error.HTTPError as e:
            схема_есть = e.code == 200
        with urllib.request.urlopen(
                f"http://127.0.0.1:{ПОРТ}/api/v1/control-plane/version",
                timeout=5) as о:
            версия_ответа = json.loads(о.read())["control_plane_version"]
        return {
            "version": версия, "up": True,
            "served_version": версия_ответа,
            "bundle_sha256": отпечаток(версия),
            "seo_content_proposal": имена.get("seo.content.proposal"),
            "changeset_adapter_seo": имена.get("changeset.adapter.seo"),
            "schema_served": схема_есть,
            "capabilities": каталог["count"],
        }
    finally:
        сервер.terminate()
        try:
            сервер.wait(timeout=20)
        except subprocess.TimeoutExpired:
            сервер.kill(); сервер.wait(timeout=10)
        лог.close()


def main() -> int:
    врем = Path(tempfile.mkdtemp(prefix="arc003-rollback-"))
    шаги = []
    for подпись, версия in (("до изменения", "1.3.1"),
                            ("кандидат", "1.3.2"),
                            ("откат", "1.3.1"),
                            ("возврат вперёд", "1.3.2")):
        н = наблюдать(версия, врем)
        н["step"] = подпись
        шаги.append(н)
        print(f"  {подпись:16} набор {версия}: отдаёт {н.get('served_version')}, "
              f"seo.content.proposal={н.get('seo_content_proposal')}, "
              f"adapter.seo={н.get('changeset_adapter_seo')}, "
              f"схема={'есть' if н.get('schema_served') else 'нет'}")

    до, кандидат, откат, вперёд = шаги
    ок = (до["seo_content_proposal"] is None
          and до["changeset_adapter_seo"] == "PLANNED"
          and not до["schema_served"]
          and кандидат["seo_content_proposal"] == "AVAILABLE"
          and кандидат["changeset_adapter_seo"] == "AVAILABLE"
          and кандидат["schema_served"]
          and откат["seo_content_proposal"] is None
          and откат["changeset_adapter_seo"] == "PLANNED"
          and not откат["schema_served"]
          and вперёд["seo_content_proposal"] == "AVAILABLE"
          and вперёд["bundle_sha256"] == кандидат["bundle_sha256"])
    отчёт = {"cycle": шаги, "rollback_executed": True,
             "restore_forward_executed": True,
             "verdict": "PASS" if ок else "FAIL",
             "note": ("Откат и возврат вперёд выполнены на кандидатском "
                      "рантайме. Production не затрагивался: обслуживаемый "
                      "каталог и работающая служба не менялись.")}
    цель = КОРЕНЬ / "artifacts/fleet-arc-003/rollback-restore-forward.json"
    цель.parent.mkdir(parents=True, exist_ok=True)
    цель.write_text(json.dumps(отчёт, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print(f"\n  вердикт цикла: {отчёт['verdict']}")
    print(f"  отпечаток кандидата совпал после возврата: "
          f"{вперёд['bundle_sha256'] == кандидат['bundle_sha256']}")
    return 0 if ок else 1


if __name__ == "__main__":
    sys.exit(main())
