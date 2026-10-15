# Одна операция nginx на `claude-control-01`: `http → https` и `www → апекс`

Запись от 2026-10-15. Два дефекта у девяти живых доменов правятся одной и той
же строкой в одном и том же файле, поэтому и операция нужна одна. Файлы уже
подготовлены и лежат в `var/staged-nginx/`; в `/etc/nginx` ничего не изменено.

## Что измерено

**`http://` отдаёт 200 без перенаправления** — девять доменов из семнадцати
опубликованных (`scratchpad/д24-http-на-https.py`, 2026-10-15):

| отдаёт 200 по http (правка нужна) | уже отдаёт 308 (не трогаем) |
| --- | --- |
| `animedia.icu`, `animedia.space`, `an1meg0.site`, `lordserials22.info`, `yummyani7.site`, `yummyani7.info`, `zonafilm.space`, `zonafilm.cc`, `zonafilm12.site` | `an1mego.site`, `animeg0.site`, `lordfilm47.space`, `lordserial33.biz`, `1lordserials1.online`, `yummyani.biz`, `yummyani.org`, `yummyani.site` |

Заголовка HSTS нет ни у одного домена сети — в эту операцию он не входит
(отдельное решение: ошибка в HSTS не откатывается быстро).

**`www` отдаёт сайт с canonical на сам www-хост** — четыре домена:
`zonafilm.cc`, `zonafilm12.site`, `lordserials22.info`, `an1meg0.site`.
Причина видна в конфигурации: имя `www` стоит в `server_name` блока апекса, и
приложение собирает canonical из `$host`. Ещё у двух (`yummyani7.site`,
`yummyani7.info`) `www` отвечает 200, но canonical ведёт на апекс — сигнал
верный, адресов всё же два; правка та же, срочность ниже.

Срочность выросла: 2 октября эти домены были закрыты к индексации, сейчас
открыты все семнадцать. Подробности и независимое измерение SEO-сессии —
[`OWNER_WWW_MIRRORS_20261015.md`](OWNER_WWW_MIRRORS_20261015.md).

## Чем правка подготовлена

```bash
python3 automation/local/stage-https-www-fix.py              # exit 0
python3 automation/local/stage-https-www-fix.py --diff        # что именно меняется
python3 -m pytest tests/unit/test_stage_https_www_fix.py -q   # 10 passed
```

Инструмент читает ДЕЙСТВУЮЩУЮ конфигурацию и применяет ровно два
преобразования, образец — уже работающий файл этого же узла
(`/etc/nginx/sites-enabled/yummyani.biz.conf`):

1. в блоке порта 80 `location /` отдаёт `308 https://<апекс>$request_uri`;
   путь ACME и `location = /healthz` остаются как были;
2. имя `www` убирается из `server_name` блока **443** и получает свой блок 443
   с тем же сертификатом и `308` на апекс.

Три вещи сделаны намеренно и проверками закреплены:

- **имя `www` остаётся в блоке порта 80.** Подтверждение владения именем
  (`http-01`) идёт на порт 80; убрав `www` оттуда, продление сертификата,
  который это имя покрывает, сломалось бы при следующем сроке. Содержимое по
  `http` блок всё равно не отдаёт — там `308`.
- **`308`, а не `301`:** сохраняет метод и тело, `POST` не вырождается в `GET`.
  Так же устроены восемь доменов узла, которые уже в норме.
- **заголовка `X-Robots-Tag` в блоке `www` нет.** Переменная режима
  `$cell_robots_*` объявлена `map`-ом в файле витрины; ссылка на неё из файла,
  где её нет, даёт `unknown variable`, и nginx не перезагрузится ВОВСЕ — то
  есть ошибка одного домена уронит соседние.

Покрытие сертификата именем `www` проверено у живого хоста (SAN в
предъявленном сертификате), а не в `/etc/letsencrypt`: каталог под root.
Покрывают: `an1meg0.site`, `lordserials22.info`, `zonafilm.cc`,
`zonafilm12.site`, `yummyani7.site`, `yummyani7.info`. У `animedia.icu`,
`animedia.space` и `zonafilm.space` один общий сертификат без имён `www` —
но у них имени `www` нет и в DNS, поэтому блок `www` им не создаётся и не
нужен.

## Подготовленные файлы

| домен | файл(ы) в `var/staged-nginx/` | что внутри |
| --- | --- | --- |
| `animedia.icu` | `animedia-01.conf` | http → https |
| `animedia.space` | `animedia-02.conf` | http → https |
| `an1meg0.site` | `animego-04.conf`, `animego-04-tls.conf` | http → https, www → апекс |
| `lordserials22.info` | `lords-05.conf`, `lords-05-tls.conf` | http → https, www → апекс |
| `yummyani7.site` | `yummy-07.conf`, `yummy-07-tls.conf` | http → https, www → апекс |
| `yummyani7.info` | `yummy-08.conf`, `yummy-08-tls.conf` | http → https, www → апекс |
| `zonafilm.space` | `zona-01.conf` | http → https |
| `zonafilm.cc` | `zona-02.conf` | http → https, www → апекс |
| `zonafilm12.site` | `zona-03.conf`, `zona-03-tls.conf` | http → https, www → апекс |

## Порядок (root на `claude-control-01`, по одному домену)

Один домен за раз — чтобы отказ не задел соседей: `nginx -t` проверяет ВСЮ
конфигурацию, и перезагрузки не будет ни у кого, если ошибся один файл.

```bash
# host: claude-control-01, от root. Пример — zonafilm.cc.
# Имена переменных латиницей: bash не принимает кириллицу в именах
# (`Д=…` даёт «command not found»), и копировать такое владельцу нельзя.
DOM=zonafilm.cc; CONF=zona-02.conf
REPO=/home/claude/wt-nova-publish-memory-02

# 1. Копия текущего файла рядом, с датой (как уже принято в lords/).
cp -a /etc/nginx/lords/$CONF /etc/nginx/lords/$CONF.bak.$(date -u +%Y%m%dT%H%M%SZ)

# 2. Разница — глазами, до установки.
diff -u /etc/nginx/lords/$CONF $REPO/var/staged-nginx/$CONF

# 3. Установка и ПРОВЕРКА ДО перезагрузки.
install -m 0644 -o root -g root $REPO/var/staged-nginx/$CONF /etc/nginx/lords/$CONF
nginx -t && systemctl reload nginx

# 4. Проверка результата сразу, не следуя переходам.
curl -sI http://$DOM/           | head -3      # ждём 308 и Location https://$DOM/
curl -sI https://www.$DOM/      | head -3      # ждём 308 и Location https://$DOM/
curl -s https://$DOM/ | grep -o 'rel="canonical" href="[^"]*"' | head -1
curl -sI "http://$DOM/.well-known/acme-challenge/test" | head -1     # не 308: ACME жив
```

Откат — одной командой, копия снята на шаге 1:

```bash
install -m 0644 -o root -g root /etc/nginx/lords/$CONF.bak.<дата> /etc/nginx/lords/$CONF
nginx -t && systemctl reload nginx
```

У доменов с двумя файлами (`-tls.conf`) шаги 1–3 выполняются для каждого
файла, а `nginx -t && systemctl reload nginx` — один раз, после обоих.

## Проверка после применения

Моя сторона, без прав:

```bash
python3 automation/local/public-acceptance.py zonafilm.cc zonafilm12.site \
    lordserials22.info an1meg0.site
python3 /tmp/.../д24-http-на-https.py        # перечень 17 доменов, код и Location
```

Полный обход 17 доменов (код, `Location`, canonical, режим индексации) берёт
на себя SEO-сессия — об этом договорено сообщением, и её измерение уже
сошлось с моим.

## Чего эта запись не делает

Не меняет конфигурацию живых сайтов: правка `/etc/nginx` — root. Не добавляет
HSTS. Не трогает восемь доменов, которые уже отвечают `308`. Не касается
партии K2 (`lordfilm.*`, `lordserial.*` на `k2-zomro-01`): у неё отдельный
узел, своя раскладка и свой документ
[`OWNER_DNS_TLS_K2_20261015.md`](OWNER_DNS_TLS_K2_20261015.md).
