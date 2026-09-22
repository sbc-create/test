# BLOCK 00 — Deploy / Mutation Path Audit

**Stage:** `SITE-FACTORY-RELEASE-ORCHESTRATOR-01`
**Scope:** `/srv/site-factory/repo`
**Method:** repository evidence only (Read/Grep/Glob). Live host probes deferred.
**Date:** 2026-09-20

## Verdict

There is **no unified Release Orchestrator**. Runtime mutations split into four worlds. Paths that bypass Core registry / factory pipeline are marked **BYPASS** and must lose “supported automation” status once the orchestrator is bootstrapped.

Administrative root remains a documented boundary, not supported unattended automation.

## Matrix legend

| Column | Meaning |
| --- | --- |
| privilege | effective OS privilege |
| site_scope | blast radius |
| accepts_arbitrary_args | free-form args change blast radius |
| registry_aware | uses inventory / site-profiles / directions |
| indexability_guarded | gates on indexing policy |
| artifact_digest_guarded | verifies digest before mutate |
| rollback_capable | automated rollback of mutation |
| idempotent | safe re-run |
| currently_supported | runnable with filled inventory today |

## Factory pipeline (guarded)

| entrypoint | owner | privilege | site_scope | accepts_arbitrary_args | registry_aware | indexability_guarded | artifact_digest_guarded | rollback_capable | idempotent | currently_supported |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `python3 -m factory deploy` | factory | process | one site | no | yes | yes (QA/SEO) | partial (build_id) | yes | yes | local adapters yes; ssh no |
| `python3 -m factory rollback` | factory | process | one site | `--allow-production` | yes | no | no | is rollback | yes | local yes |
| `python3 -m factory build` | factory | process | one site | `--force` | yes | yes | build_id | n/a | yes | yes |
| `LocalDisposableTarget` | factory | local FS | one site | no | yes | via pipeline | yes | yes | yes | yes |
| `PayloadMultisiteTarget` | factory | local FS | per-tenant | no | yes | via pipeline | BUILD_ID | yes | yes | if toolchain |
| `SshAnsibleTarget` | factory | deploy_user | remote | no | yes | via pipeline | build_id | yes | designed | **no** (empty hosts) |
| `operator_applied` in `inventory/targets.yaml` | **unimplemented** | n/a | n/a | n/a | declared | n/a | n/a | n/a | n/a | **no** |

## Ansible (prepared, not live)

| entrypoint | owner | privilege | site_scope | accepts_arbitrary_args | registry_aware | indexability_guarded | artifact_digest_guarded | rollback_capable | idempotent | currently_supported |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `automation/ansible/deploy-site.yml` | ansible | sudo allowlist | one site | no | yes | no in playbook | no | prune previous | yes | no |
| `automation/ansible/rollback-site.yml` | ansible | deploy_user | one site | optional target | yes | no | no | is rollback | yes | no |

## BYPASS — host scripts (must close as supported paths)

| entrypoint | owner | privilege | site_scope | accepts_arbitrary_args | registry_aware | indexability_guarded | artifact_digest_guarded | rollback_capable | idempotent | currently_supported |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `automation/host/lords-staging-apply.sh` | operator | **root** | lords-01..03 hardcoded | env SHA/certs | partial | closed staging only | if EXPECT_SHA | yes | yes | **BYPASS yes** |
| `automation/host/finalize-public-sites.sh` | operator | **root** | hardcoded domains | no | partial | does not open indexing | HEAD SHA | nginx restore | yes | **BYPASS yes** |
| `automation/host/lords-content-refresh.sh` | timer | privileged | lords-01..03 | script list | partial | player freeze | render gate | symlink | yes | **BYPASS yes** |
| `automation/host/nova-daily-refresh.sh` | cron/host | user+systemctl | lords+zona hardcoded | budgets | hardcodes | min-catalog | fingerprint | leave previous | designed | **BYPASS yes** |
| `automation/host/nova-catalog-publish.py --apply` | tools | FS + suggested sudo restart | CSV sites | **yes** | partial | min-catalog | sha256 | before-images | lock | **BYPASS yes** |
| `automation/host/nova-player-configure.py` | operator | systemctl hardcoded | mapped | site select | profiles | no | no | unknown | partial | **BYPASS yes** |
| `automation/host/yummy-content-run.sh` | root units | root+docker | env project | relative path | no | no | image-bound | no | once | **BYPASS yes** |
| `automation/host/deploy-control-api.sh` | operator | sudo systemctl | control plane | `--source` | no | n/a | digest_of | yes | yes | control-only |
| `automation/host/install-units.sh` | operator | root | host | arbitrary unit names | no | no | no | no | yes | **BYPASS yes** |
| Secret Hub `apply_consumer` | hub | root+restart unit | one consumer | restart flag | **yes** | no | no | snapshot | yes | scoped bypass |

## Unit name drift (evidence of guessed services)

- `lords-content-refresh.sh`: `systemctl restart ${site}.service` → `lords-01.service`
- `nova-daily-refresh.sh`: `lords-nova-01.service`, `nova-zona-01.service` with `|| true`
- Two naming schemes for the same tenants → orchestrator must use **registry `service_name` only**

## factory-guard / sudoers / polkit

| entrypoint | notes |
| --- | --- |
| `.claude/hooks/guard_bash.py` | agent Bash only; does not bind host root scripts |
| sudoers / polkit in repo | **none found** — privilege boundary not versioned |
| inventory sudo_allowlist | schema exists; ssh hosts empty |

## Core registry today

| path | role |
| --- | --- |
| `config/site-profiles/*.json` | site_id + domains[] + indexing_enabled (exact domains) |
| `config/directions/lords.json` | Lords apex/www + profile + runtime_root + ports |
| `config/SITE-MATRIX.json` | derived matrix |
| `inventory/targets.yaml` | deploy adapters (operator_applied dead) |

**No TLD fallback** found for domain→site. Exact match only (profiles / directions / analytics).

## Close plan (orchestrator)

1. Supported batch release path = `site-factory-release` + root runner (registry handlers only).
2. Host BYPASS scripts gain `RELEASE_ORCHESTRATOR_REQUIRED` refuse gate when enforcement is on.
3. `operator_applied` either implemented as registry handler or removed from “supported”.
4. Runbooks updated: no manual `systemctl`/`curl` per site for normal batches.
5. Administrative root install remains one-time bootstrap only.

## Key files

- `factory/cli.py`, `factory/pipeline.py`, `factory/targets/*`
- `automation/ansible/*`, `automation/host/*`
- `inventory/targets.yaml`, `inventory/ssh-hosts.yaml`
- `config/site-profiles/*`, `config/directions/lords.json`
- `docs/DEPLOY.md`, `docs/lords/STAGING.md`, `docs/runbooks/*`
