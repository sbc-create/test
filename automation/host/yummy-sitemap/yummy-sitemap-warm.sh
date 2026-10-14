#!/usr/bin/env bash
# Прогрев карт сайта Yummy (B016) — временная мера до выкладки b016-sitemap-swr.patch.
#
# Почему это работает. Инвентарь карты в Redis живёт ровно час; первый запрос после
# истечения строит его синхронно 35–57 с. Через nginx yummyani7.* (proxy_read_timeout 30s)
# такой запрос получает 504, но Next.js сборку ДОВОДИТ и кладёт в кеш — следующий
# запрос за 0,2–0,9 с (замеры 13–14.10). Таймер раз в 5 минут делает этот «первый
# запрос» сам, так что окно холодного кеша для обходчика сжимается с часа до ≤5 минут.
# Тёплый запрос стоит ~0,2 с, холодный строит инвентарь один раз в час.
#
# Только чтение по HTTPS, только домены Yummy из списка ниже, ничего не пишет на диск
# кроме журнала службы. Код выхода 0 всегда, если сеть есть: 504 на холодном — ожидаемо.
set -u
DOMAINS="yummyani7.site yummyani7.info yummyani.site yummyani.org yummyani.biz"
PARTS="titles seasons episodes"
for d in $DOMAINS; do
  for p in $PARTS; do
    out=$(curl -s -o /dev/null --max-time 90 -A "yummy-sitemap-warm" \
      -w '%{http_code} %{time_total}' "https://$d/sitemap/$p.xml" || echo "ERR 0")
    echo "warm $d/sitemap/$p.xml $out"
  done
done
exit 0
