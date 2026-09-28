# Owner restart command

Exactly one command. Do not run anything else first.

```bash
sudo -n systemctl restart lords-nova-01.service
```

Preflight already passed; rollback is verified (see `ROLLBACK_VERIFICATION.json`).
This agent could not execute the command (G-PRIV). After restart, follow
`POST_RESTART_CHECKLIST.md`.
