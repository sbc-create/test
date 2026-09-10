#!/usr/bin/env bash
# Довести контур: дождаться обогащения, собрать рейтинги, прогнать шесть циклов.
set -uo pipefail
cd /srv/site-factory/yummy-content
echo "[finish] жду завершения обогащения"
while pgrep -f "enrich.py" >/dev/null 2>&1; do sleep 20; done
echo "[finish] обогащение завершено: $(tail -2 state/enrich.log | tr '\n' ' ')"

echo "[finish] применяю detail ко всем сущностям"
python3 -c "
import sys,json; sys.path.insert(0,'.')
import store, detail
c=store.открыть('state/yummy-content.sqlite3')
print(json.dumps(detail.обогатить(c), ensure_ascii=False))"

echo "[finish] рейтинги: kitsu (официальный API, ID-first)"
python3 -c "
import sys,json; sys.path.insert(0,'.')
import store, ratings
c=store.открыть('state/yummy-content.sqlite3')
print(json.dumps(ratings.собрать(c,'kitsu'), ensure_ascii=False))" 2>&1 | tail -2

echo "[finish] шесть новых циклов"
rm -f state/shadow-cycles.jsonl state/cycles.log
python3 cycles.py
echo "[finish] готово"
