# OWNER RESTART — lords-02 only

СЕРВЕРНЫЙ ТЕРМИНАЛ

1. Подключение:
```text
ssh claude@185.231.154.18
```

2. Одна точная restart-команда текущего сервиса:
```text
sudo -n systemctl restart nova-lords-02.service
```

3. Одна точная проверка:
```text
systemctl show nova-lords-02.service -p ActiveState -p SubState -p MainPID -p ExecMainStartTimestamp -p NRestarts --no-pager
```

4. Одна точная live build-проверка:
```text
curl -sS -D- -o /tmp/lords02-home.html -A 'lords-deploy-verify/1' https://lordserial33.biz/ | head -n 40
python3 - <<'PY'
import re, pathlib
html=pathlib.Path('/tmp/lords02-home.html').read_text(encoding='utf-8', errors='replace')
print('data-design=', re.search(r'data-design="([^"]+)"', html).group(1))
PY
curl -sS -A 'lords-deploy-verify/1' https://lordserial33.biz/__template_version | python3 -m json.tool
```

Ожидаемый результат:
- ActiveState=active, SubState=running
- MainPID новый относительно 2900912 (или новый ExecMainStartTimestamp после 2026-09-20 19:40:06 UTC)
- NRestarts не в loop
- build_id=`20260920T193847Z-3c90aab-nova`
- artifact_sha256=`5dd817fe6ee12070609e16123cccc5cd3a6eace80fa895993227d2b3b2ad78cc`
- data-design=`lords-series-feed-v2` (не `lords-sheet`)
- X-Robots-Tag / meta robots остаются `noindex, nofollow`

Что прислать:
полный вывод команд.

---

Staged (no restart yet):
- rollback: `/srv/lords/.frontend/.rollback/20260920T194006Z-lords-02`
- disk artifact SHA matches release
- neighbor manifests lords-01/03 unchanged
- lords-01 and lords-03 NOT staged (shared artifact awaiting this restart)
