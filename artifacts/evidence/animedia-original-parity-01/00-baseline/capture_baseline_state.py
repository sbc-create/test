#!/usr/bin/env python3
"""Read-only снимок исходного состояния ANIMEDIA перед работой над паритетом.

Ничего не мутирует. Всё, что раньше было заявлено в отчёте, здесь измеряется
заново: ветка, HEAD, дерево, worktree, состояние обоих доменов, соответствие
служб доменам, назначения, цели откáта, индексация, DNS и TLS.

Чужие контуры в снимок не попадают. Единственное неизбежное чтение общего
файла — реестр рантайма: только из него домен связывается со службой и
релизом. Такие чтения считаются в FOREIGN_TENANT_READS.
"""
from __future__ import annotations

import hashlib, json, os, pathlib, re, socket, ssl, subprocess, time

РЕПО = pathlib.Path("/home/claude/wt-animedia-finalization-01")
FRONT = pathlib.Path("/srv/lords/.frontend")   # общий корень рантайма
ДОМЕНЫ = {"animedia-01": "animedia.icu", "animedia-02": "animedia.space"}
ВЫХОД = pathlib.Path("/tmp/claude-1001/-srv-site-factory-repo"
                     "/8ca8197e-7812-42cc-bf2d-ab1145272c2d/scratchpad/BASELINE_STATE.json")
чужие_чтения: list[str] = []


def г(*args, cwd=РЕПО) -> str:
    return subprocess.run(list(args), cwd=str(cwd), capture_output=True,
                          text=True).stdout.strip()


def ц(p) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def заголовки(домен: str) -> dict:
    h = subprocess.run(["curl", "-sSI", "--max-time", "25", f"https://{домен}/"],
                       capture_output=True, text=True).stdout
    б = lambda k: (re.search(rf"(?im)^{k}:\s*(.+)$", h).group(1).strip()
                   if re.search(rf"(?im)^{k}:\s*(.+)$", h) else None)
    код = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
                          "--max-time", "25", f"https://{домен}/"],
                         capture_output=True, text=True).stdout.strip()
    тело = subprocess.run(["curl", "-sS", "--max-time", "25", f"https://{домен}/"],
                          capture_output=True, text=True).stdout
    мета = re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']+)',
                     тело, re.I)
    канон = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',
                      тело, re.I)
    return {"http": код, "build_id": б("x-site-factory-build-id"),
            "artifact_sha256": б("x-site-factory-artifact-sha256"),
            "template_revision": б("x-site-factory-template-revision"),
            "x_robots_tag": б("x-robots-tag"), "server": б("server"),
            "meta_robots": мета.group(1) if мета else None,
            "canonical": канон.group(1) if канон else None,
            "header_and_meta_agree": bool(мета and б("x-robots-tag")
                                          and "noindex" in мета.group(1)
                                          and "noindex" in б("x-robots-tag"))}


def dns_tls(домен: str) -> dict:
    адреса = sorted({i[4][0] for i in socket.getaddrinfo(домен, 443,
                                                         proto=socket.IPPROTO_TCP)})
    ctx = ssl.create_default_context()
    with socket.create_connection((домен, 443), timeout=20) as s:
        with ctx.wrap_socket(s, server_hostname=домен) as ss:
            c = ss.getpeercert()
            имена = sorted({v for k, v in c.get("subjectAltName", ()) if k == "DNS"})
            return {"addresses": адреса, "tls_version": ss.version(),
                    "cert_subject_alt_names": имена,
                    "cert_not_after": c.get("notAfter"),
                    "cert_issuer": dict(x[0] for x in c.get("issuer", ()))
                                        .get("organizationName"),
                    "cert_covers_domain": домен in имена}


def служба(юнит: str) -> dict:
    v = г("systemctl", "show", "-p",
          "MainPID,ActiveState,SubState,Result,NRestarts,ExecMainStartTimestamp,"
          "ExecStart,Environment,Description", юнит, cwd="/")
    d = {}
    for строка in v.splitlines():
        if "=" in строка:
            k, _, з = строка.partition("=")
            d[k] = з
    return d


def main() -> int:
    итог: dict = {"task": "ANIMEDIA-BASELINE-STATE",
                  "tenant": "animedia",
                  "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  "mutations": 0}

    # --- репозиторий ---
    итог["repository"] = {
        "toplevel": г("git", "rev-parse", "--show-toplevel"),
        "common_dir": г("git", "rev-parse", "--git-common-dir"),
        "branch": г("git", "rev-parse", "--abbrev-ref", "HEAD"),
        "head": г("git", "rev-parse", "HEAD"),
        "head_subject": г("git", "log", "-1", "--format=%s"),
        "tree_hash": г("git", "rev-parse", "HEAD^{tree}"),
        "remote_head_of_branch": г("git", "rev-parse", "--verify", "--quiet",
                                   "origin/claude/animedia-template-finalization-01")
                                 or "не опубликована в origin",
        "remotes": г("git", "remote", "-v"),
        "reflog_head_10": г("git", "reflog", "-n", "10", "--date=iso").splitlines(),
        "status_porcelain": г("git", "status", "--porcelain").splitlines(),
        "worktrees": [b for b in г("git", "worktree", "list", "--porcelain").split("\n\n") if b],
        "animedia_branches": [s.strip() for s in
                              г("git", "branch", "--list", "claude/animedia-*").splitlines()],
    }
    итог["repository"]["worktree_clean"] = not итог["repository"]["status_porcelain"]

    # --- заявленные ранее факты, перепроверенные ---
    заявлено = {
        "branch": "claude/animedia-template-finalization-01",
        "last_commit_claimed": "7683566",
    }
    итог["verification_of_previous_claims"] = {
        "branch_claimed": заявлено["branch"],
        "branch_actual": итог["repository"]["branch"],
        "branch_matches": итог["repository"]["branch"] == заявлено["branch"],
        "commit_7683566_exists": bool(г("git", "cat-file", "-t", "7683566^{commit}") == "commit"),
        "commit_7683566_full": г("git", "rev-parse", "7683566^{commit}"),
        "commit_7683566_is_ancestor_of_head": subprocess.run(
            ["git", "merge-base", "--is-ancestor", "7683566", "HEAD"],
            cwd=str(РЕПО)).returncode == 0,
        "commits_after_7683566": г("git", "log", "--oneline", "7683566..HEAD").splitlines(),
    }

    # --- неизвестные файлы, происхождение которых не доказано ---
    пиды = sorted(РЕПО.glob("artifacts/evidence/animedia-blockwise-2026-09-19/raw/*.pid"))
    сведения = []
    for p in пиды:
        текст = p.read_text(encoding="utf-8", errors="replace").strip()
        живой = None
        if текст.isdigit():
            живой = pathlib.Path(f"/proc/{текст}").exists()
            команда = ""
            if живой:
                try:
                    команда = (pathlib.Path(f"/proc/{текст}/cmdline")
                               .read_bytes().decode("utf-8", "replace").replace("\0", " ").strip())
                except OSError:
                    команда = "недоступно"
        сведения.append({"file": str(p.relative_to(РЕПО)),
                         "content": текст,
                         "mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                    time.gmtime(p.stat().st_mtime)),
                         "pid_alive": живой,
                         "process_cmdline": (команда if живой else None),
                         "tracked_by_git": bool(г("git", "ls-files", "--error-unmatch",
                                                  str(p.relative_to(РЕПО)))),
                         "introduced_by_commit": г("git", "log", "-1", "--format=%h %ad %s",
                                                   "--date=short", "--",
                                                   str(p.relative_to(РЕПО))) or "не в истории",
                         "deleted": False,
                         "note": "не удаляется до доказательства происхождения"})
    итог["unknown_pid_files"] = сведения

    # --- блокировки фабрики ---
    замки = []
    for корень in (РЕПО / "artifacts" / "locks", РЕПО / ".locks", pathlib.Path("/run/site-factory")):
        if корень.is_dir():
            замки += [str(p) for p in корень.rglob("*") if p.is_file()]
    итог["locks"] = {"found": замки, "count": len(замки)}

    # --- реестр рантайма: только записи Animedia ---
    чужие_чтения.append(str(FRONT / "lords-runtime-registry.json"))
    реестр = json.loads((FRONT / "lords-runtime-registry.json").read_text())["sites"]
    итог["runtime_registry_animedia_entries"] = {k: v for k, v in реестр.items()
                                                 if k in ДОМЕНЫ}

    # --- витрины ---
    итог["sites"] = {}
    for sid, домен in ДОМЕНЫ.items():
        запись = реестр[sid]
        юнит = запись["unit"]
        ман_путь = pathlib.Path(запись["manifest_path"])
        ссылка = FRONT / "sites" / sid / "current"
        цель = pathlib.Path(os.readlink(ссылка)).name if ссылка.is_symlink() else None
        релиз = FRONT / "releases" / цель if цель else None
        код = релиз / "lords-frontend.py" if релиз else None
        сл = служба(юнит)
        ман = json.loads(ман_путь.read_text())
        резерв = ман_путь.with_suffix(ман_путь.suffix + ".before-b16")
        итог["sites"][sid] = {
            "domain": домен, "port": запись["port"], "unit": юнит,
            "unit_description": сл.get("Description"),
            "unit_exec_start": сл.get("ExecStart", "")[:200],
            "main_pid": сл.get("MainPID"), "active_state": сл.get("ActiveState"),
            "sub_state": сл.get("SubState"), "result": сл.get("Result"),
            "n_restarts": сл.get("NRestarts"),
            "started_at": сл.get("ExecMainStartTimestamp"),
            "manifest_path": str(ман_путь), "manifest": ман,
            "manifest_owner": f"{ман_путь.owner()}:{ман_путь.group()}",
            "manifest_mode": oct(ман_путь.stat().st_mode)[-4:],
            "manifest_sha256": ц(ман_путь),
            "assignment_symlink": str(ссылка),
            "assignment_target": цель,
            "assigned_code_sha256": ц(код) if код and код.is_file() else None,
            "assigned_release_json": (json.loads((релиз / "RELEASE.json").read_text())
                                      if релиз and (релиз / "RELEASE.json").is_file() else None),
            "rollback_manifest_backup": str(резерв) if резерв.is_file() else None,
            "rollback_manifest_build_id": (json.loads(резерв.read_text())["build_id"]
                                           if резерв.is_file() else None),
            "live": заголовки(домен),
            "dns_tls": dns_tls(домен),
        }
        s = итог["sites"][sid]
        s["declared_vs_executed_match"] = (
            s["manifest"]["artifact_sha256"] == s["assigned_code_sha256"])
        s["live_matches_assignment"] = (
            s["live"]["artifact_sha256"] == s["assigned_code_sha256"])
        s["service_matches_domain"] = (домен.split(".")[0] in (s["unit_description"] or "")
                                       or домен in (s["unit_description"] or ""))

    # --- цели откáта, принадлежащие Animedia ---
    откаты = {}
    for d in sorted((FRONT / "releases").iterdir()):
        if not d.is_dir() or "animedia" not in d.name:
            continue
        ф = d / "lords-frontend.py"
        откаты[d.name] = {"path": str(d),
                          "code_sha256": ц(ф) if ф.is_file() else None,
                          "release_json": (json.loads((d / "RELEASE.json").read_text())
                                           if (d / "RELEASE.json").is_file() else None)}
    итог["animedia_releases_on_host"] = откаты

    # --- пакеты и связка домен → профиль → шаблон → артефакт → служба ---
    пакеты = {}
    for p in sorted((РЕПО / "sites").glob("animedia*")) + \
             sorted((РЕПО / "config" / "site-profiles").glob("animedia*")):
        пакеты[str(p.relative_to(РЕПО))] = {"is_dir": p.is_dir(),
                                            "sha256": ц(p) if p.is_file() else None}
    итог["animedia_packages_in_repo"] = пакеты
    итог["chain_domain_to_service"] = {
        s["domain"]: {"profile": s["manifest"].get("profile"),
                      "template_family": s["manifest"].get("template_family"),
                      "design_version": s["manifest"].get("design_version"),
                      "build_id": s["manifest"].get("build_id"),
                      "artifact_sha256": s["manifest"].get("artifact_sha256"),
                      "assignment": s["assignment_target"],
                      "service": s["unit"], "pid": s["main_pid"]}
        for s in итог["sites"].values()}

    итог["FOREIGN_TENANT_READS"] = len(set(чужие_чтения))
    итог["foreign_tenant_reads_paths"] = sorted(set(чужие_чтения))
    итог["foreign_tenant_reads_why"] = (
        "реестр рантайма — единственный источник связи домен → порт → служба → "
        "релиз; без него связку пришлось бы угадывать")
    итог["FOREIGN_TENANT_MUTATIONS"] = 0
    ВЫХОД.write_text(json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
    print("снимок:", ВЫХОД)
    print("ветка:", итог["repository"]["branch"], "| HEAD:", итог["repository"]["head"][:12],
          "| дерево:", итог["repository"]["tree_hash"][:12],
          "| чисто:", итог["repository"]["worktree_clean"])
    for sid, s in итог["sites"].items():
        print(f"  {sid} {s['domain']}: http={s['live']['http']} build={s['live']['build_id']}")
        print(f"     PID {s['main_pid']} старт {s['started_at']} служба {s['unit']}")
        print(f"     назначение {s['assignment_target']}")
        print(f"     объявлено==исполняемо: {s['declared_vs_executed_match']}, "
              f"живое==назначение: {s['live_matches_assignment']}, "
              f"служба↔домен: {s['service_matches_domain']}")
        print(f"     robots: header={s['live']['x_robots_tag']!r} meta={s['live']['meta_robots']!r} "
              f"согласованы={s['live']['header_and_meta_agree']}")
        print(f"     canonical={s['live']['canonical']}")
        print(f"     DNS={s['dns_tls']['addresses']} TLS={s['dns_tls']['tls_version']} "
              f"сертификат покрывает домен={s['dns_tls']['cert_covers_domain']}")
    print("проверка заявленного:", json.dumps(итог["verification_of_previous_claims"],
                                              ensure_ascii=False)[:400])
    print("FOREIGN_TENANT_READS =", итог["FOREIGN_TENANT_READS"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
