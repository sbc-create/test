# Privilege Boundary

## Preferred architecture

```text
unprivileged planner
→ immutable approved manifest
→ root-owned verifier/runner
→ allowlisted handlers from Core registry
```

## Runner contract

Accepts **only**:

```text
--release-id
--manifest
--manifest-digest
--approval
```

Rejects: arbitrary shell, service name, path, domain, `--force`, inline secret env.

Executable: `automation/host/site-factory-release-runner.py`

## One-time owner bootstrap

```text
1. install root-owned site-factory-release-runner
2. install systemd unit (optional)
3. install narrow sudoers/polkit for that runner only
4. create state dirs under /var/lib/site-factory/releases
5. set RELEASE_ORCHESTRATOR_REQUIRED=1 on legacy BYPASS host scripts
```

Print checklist:

```text
bin/site-factory-release bootstrap-print
```

After bootstrap, ordinary batches need **zero** owner SSH/systemctl/curl commands.

## Not allowed for agents

```text
systemctl *
docker *
bash *
python *   # as arbitrary root shell
```
