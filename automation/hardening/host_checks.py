#!/usr/bin/env python3
"""Проверки хоста до и после транзакции, и сравнение с исходным состоянием.

Зачем отдельный модуль, а не набор строк в установщике: baseline снимается ДО
изменений, проверки идут ПОСЛЕ, а после отката состояние сравнивается с
baseline. Три вызова одного и того же кода — единственный способ, которым
«вернулись как было» может означать что-то проверяемое, а не «скрипт дошёл до
конца без ошибки».

Значений секретов модуль не читает. Проверка на утечку смотрит на файлы,
которые транзакция создаёт, и на журнал — и ищет там ПРИЗНАКИ значения, а не
само значение: длинные непробельные строки рядом со словами про токен. Сам
секрет для этого не нужен, и брать его неоткуда.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

SYSTEMCTL = "/usr/bin/systemctl"
SYSTEMD_ANALYZE = "/usr/bin/systemd-analyze"
JOURNALCTL = "/usr/bin/journalctl"
CURL = "/usr/bin/curl"

#: Витрины, чьё здоровье обязано пережить транзакцию. Заданы по домену, а не по
#: порту: порт — деталь реализации, которая уже однажды переехала (9104→9120).
SHOWCASES = ("lordfilm47.space", "lordserial33.biz", "1lordserials1.online",
             "zonafilm.space", "animedia.icu", "animedia.space")

#: Заголовки, по которым видно, что именно отдаёт витрина. Их совпадение до и
#: после — доказательство того, что транзакция не подменила контент.
FINGERPRINT_HEADERS = ("x-site-factory-build-id", "x-site-factory-artifact-sha256",
                       "x-site-factory-template", "x-site-factory-template-revision")


def _run(*args: str, timeout: int = 60) -> tuple[int, str]:
    try:
        proc = subprocess.run(list(args), capture_output=True, text=True,
                              timeout=timeout, check=False)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, f"{exc.__class__.__name__}: {exc}"


def effective_units(units: list[str]) -> dict:
    """Эффективные определения — как их видит systemd, а не как написано в файле."""
    out = {}
    for unit in units:
        row = {}
        for prop in ("ExecStart", "User", "WorkingDirectory", "Environment",
                     "EnvironmentFiles", "LoadCredential", "FragmentPath", "DropInPaths"):
            code, text = _run(SYSTEMCTL, "show", "-p", prop, "--value", unit, timeout=30)
            row[prop] = text.strip() if code == 0 else f"<ошибка {code}>"
        out[unit] = row
    return out


def unit_activity(units: list[str]) -> dict:
    """Активность юнитов и их таймеров: транзакция не должна ничего погасить."""
    out = {}
    for unit in units:
        code, state = _run(SYSTEMCTL, "is-active", unit, timeout=20)
        code2, enabled = _run(SYSTEMCTL, "is-enabled", unit, timeout=20)
        timer = unit.replace(".service", ".timer")
        code3, tstate = _run(SYSTEMCTL, "is-active", timer, timeout=20)
        out[unit] = {"active": state.strip(), "enabled": enabled.strip(),
                     "timer_active": tstate.strip()}
    return out


def systemd_verify(units: list[str]) -> dict:
    out = {}
    for unit in units:
        code, text = _run(SYSTEMD_ANALYZE, "verify", unit, timeout=60)
        # `verify` строг к шаблонным юнитам и к чужим предупреждениям; сюда
        # пишется факт, а трактует его вызывающий.
        out[unit] = {"exit": code, "output": text.strip()[:400]}
    return out


def pinned_tree_ownership(pinned_root: str) -> dict:
    """Владелец и права закреплённого дерева — выборочно, но по всей глубине."""
    root = Path(pinned_root)
    if not root.exists():
        return {"present": False}
    bad = []
    checked = 0
    for path in root.rglob("*"):
        checked += 1
        try:
            info = path.lstat()
        except OSError:
            continue
        if info.st_uid != 0 or info.st_gid != 0:
            bad.append(f"{path}: владелец {info.st_uid}:{info.st_gid}")
        if not path.is_symlink() and (info.st_mode & 0o022):
            bad.append(f"{path}: открыт на запись не владельцу")
        if len(bad) >= 20:
            break
    return {"present": True, "checked": checked, "problems": bad}


def showcase_health(sites: tuple[str, ...] = SHOWCASES) -> dict:
    """Здоровье и отпечаток отдаваемого витриной контента."""
    out = {}
    for site in sites:
        code, body = _run(CURL, "-s", "-o", "/dev/null", "-D", "-", "--max-time", "15",
                          "-k", "--resolve", f"{site}:443:127.0.0.1",
                          f"https://{site}/", timeout=30)
        status = ""
        fingerprint = {}
        for line in body.splitlines():
            if line.startswith("HTTP/"):
                parts = line.split()
                if len(parts) > 1:
                    status = parts[1]
            name, _, value = line.partition(":")
            if name.strip().lower() in FINGERPRINT_HEADERS:
                fingerprint[name.strip().lower()] = value.strip()
        hcode, hbody = _run(CURL, "-s", "-o", "/dev/null", "-w", "%{http_code}",
                            "--max-time", "15", "-k", "--resolve",
                            f"{site}:443:127.0.0.1", f"https://{site}/healthz",
                            timeout=30)
        out[site] = {"status": status, "healthz": hbody.strip(),
                     "fingerprint": fingerprint}
    return out


def content_refresh_health(state_dir: str = "/var/lib/lords-content-refresh") -> dict:
    """Состояние конвейера обновления каталога."""
    directory = Path(state_dir)
    if not directory.is_dir():
        return {"present": False}
    out = {"present": True}
    for name in ("last_failure", "last_success"):
        path = directory / name
        if path.exists():
            try:
                out[name] = path.read_text(encoding="utf-8", errors="replace").strip()[:64]
            except OSError:
                out[name] = "<не прочитан>"
    code, text = _run(SYSTEMCTL, "show", "-p", "Result", "--value",
                      "lords-content-refresh.service", timeout=20)
    out["last_result"] = text.strip() if code == 0 else f"<ошибка {code}>"
    return out


#: Признак значения секрета рядом со словом про секрет. Само значение для этой
#: проверки не нужно и не используется.
LEAK_RE = re.compile(
    r"(?i)(api[_-]?token|publisher[_-]?id|secret|password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-.]{12,})")


def credential_leak_scan(paths: list[str], journal_units: list[str]) -> dict:
    """Ни значения, ни его следов не должно появиться там, где их не было."""
    findings = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            continue
        targets = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
        for target in targets[:2000]:
            try:
                text = target.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in LEAK_RE.finditer(text):
                # Имя credential'а — не значение: `LoadCredential=имя:путь` и
                # `Environment=..._CREDENTIAL=имя` легальны и обязаны быть.
                if "CREDENTIAL" in match.group(0).upper() or "/" in match.group(2):
                    continue
                findings.append(f"{target}: похоже на значение рядом с «{match.group(1)}»")
    for unit in journal_units:
        code, text = _run(JOURNALCTL, "-u", unit, "-n", "200", "--no-pager", timeout=30)
        if code != 0:
            continue
        for match in LEAK_RE.finditer(text):
            if "CREDENTIAL" in match.group(0).upper() or "/" in match.group(2):
                continue
            findings.append(f"journal:{unit}: похоже на значение рядом с «{match.group(1)}»")
    return {"scanned_paths": len(paths), "findings": findings[:20],
            "clean": not findings}


def snapshot(units: list[str], pinned_root: str) -> dict:
    """Полный снимок наблюдаемого состояния. Снимается до и после."""
    return {
        "effective_units": effective_units(units),
        "unit_activity": unit_activity(units),
        "pinned_tree": pinned_tree_ownership(pinned_root),
        "showcases": showcase_health(),
        "content_refresh": content_refresh_health(),
    }


def compare_to_baseline(baseline: dict, current: dict) -> dict:
    """Что разошлось между исходным состоянием и текущим.

    Сравниваются не все поля: эффективные определения юнитов транзакция меняет
    намеренно, и их расхождение — цель, а не дефект. Сравнивается то, что
    обязано выжить: активность юнитов, здоровье витрин и отпечаток контента.
    """
    differences = []

    for unit, before in (baseline.get("unit_activity") or {}).items():
        after = (current.get("unit_activity") or {}).get(unit)
        if after is None:
            differences.append(f"{unit}: пропал из наблюдения")
            continue
        for key in ("active", "enabled", "timer_active"):
            if before.get(key) != after.get(key):
                differences.append(
                    f"{unit}.{key}: было «{before.get(key)}», стало «{after.get(key)}»")

    for site, before in (baseline.get("showcases") or {}).items():
        after = (current.get("showcases") or {}).get(site)
        if after is None:
            differences.append(f"{site}: пропал из наблюдения")
            continue
        if before.get("status") != after.get("status"):
            differences.append(
                f"{site}: код был {before.get('status')}, стал {after.get('status')}")
        if before.get("fingerprint") != after.get("fingerprint"):
            differences.append(
                f"{site}: отпечаток отдаваемого контента изменился — "
                "транзакция не должна была его трогать")

    return {"identical": not differences, "differences": differences}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="host_checks")
    parser.add_argument("--units", required=True, help="через запятую")
    parser.add_argument("--pinned-root", default="/opt/site-factory/runtime")
    parser.add_argument("--snapshot", help="записать снимок в файл")
    parser.add_argument("--compare", help="сравнить с ранее записанным снимком")
    args = parser.parse_args()

    units = [u.strip() for u in args.units.split(",") if u.strip()]
    current = snapshot(units, args.pinned_root)

    if args.snapshot:
        Path(args.snapshot).write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.compare:
        baseline = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        result = compare_to_baseline(baseline, current)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["identical"] else 1

    print(json.dumps(current, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
