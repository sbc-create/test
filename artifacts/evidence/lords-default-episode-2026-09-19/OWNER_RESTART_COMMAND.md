# Owner restart command

Exactly one command. Do not run anything else first.

```bash
sudo -n systemctl restart lords-nova-01.service
```

This agent must not execute the command. After restart, follow
`POST_RESTART_CHECKLIST.md`.
