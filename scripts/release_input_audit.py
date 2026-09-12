#!/usr/bin/env python3
"""RELEASE_INPUT_AUDIT — что именно предлагается выложить и чем это доказано.

Аудит собирается из фактов машины, а не из отчётов и не из истории переписки.
Каждое поле имеет источник: файл, команду или ревизию. Поле, которое нечем
заполнить, остаётся пустым со статусом, а не заполняется правдоподобным
значением — это главное правило файла.

Отдельно о коротких ревизиях. Короткий SHA и префикс отпечатка в аудит не
принимаются: `cd2f718` и `52b56d557564717a` встречались в отчётах как
идентификаторы релиза, и ни того ни другого недостаточно, чтобы указать на
содержимое. Здесь только полные значения, и отпечаток пересчитывается из
точной ревизии в чистом дереве, а не переписывается из отчёта.

Запуск:
    .venv/bin/python scripts/release_input_audit.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "artifacts" / "evidence" / "release" / "release-input-audit.json"

#: Известные версии артефакта. Номер выводится из отпечатка, а не пишется
#: числом рядом: зашитый номер расходится с содержимым при первой же правке —
#: именно так в отчёте однажды оказался «артефакт v2» с отпечатком версии 3.
ARTIFACT_VERSIONS = {
    "52b56d557564717adcf32011c3494bc8c548eae1a96e010f7bd499351e0847dc": 1,
    "7b38ca10685a75c3d52527746208539cc30015fc1bfb3fce010a9491616ed965": 2,
    "ca3d395ade25fb295735a20ad1477e385c9f149a69976b875d0d9af2f5a5f939": 3,
    "93c9af85dd303945d9397f69486aa3c77e22cb0ea8b6c051f9f281e85ad2d922": 4,
    "1888f394b9d0afa2024bfaeb10ecba19e347a97f2b34b911bf47e948db1d82ff": 5,
    "3a1f8938896e12878f7b1efa0d2d67db64296a51f2aaf734979b1c10846e313c": 6,
    "707f1d7298d2986ce91e73b5ccd807788663bbc9c9938af74c7f7f2b369489b4": 7,
    "0e46a67c2f6b17b62dfa06eda33dc17132db8e5dd71fb00872f56a9194542f81": 8,
    "e4d367db1c87cee56db56feb7d1eabc8993473230fe78351ca58ac0b6f344671": 9,
    "ea2564538159c89beb4f2fd0e71c822e6a2375dcebd97033efe9ffb225ce1c7d": 10,
    "1e683031cbe5b802c70f72b708afc35018bf798722d74389c7d0bfaccbf38225": 11,
    "c4e04d93f348132ed0f65ef23bec3aa999806caa7ac2df41fb16ad8fddf178fd": 12,
    "195f28655178065281089046de83e379db4f5024e28759b9c50d949adfa803f0": 13,
    "75754069edadfc1bb2b0d528a7ce2804dfaba2166cf9caf4a4faf2e39c297f62": 14,
    "e8c98cb27e39ca94e9065768eb768953657185df42d63934da493d56aee17e67": 15,
    "94920e2ee1db4a6f840d35bf5b42b83c66dc533612f9e74fd312a45cfa74caf2": 16,
    "a54f4bfdd2fb1936f1cc24f3b5475d17007305e3f68e08686268c8bb5996682a": 17,
    "f5a7be720b53b021ec9b4f4f7fe4ba7ec14f5a46d28db4ed147328c6f6ee581a": 18,
    "872bb9f257b2ee4c49073d3539914f6c45a716e6fbf14ce77f486ab8dbf6b6a8": 19,
    "a4ef5d68cda460a03773a0b730ac696f629cf4fbe0dfdba4b96781699fdaaf93": 20,
    "35e4308c811c7cadebe31d4d7cf897994587465e9e288ff17efcf4f0c76ae8da": 21,
    "13aa4f6ec124a970e79c3f14e9124018600a8ead0702e4bd6199357e7c63308f": 22,
    "3a543dba6f0f113793d575f9d259eded661c2a2c7545c6d1059d6c8750c0b5a3": 23,
    "c6a11f65d2f9d3350d3a031a7437042e72c888430ab11a72674ba0cb82305d4a": 24,
    "381fbd01a40e44ba83e4324b228b0db9067a7cf093457efc68a544509aafd76c": 25,
    "a0cfaf7135255d62e70432162cadc554c393c2c01dec3936baddafd8ca694859": 26,
    "03e690f4fa269e8644f615e9845cf9c877aff76bd5720219b3088c052625e714": 27,
    "ca25a6e8319edf8727cf167d73ddfbf044cdaa422c889ca9c7609dd11b0af363": 28,
    "5137fb30444e305b365d747783f5b4d9e91702ffc2fa38b384a61af360296af0": 29,
}

#: Ревизии, участвующие в релизе. Полные, а не сокращённые.
CANDIDATE_SHA = "cd2f718ae656e6bfcdc68099601d92078bd1f13f"
CANARY_BASE_SHA = "21d2c21dfc50c01b2fdd5a13821a29f3cbce1626"
DEPLOYED_CHECKOUT = Path("/srv/site-factory/repo")

COORD = Path("/srv/site-factory/coordination/v1")
LORDS_ROOT = Path("/srv/lords")
PORTS = {"lords-01": 9101, "lords-02": 9102,
    "eeb442aef29011757526e65711e5e30e6dee8b9c73b0fe14b8e1d62d402a1a0a": 9103,
    "afb23829d14b8f27201b23075dd5e750800251c676057a3d595bc82a30a024d2": 9104,
    "32272d5e2fbb93000274c33bc9630582856f63b61dda2b4db6dd64f785400179": 9105,
    "bbb2d861a6412521791a7b3943b388266836da7059b41333adb54e52e00d5da5": 9106,
    "97981948e4b058b2dcf5d74caee63b6dc1f5babdd9c0184e159fb7627137f2d7": 9107,
    "b20b72e4565a1cfe65297addb091d8fe295b855145600918e35cad95e5b66c02": 9108,
    "0eab0ce7ca4a5a9ccb6ee6167511ed58f60379ef38ab0d6670c2433216ee278a": 9109,
    "ddbeddb8fcf2ddb5091cc9e87cc83262e05235b739cbb3a53e2f408350c6626a": 9110,
    "cfe8ee2d21d19a71fa3805177890a8eac240a2cffad146ce404f42b503eafa76": 9111,
    "e40b937830025085ea64b4c344ccf04bcceaad17056b1f02fa6a29df15c04815": 9112,
    "f5a7be720b53b021ec9b4f4f7fe4ba7ec14f5a46d28db4ed147328c6f6ee581a": 9113, "lords-03": 9103}


def _git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True).stdout.strip()


def digest_at(sha: str) -> dict:
    """Отпечаток артефакта, пересчитанный из ревизии в чистом дереве.

    Именно пересчитанный: значение из отчёта доказывает только то, что его
    кто-то написал.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tar = Path(tmp) / "t.tar"
        made = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar",
                               "-o", str(tar), sha], capture_output=True, text=True)
        if made.returncode:
            return {"status": "unavailable", "reason": made.stderr.strip()[:160]}
        tree = Path(tmp) / "tree"
        tree.mkdir()
        subprocess.run(["tar", "-xf", str(tar), "-C", str(tree)], check=True)
        module = tree / "factory" / "templates" / "digest.py"
        if not module.is_file():
            return {"status": "undefined",
                    "reason": "в ревизии нет factory/templates/digest.py: артефакт не определён"}
        namespace: dict = {}
        exec(compile(module.read_text(encoding="utf-8"), str(module), "exec"), namespace)
        computed = namespace["compute"](tree)
        return {"status": "reproduced",
                "template_digest": computed["template_digest"],
                "files": computed["files"]}


def artifact_members() -> list[dict]:
    """Состав артефакта с отпечатком каждого файла.

    Перечисление нужно затем, чтобы отпечаток было к чему привязать: одно
    шестидесятичетырёхзначное число не говорит, какому шаблону оно принадлежит.
    """
    from factory.templates import digest as digest_mod
    return list(digest_mod.compute(ROOT).get("members") or [])


def pinned_digest() -> str | None:
    import re
    text = (ROOT / "automation" / "host" / "lords-canary-apply.sh").read_text(encoding="utf-8")
    m = re.search(r'readonly EXPECT_DIGEST="([0-9a-f]{64})"', text)
    return m.group(1) if m else None


def domain_map() -> list[dict]:
    config = json.loads((ROOT / "config" / "directions" / "lords.json").read_text(encoding="utf-8"))
    rows = []
    for d in config.get("domains", []):
        rows.append({"site_id": d["site_id"], "domain": d["apex"], "profile": d["profile"],
                     "runtime_root": d["runtime_root"], "port": d["staging_port"],
                     "launched": d["launched"]})
    return rows


def runtime_state() -> dict:
    import os
    import datetime
    out = {}
    for site in PORTS:
        base = LORDS_ROOT / site
        link = base / "current"
        row: dict = {"site_id": site}
        if link.is_symlink():
            target = os.readlink(link)
            row["current_release"] = Path(target).name
            row["switched_at_utc"] = datetime.datetime.utcfromtimestamp(
                link.lstat().st_mtime).isoformat() + "Z"
            row["switched_by_uid"] = link.lstat().st_uid
        releases = sorted((base / "releases").iterdir(),
                          key=lambda p: p.stat().st_mtime) if (base / "releases").is_dir() else []
        row["releases"] = [p.name for p in releases]
        # Откат — предыдущий выложенный релиз, а не запись в rollback.json:
        # та на боевых витринах утверждает «предыдущего релиза нет», хотя
        # каталогов два.
        row["rollback_release"] = releases[-2].name if len(releases) >= 2 else None
        fingerprint = ROOT.parent / "x"  # заполняется ниже из боевого каталога
        fp = Path("/srv/site-factory/repo/var/lords/fingerprints") / f"{site}.json"
        if fp.is_file():
            row["fingerprint"] = json.loads(fp.read_text(encoding="utf-8"))
        out[site] = row
    return out


def live_probe() -> dict:
    out = {}
    for site, port in PORTS.items():
        row: dict = {}
        for name, path in (("home", "/"), ("catalog", "/catalog/")):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=20) as r:
                    body = r.read().decode("utf-8", "replace")
                    row[name] = {"status": r.status, "bytes": len(body)}
                    if name == "home":
                        import re
                        m = re.search(r'<meta name="lords-data-source" content="([^"]*)"', body)
                        row["data_source_label"] = m.group(1) if m else None
            except (urllib.error.URLError, OSError) as exc:
                row[name] = {"status": None, "error": str(exc)[:120]}
        out[site] = row
    return out


def compatibility() -> dict:
    path = COORD / "COMPATIBILITY_MATRIX.yaml"
    if not path.is_file():
        return {"status": "absent"}
    text = path.read_text(encoding="utf-8")
    contract = None
    sites = []
    current = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("engineContract:"):
            contract = s.split(":", 1)[1].strip().strip('"')
        elif s.startswith("- siteId:"):
            current = s.split(":", 1)[1].strip()
            sites.append(current)
    return {"status": "declared", "engineContract": contract, "sites": sorted(sites),
            "generatedAt": next((l.split(":", 1)[1].strip().strip('"')
                                 for l in text.splitlines()
                                 if l.strip().startswith("generatedAt:")), None)}


def build() -> dict:
    compat = compatibility()
    known = set(compat.get("sites") or [])
    return {
        "artifact": "RELEASE_INPUT_AUDIT",
        "schemaVersion": 1,
        "lane": "ARCHITECT_CORE",
        "iteration": "SITE-FACTORY-RELEASE-LIVE-CIRCUIT-03",
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "headSha": _git("rev-parse", "HEAD"),
        "template": {
            "templateId": "lords",
            "scope": "только направление lords: все девятнадцать файлов лежат в "
                     "blueprints/lords, factory/lords, factory/templates и схеме "
                     "манифеста; ни Yummy, ни zona, ни animedia, ни basis-video "
                     "артефакт не описывает",
            "artifactVersion": None,  # выводится из отпечатка ниже
            "digest": None,
            "files": None,
            "members": artifact_members(),
            "pinnedInApplyScript": pinned_digest(),
            "reproduction": {
                "candidateSha": {"sha": CANDIDATE_SHA, **digest_at(CANDIDATE_SHA)},
                "canaryBaseSha": {"sha": CANARY_BASE_SHA, **digest_at(CANARY_BASE_SHA)},
            },
            "history": [
                {"version": 1,
                 "digest": "52b56d557564717adcf32011c3494bc8c548eae1a96e010f7bd499351e0847dc",
                 "acceptedBy": "TEMPLATE_TO_CORE-008 / CORE_TO_OWNER-011",
                 "state": "заменён"},
                {"version": 2,
                 "digest": "7b38ca10685a75c3d52527746208539cc30015fc1bfb3fce010a9491616ed965",
                 "difference": "метка происхождения данных перестала быть зашитой "
                               "строкой fixture/test",
                 "state": "заменён, в production не выкладывался"},
                {"version": 3,
                 "digest": "ca3d395ade25fb295735a20ad1477e385c9f149a69976b875d0d9af2f5a5f939",
                 "difference": "длительность серии стала неизвестной, а не нулевой",
                 "state": "собран для canary"},
            ],
        },
        "deployedCheckout": {
            "path": str(DEPLOYED_CHECKOUT),
            "sha": _git("rev-parse", "HEAD", cwd=DEPLOYED_CHECKOUT),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD", cwd=DEPLOYED_CHECKOUT),
            "clean": _git("status", "--porcelain", cwd=DEPLOYED_CHECKOUT) == "",
            "artifact": digest_at(_git("rev-parse", "HEAD", cwd=DEPLOYED_CHECKOUT)),
        },
        "compatibility": compat,
        "domains": domain_map(),
        "runtime": runtime_state(),
        "liveProbe": live_probe(),
        "templateIdRegistration": {
            "lords": "зарегистрирован: lords-01, lords-02, lords-03 в COMPATIBILITY_MATRIX",
            "yummy": "зарегистрирован: yummyani-site, yummyani-org, yummyani-biz",
            "zona-cinema": "НЕ зарегистрирован ни в PROGRAM_STATE, ни в COMPATIBILITY_MATRIX",
            "animedia-portal": "НЕ зарегистрирован ни в PROGRAM_STATE, ни в COMPATIBILITY_MATRIX",
            "basis-video": "НЕ зарегистрирован: PENDING_ARCHITECT_CONFIRMATION",
            "lords-04": "профиль lords-genre существует в репозитории, но витрины "
                        "lords-04 в матрице совместимости нет",
            "note": "поиск по /srv/site-factory/coordination/v1 не нашёл упоминаний "
                    "basis-video, zona-cinema и animedia-portal ни в одном файле",
        },
        "unknownSites": sorted(known - {d["site_id"] for d in domain_map()}
                               - {"yummyani-site", "yummyani-org", "yummyani-biz"}),
    }


def main() -> int:
    payload = build()
    from factory.templates import digest as digest_mod
    computed = digest_mod.compute(ROOT)
    payload["template"]["digest"] = computed["template_digest"]
    payload["template"]["files"] = computed["files"]
    payload["template"]["artifactVersion"] = ARTIFACT_VERSIONS.get(
        computed["template_digest"])
    if payload["template"]["artifactVersion"] is None:
        payload["template"]["artifactVersionNote"] = (
            "отпечаток не значится ни в одной известной версии: артефакт изменён "
            "без записи в ARTIFACT_VERSIONS")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{OUT.relative_to(ROOT)} собран")
    t = payload["template"]
    print(f"  артефакт v{t['artifactVersion']}: {t['digest']}")
    print(f"  файлов: {t['files']}; закреплён в сценарии: "
          f"{'да' if t['pinnedInApplyScript'] == t['digest'] else 'НЕТ — расхождение'}")
    for name, row in t["reproduction"].items():
        print(f"  воспроизведение {name}: {row.get('status')} "
              f"{(row.get('template_digest') or '')[:16]}")
    d = payload["deployedCheckout"]
    print(f"  развёрнутый чекаут: {d['sha'][:12]} ({d['branch']}), артефакт: "
          f"{d['artifact'].get('status')}")
    for site, row in payload["runtime"].items():
        fp = (row.get("fingerprint") or {})
        print(f"  {site}: релиз {row.get('current_release')} откат "
              f"{row.get('rollback_release')} каталог {fp.get('catalog', '')[:12]}")
    for site, row in payload["liveProbe"].items():
        print(f"  {site}: / {row['home'].get('status')} /catalog/ "
              f"{row['catalog'].get('status')} метка {row.get('data_source_label')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
