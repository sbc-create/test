# OWNER RESTART — lords-02 only (visual repair canary)

СЕРВЕРНЫЙ ТЕРМИНАЛ

1. Подключение (канонический host из предыдущего runbook):
```text
ssh claude@185.231.154.18
```

2. Одна точная restart-команда:
```text
sudo -n systemctl restart nova-lords-02.service
```

3. Проверка unit:
```text
systemctl show nova-lords-02.service -p ActiveState -p SubState -p MainPID -p ExecMainStartTimestamp -p NRestarts --no-pager
```

4. Live build / design / indexability:
```text
curl -sS -A 'lords-deploy-verify/1' https://lordserial33.biz/__template_version | python3 -m json.tool
curl -sS -A 'lords-deploy-verify/1' https://lordserial33.biz/ | python3 - <<'PY'
import sys,re
html=sys.stdin.read()
print('data-design=', re.search(r'data-design="([^"]+)"', html).group(1))
print('green', '#3F7D26' in html or '#3f7d26' in html)
print('no_118', 'margin-top:118px' not in html)
print('no_tech_footer', not re.search(r'Lords · \d+\.\d+\.\d+ · [0-9a-f]{7,}', html))
print('no_anime', 'каталог аниме' not in html)
print('episode_card', 'c--episode' in html and 'grid--episode' in html)
print('robots', 'noindex, nofollow' in html)
PY
```

Ожидаемый результат:
- ActiveState=active, SubState=running
- build_id=`20260920T223935Z-4f8ef5a-visual`
- artifact_sha256=`b32438c91aaa8d3fa0a5297731a8ecfe2445c4f8f8ab7fedbe1998d69ff92988`
- data-design=`lords-series-feed-v2`
- green primary `#3F7D26`, no `margin-top:118px`, no tech footer SHA, no «каталог аниме»
- episode grid/cards present
- robots / indexability unchanged (`noindex, nofollow`)

Что прислать: полный вывод команд.

---

Staged (no restart yet):
- rollback: `/srv/lords/.frontend/.rollback/20260920T223958Z-lords-02`
- collection_contract bak: `/srv/lords/.frontend/.rollback/20260920T223935Z-4f8ef5a-visual-collection_contract.bak`
- disk artifact SHA matches release
- neighbor manifests lords-01/03 not yet restaged for this build
- lords-01 and lords-03 must NOT be restarted until lords-02 passes two stable live runs
