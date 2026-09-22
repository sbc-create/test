# zonafilm.cc — что осталось сделать владельцу

Контур `zona-02` собран, запущен и проверен целиком. Не сделаны ровно те шаги,
которые требуют root или учётных данных Cloudflare, — и ни один из них не
обходится: `sudo` закрыт профилем `UNATTENDED_SAFE`, а брокер выкладки
(`/usr/local/libexec/site-factory/lords-deploy-broker`) принимает заявки только
на `lords-01..03` — список зашит в root-файле.

Всё, что ниже, — четыре команды и одна запись в панели. Ожидаемый результат
каждой указан: если он не совпал, дальше идти не нужно.

---

## Что уже готово

| Что | Где лежит | Чем подтверждено |
| --- | --- | --- |
| Релиз | `/srv/lords/.frontend/releases/zona-02-1015c650d8be/` | sha256 рантайма `7ccf094a…` совпадает с закреплённым шаблоном |
| Манифест | `/srv/lords/.frontend/template-manifest-zona-02.json` | `design_version 1.2.0` проверена по набору версий артефакта |
| Каталог | `zona-02-catalog.json`, `zona-02-details.json` | 53 652 записи, ревизия `0b59f77b…`, дубликатов 0 |
| Привязка порта | `lords-runtime-registry.json`, ключ `zona-02` | записи соседей сверены побайтно |
| Юнит | `automation/host/systemd/nova-zona-02.service` | **не установлен** — нужен root |
| vhost | `automation/host/nginx/zona-02.conf` | **не установлен** — нужен root |
| Запись DNS | — | **не создана** — нет учётных данных Cloudflare |

---

## Шаг 1. Запись DNS (панель Cloudflare, зона `zonafilm.cc`)

```
A    zonafilm.cc       45.131.182.225   Proxy status: DNS only
A    www.zonafilm.cc   45.131.182.225   Proxy status: DNS only
```

`45.131.182.225` — origin стенда: то же значение в `origin_ipv4`
(`config/directions/lords.json`) и в живой записи соседней витрины
`zonafilm.space`.

`DNS only` — не предпочтение. В `config/directions/lords.json` все домены
направления объявлены `"mode": "dns-only"`. Proxy-режим добавил бы поверх
витрины кэш и сертификат Cloudflare, и тогда `X-Robots-Tag: noindex`, который
отдаёт origin, зависел бы от политики кэширования CDN — ровно тот риск
случайного открытия индексации, который исключён по заданию.

Делегация уже подтверждена и менять её не нужно: серверы зоны `.cc` отдают
`paris.ns.cloudflare.com` и `piers.ns.cloudflare.com`, зона активна, оба
назначенных NS отвечают авторитетно.

**Ожидаемый результат:** `dig +short zonafilm.cc` → `45.131.182.225`.

---

## Шаг 2. Юнит витрины

```bash
sudo install -m 0644 -o root -g root \
  /home/claude/wt-release-zonafilm-cc-full-cycle-01/automation/host/systemd/nova-zona-02.service \
  /etc/systemd/system/nova-zona-02.service
sudo systemctl daemon-reload
sudo systemctl enable --now nova-zona-02.service
```

**Ожидаемый результат:**

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9123/healthz     # 200
curl -s -D- -o /dev/null http://127.0.0.1:9123/ | grep Build-Id
# X-Site-Factory-Build-Id: zona-02-1015c650d8be
```

Первый ответ появляется **не сразу**: старт читает каталог на 16 МиБ и боковой
файл на 75 МиБ и строит указатели. Измерено на этом стенде — от 105 до 290 с.
`TimeoutStartSec` в юните намеренно не задан.

Порт 9123 сейчас занят проверочным процессом этой сессии, запущенным от
пользователя `claude`. Его нужно остановить до включения юнита:

```bash
pkill -f 'releases/zona-02-1015c650d8be/lords-frontend.py --port 9123'
```

---

## Шаг 3. Сертификат

Выпускается **до** переключения DNS, если используется DNS-01, и **после** —
если HTTP-01. Порт 80 в vhost уже отдаёт `/.well-known/acme-challenge/`.

```bash
sudo certbot certonly --webroot -w /var/www/certbot -d zonafilm.cc -d www.zonafilm.cc
```

**Ожидаемый результат:** `/etc/letsencrypt/live/zonafilm.cc/fullchain.pem`
существует и покрывает оба имени.

---

## Шаг 4. vhost

Ставить **после** сертификата: конфигурация ссылается на его файлы, и без них
`nginx -t` не пройдёт.

```bash
sudo install -m 0644 -o root -g root \
  /home/claude/wt-release-zonafilm-cc-full-cycle-01/automation/host/nginx/zona-02.conf \
  /etc/nginx/lords/zona-02.conf
sudo nginx -t && sudo systemctl reload nginx
```

**Ожидаемый результат:** `nginx -t` → `syntax is ok` / `test is successful`.

**Конфигурация уже проверена офлайн.** `factory.lords.nginx_check` разбирает её
против nginx 1.18 — той версии, что стоит на хосте (`/usr/sbin/nginx` →
1.18.0), — и претензий не имеет. Это не замена `nginx -t`, и выдавать её за неё
нельзя: настоящую проверку делает сам nginx перед reload, и она в команде выше.

**Стык с TLS отрепетирован.** `automation/host/zonafilm-cc-tls-rehearsal.py`
поднимает локальный терминатор с одноразовым сертификатом и проксирует на
витрину ровно те заголовки, что задаёт этот vhost (`Host`,
`X-Forwarded-Proto: https`). Проверено то, что ломается именно здесь:

| проверка | результат |
| --- | --- |
| петля редиректов | нет, не больше одного перехода |
| итоговый код на четырёх маршрутах | 200 |
| canonical | `https://zonafilm.cc/…` на всех |
| `X-Robots-Tag: noindex, nofollow` доживает через прокси | да |
| обход слэша срабатывает до витрины | да, один переход |

Отчёт — `artifacts/evidence/release-zonafilm-cc-full-cycle-01/12-deploy/tls-rehearsal.json`.
Одноразовый сертификат удалён, доверенным нигде не объявлялся. Публичным HTTPS
репетиция не является и им не притворяется.

---

## Шаг 5. Приёмка запускается сама

После шага 4 больше ничего вводить не нужно. Один раз запустить наблюдателя:

```bash
cd /home/claude/wt-release-zonafilm-cc-full-cycle-01
/srv/site-factory/repo/.venv/bin/python automation/host/zonafilm-cc-await-cutover.py \
  --out artifacts/evidence/release-zonafilm-cc-full-cycle-01/13-live/await-cutover.json
```

Он ждёт, пока сойдутся четыре условия — запись A резолвится, TLS отвечает и
покрывает имя, `https://zonafilm.cc/` даёт 200, и заголовок
`X-Site-Factory-Build-Id` равен `zona-02-1015c650d8be`, — и только тогда сам
прогоняет полную приёмку по публичному адресу, складывая отчёт в
`13-live/acceptance-public.json`.

Проверять что-то одно бессмысленно: 200 без build-id может отдать соседняя
витрина, поймавшая имя, а сменившийся PID сам по себе не говорит, какой релиз
поднялся.

---

## Чего делать НЕ нужно

* **не открывать индексацию.** Витрина закрыта на двух уровнях: `noindex,
  nofollow` в заголовке и в разметке каждой страницы, `robots.txt` запрещает
  всё, карта сайта пуста. Открытие — отдельная команда, после визуальной
  приёмки;
* **не перезапускать соседей.** `nova-zona-01`, `zonafilm.space`, Animedia,
  Yummy, Lords, gateway, ratings и comments к этому контуру отношения не имеют;
* **не трогать зоны других доменов** в Cloudflare.

---

## Откат

Если после включения что-то не так:

```bash
cd /home/claude/wt-release-zonafilm-cc-full-cycle-01
/srv/site-factory/repo/.venv/bin/python automation/host/zonafilm-cc-rollback.py \
  --mode unbind --apply

sudo systemctl stop nova-zona-02.service
sudo systemctl disable nova-zona-02.service
sudo rm -f /etc/nginx/lords/zona-02.conf && sudo nginx -t && sudo systemctl reload nginx
```

Останов службы и снятие vhost — **обязательная** часть, а не рекомендация.
Репетиция показала: после отвязки общий загрузчик на освободившемся порту
уходит не в отказ, а в `releases/legacy/current`, и `zonafilm.cc` отдавал бы
чужую легаси-витрину.

Откат проверен: общий реестр возвращается к тем же байтам, что были до первой
выкладки (`267db340…`), восстановление — обратно к `98a2eef6…`.
Данные витрины при отвязке не удаляются, повторная выкладка занимает секунды.

---

## Что останется после открытия индексации

Перед тем как открывать, нужно закрыть три внешних блокера — ни один не решается
внутри этого контура:

1. **Плеер.** Витрине не выдан Publisher ID провайдера. Все 52 794 записи с
   источниками отдают честное `noaccess` с подписью и без пустого iframe.
   Нужно решение владельца: выдать `zona-02` пару учётных данных CDNVideoHub
   (профиль `lords`) и подтвердить у провайдера домен `zonafilm.cc`, после чего
   боковой файл создаётся операцией `PLAYER_CONFIGURE`.
2. **Счётчик Метрики и проект Topvisor.** Чужой счётчик не подставлен намеренно:
   он писал бы события не туда. Нужны учётные данные для создания отдельных
   объектов под `zonafilm.cc`.
3. **Юридические данные.** `legal_profile` нового сайта не заполнен. Выдумывать
   владельца и документы нечем — это owner gate.
