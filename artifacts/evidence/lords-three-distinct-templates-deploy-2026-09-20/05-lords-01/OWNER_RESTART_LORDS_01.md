# OWNER RESTART — lords-01 only

СЕРВЕРНЫЙ ТЕРМИНАЛ

1. Подключение:
```text
ssh claude@185.231.154.18
```

2. Одна точная restart-команда текущего сервиса:
```text
sudo -n systemctl restart lords-nova-01.service
```

3. Одна точная проверка:
```text
systemctl show lords-nova-01.service -p ActiveState -p SubState -p MainPID -p ExecMainStartTimestamp -p NRestarts --no-pager
```

4. Одна точная live build-проверка:
```text
curl -sS -D- -o /tmp/lords01-home.html -A 'lords-deploy-verify/1' https://lordfilm47.space/ | head -n 40
python3 - <<'PY'
import re, pathlib
html=pathlib.Path('/tmp/lords01-home.html').read_text(encoding='utf-8', errors='replace')
print('data-design=', re.search(r'data-design="([^"]+)"', html).group(1))
PY
curl -sS -A 'lords-deploy-verify/1' https://lordfilm47.space/__template_version | python3 -m json.tool
```

Ожидаемый результат:
- ActiveState=active, SubState=running
- MainPID новый относительно 3875810 (или ExecMainStartTimestamp после 2026-09-20 20:51:03 UTC)
- NRestarts не в loop
- build_id=`20260920T193847Z-3c90aab-nova`
- artifact_sha256=`5dd817fe6ee12070609e16123cccc5cd3a6eace80fa895993227d2b3b2ad78cc`
- data-design=`lords-cinema-v2` (не `lords-sheet`)
- X-Robots-Tag / meta robots остаются `noindex, nofollow`
- lordserial33.biz остаётся `lords-series-feed-v2` (не откатывать)

Что прислать:
полный вывод команд.

---

Staged (no restart yet):
- rollback: `/srv/lords/.frontend/.rollback/20260920T205103Z-lords-01`
- disk artifact SHA matches release
- lords-02 live still PASS (series-feed-v2)
- lords-03 NOT staged (waiting lords-01 post-deploy)
- PID before: 3875810 / start 2026-09-20 14:18:35 UTC
