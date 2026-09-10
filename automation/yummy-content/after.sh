#!/usr/bin/env bash
# Фоновый backfill Kitsu + шесть production-циклов после выкладки.
set -uo pipefail
cd /srv/site-factory/yummy-content
echo "[after] шесть production-циклов"
rm -f state/shadow-cycles.jsonl state/cycles.log
python3 cycles.py
echo "[after] циклы завершены"
echo "[after] фоновый backfill Kitsu, партиями с паузой"
for i in $(seq 1 20); do
  python3 -c "
import sys,json; sys.path.insert(0,'.')
import store, ratings
c=store.открыть('state/yummy-content.sqlite3')
r=ratings.собрать(c,'kitsu')
print('партия %s:' % $i, json.dumps({k:r.get(k) for k in ('matched','providerNoRating','errors','abortedReason')}, ensure_ascii=False))" 2>&1 | tail -1
  sleep 240
done
echo "[after] готово"
