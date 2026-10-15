# Переключение DNS и выпуск TLS для партии K2: один точный список

Запись от 2026-10-15. Узел назначения — **`k2-zomro-01`, `145.63.129.86`**;
прежний узел — `claude-control-01`, `45.131.182.225`. Партия: восемь витрин
`lords-10…lords-17`, все восемь служб на новом узле **уже работают** (измерено
мной, не пересказано: см. таблицу ниже).

## Почему это список для владельца, а не моя операция

Управления зоной у сессии нет, и это не предположение:

| проверено | результат |
| --- | --- |
| `inventory/dns-zones.yaml` | `zones: []` — ни одной разрешённой зоны |
| токен в окружении (`FACTORY_DNS_TOKEN*`, `CLOUDFLARE*`, `CF_*`) | нет ни одной переменной |
| `flarectl`, `cloudflared`, `cf-terraforming` | не установлены |
| сам API Cloudflare | **достижим**: `api.cloudflare.com/client/v4/user/tokens/verify` → HTTP 400 без токена |
| запрос фабрики о недостающих входах | `dns_zone` → «DNS cutover выполняется отдельным журналируемым шагом и требует scoped-токена зоны», блокирует `PRODUCTION_DEPLOY` статусом `BLOCKED_ACCESS` |

То есть не хватает ровно одного: **разрешённой записи зоны и scoped-токена**.
Сеть и инструменты на месте.

## Вариант A: владелец меняет записи сам (8 изменений)

Все восемь зон обслуживает Cloudflare. Менять надо только A-запись апекса:
`www` у всех восьми — CNAME на апекс, то есть переедет сам; записей AAAA нет
ни у одного домена (проверено `dig AAAA` на `@8.8.8.8` и на авторитетных NS).

| домен | NS (Cloudflare) | A сейчас | A должно стать |
| --- | --- | --- | --- |
| lordfilm.group | april, pablo | 45.131.182.225 | **145.63.129.86** |
| lordfilm.spb.ru | vin, lina | 45.131.182.225 | **145.63.129.86** |
| lordfilm.msk.ru | vin, lina | 45.131.182.225 | **145.63.129.86** |
| lordserial.su | pablo, april | 45.131.182.225 | **145.63.129.86** |
| lordserial.group | pablo, april | 45.131.182.225 | **145.63.129.86** |
| lordserial.spb.ru | vin, lina | 45.131.182.225 | **145.63.129.86** |
| lordserial.msk.ru | vin, lina | 45.131.182.225 | **145.63.129.86** |
| lordserial.net.ru | lina, vin | 45.131.182.225 | **145.63.129.86** |

Прежние значения для откату сняты ДО правки и лежат в
`var/k2-data/dns-k2.json` (A, AAAA, CNAME апекса и `www`, у публичного
резолвера и у авторитетных NS). Откат — вернуть A на `45.131.182.225`.

Проверка после правки (моя сторона, без прав на зону):

```bash
python3 automation/local/dns-cutover-plan.py --batch k2 --verify
```

Инструмент спрашивает и авторитетные NS, и публичный резолвер: запись может
быть изменена и ещё не разойтись по кешам, и это разные состояния.

## Вариант B: владелец выдаёт scoped-токен, перевод делаю я

Минимальная операция владельца:

1. В Cloudflare создать токен с правом **Zone.DNS:Edit** только на эти восемь
   зон (глобальный ключ аккаунта не нужен и не подходит).
2. Положить значение в `/etc/site-factory/secrets/dns/cloudflare-k2` (владелец
   root, режим 0400) — в git оно не попадает.
3. Дописать в `inventory/dns-zones.yaml` по записи на зону:

```yaml
zones:
  - ref: lordfilm-group
    zone: lordfilm.group
    provider: cloudflare
    api_token_secret_ref: file:/etc/site-factory/secrets/dns/cloudflare-k2
    scope: zone_records_only
    allowed_record_types: [A]
    allowed_names: ["@", "www"]
    cutover_requires: [origin_health_ok, tls_ready, rollback_plan]
  # … и так для семи остальных зон
```

`inventory/` меняет оператор: правка реестра целей из сессии запрещена
правилом G-WRITE, и обходить его я не буду.

## Шаг 2 (root на узле K2): сертификаты сразу после DNS

Готовность проверена заранее, чтобы выпуск не сорвался на мелочи:

| проверено на узле | результат |
| --- | --- |
| certbot | 2.9.0 установлен |
| автопродление | `certbot.timer` **enabled и active**, следующий запуск сегодня в 16:28 UTC |
| webroot ACME | `/var/www/certbot` существует |
| маршрут ACME в nginx | отдаёт из webroot, а не из приложения: `/.well-known/acme-challenge/<проба>` → 404 размером 146 байт, тогда как обычный несуществующий путь даёт 57 489 байт (страницу витрины). И у апекса, и у `www` |
| заготовки блоков 443 | восемь файлов `/home/k2deploy/stage/nginx/lords-1X-tls.conf`, каждый ждёт сертификат на ОБА имени (апекс и `www`) |
| установленные блоки 80 | восемь в `/etc/nginx/lords/`, `www` — отдельный блок с 301 на апекс |

```bash
# host: k2-zomro-01, от root, после того как dig покажет 145.63.129.86
for d in lordfilm.group lordfilm.spb.ru lordfilm.msk.ru lordserial.su \
         lordserial.group lordserial.spb.ru lordserial.msk.ru lordserial.net.ru; do
  certbot certonly --webroot -w /var/www/certbot \
      -d "$d" -d "www.$d" \
      --non-interactive --agree-tos -m <почта владельца> || break
done

# блоки 443 ставятся ТОЛЬКО после выпуска: ссылка на несуществующий
# сертификат не даст nginx перезагрузиться и уронит соседние витрины
install -m 0644 -o root -g root /home/k2deploy/stage/nginx/lords-1*-tls.conf /etc/nginx/lords/
nginx -t && systemctl reload nginx
```

Проверка снаружи (моя сторона, обычная проверка сертификата):

```bash
python3 automation/local/public-acceptance.py --batch k2
```

## Про `serverHold`: к этой партии он не относится

Все восемь домен партии делегированы (NS Cloudflare отвечают) и имеют
A-запись — удержания у них нет. Статус `serverHold`, записанный ранее,
относится к ЧЕТЫРЁМ другим домена́м сети: `lordserials22.site`,
`lordserials22.space`, `lordserial101.site`, `lordfilm077.site`. По ним
измерение 14–15 октября: ни NS, ни A-записи нет ни у одного (`dig NS` и
`dig A` на `@8.8.8.8` — пусто), что согласуется с удержанием; подтверждение
самого статуса — WHOIS реестра, выписка в `docs/OWNER_SERVERHOLD_PACKAGE.md`.
Партии K2 это не касается.
