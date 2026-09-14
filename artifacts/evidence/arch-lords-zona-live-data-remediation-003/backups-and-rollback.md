# total 101712
# drwxrwxr-x 2 claude claude     4096 Sep 14 15:13 .
# drwxr-xr-x 7 claude claude     4096 Sep 14 14:52 ..
# -rw-rw-r-- 1 claude claude 20062109 Sep 13 18:34 lords-01-details.json.before.20260914T145205Z
# -rw-rw-r-- 1 claude claude 20062109 Sep 13 18:34 lords-01-details.json.before.canary-lords-003
# -rw-rw-r-- 1 claude claude 20062109 Sep 13 18:34 lords-01-details.json.before.canary2-lords-003
# -rw-rw-r-- 1 claude claude 20069476 Sep 14 14:53 lords-01-details.json.before.rollout-lords-003
# -rw-rw-r-- 1 claude claude 20069378 Sep 14 15:07 lords-01-details.json.before.rollout2-lords-003
# -rw-rw-r-- 1 claude claude        0 Sep 14 15:10 lords-01.lock
# -rw-rw-r-- 1 claude claude  1268266 Sep 13 21:01 zona-01-details.json.before.20260914T145205Z
# -rw-rw-r-- 1 claude claude  1268266 Sep 13 21:01 zona-01-details.json.before.canary-zona-003
# -rw-rw-r-- 1 claude claude  1276845 Sep 14 15:12 zona-01-details.json.before.rollout-zona-003
# -rw-rw-r-- 1 claude claude        0 Sep 14 15:13 zona-01.lock

# Команды отката (по одной на витрину, проверены на боевом откате Lords)

## lords-01 — возврат к состоянию до задачи
cp -p /srv/site-factory/repo/var/lords/backfill-backups/lords-01-details.json.before.20260914T145205Z /srv/lords/.frontend/lords-01-details.json && sudo -n systemctl restart lords-nova-01.service
# ожидаемый sha256 после отката: a58f9d73c3e18a90f12dd5b5aea9df3777ff6c0bc125d8b7739823a7f32fe4eb

## zona-01 — возврат к состоянию до задачи
cp -p /srv/site-factory/repo/var/lords/backfill-backups/zona-01-details.json.before.20260914T145205Z /srv/lords/.frontend/zona-01-details.json && sudo -n systemctl restart nova-zona-01.service
# ожидаемый sha256 после отката: e0967a6a33693e8022e1a989cf968003f3532340a4b7906501664c32d2914280
