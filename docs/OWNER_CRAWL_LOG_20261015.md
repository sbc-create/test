# Журнал обхода роботов по доменам: подготовлено, ждёт решения о месте

Пункт 2 недельной очереди. Запись от 2026-10-15. Файлы подготовлены, в
`/etc/nginx` ничего не изменено.

**Применять ПОСЛЕ решения о месте.** Журнал — это запись на раздел, где
свободно 3,6 % ([`OWNER_DISK_P0_20261015.md`](OWNER_DISK_P0_20261015.md)).
Отсюда и устройство: в файл попадают только обращения роботов, а не копия всего
потока.

## Что измерено

Вопрос «обходят ли роботы домены-дубли» по общему журналу не решается: своего
`log_format` для `/var/log/nginx/access.log` не объявлено, действует встроенный
`combined`, а в нём **нет ни `$host`, ни `$server_name`**. Домена в записи
просто нет, и разложить обход по доменам оттуда нельзя никаким полем.

Свои журналы есть у восьми server-блоков; остальные 35 наследуют http-контекст:

| объявляют свой `access_log` (строка дописывается) | наследуют http (достаточно `conf.d`) |
| --- | ---: |
| `animedia-02.conf` (80 и 443), `lords-01.conf`, `lords-02.conf`, `lords-03.conf`, `yummyani.biz.conf`, `yummyani.org.conf`, `yummyani.site.conf` | 35 блоков |

Это не мелочь учёта: объявив журнал только в `conf.d`, обход восьми самых
старых доменов в него не попал бы вовсе — и неполнота выглядела бы как «роботы
не ходят».

Объём журналов nginx сейчас — **1,08 ГиБ**, из них несжатые текущие и `.1`:
`access.log.1` 278 МБ, `yummyani.site.access.log.1` 218 МБ,
`yummyani.site.access.log` 113 МБ, `access.log` 98 МБ.

## Что подготовлено

```bash
# 1. Формат, признак робота и объявление для наследующих блоков.
automation/host/nginx/00-crawl-log.conf        # → /etc/nginx/conf.d/

# 2. Восемь блоков со своим журналом: по одной добавленной строке.
python3 automation/local/stage-crawl-log.py --diff
# → var/staged-nginx-crawl/{animedia-02,lords-01,lords-02,lords-03,
#    yummyani.biz,yummyani.org,yummyani.site}.conf
```

Префикс `00-` обязателен: `log_format` допустим только в http-контексте, а
`access_log` со ссылкой на ещё не объявленный формат роняет проверку
конфигурации целиком — то есть не перезагрузится ни один сайт. Та же причина
уже записана в `00-webmaster-verification-log.conf`.

В восьми блоках журнал обхода — **второй** `access_log` блока: nginx пишет в
оба файла, собственный журнал витрины остаётся как был.

## Про потолок роста: `rotate 14` и `compress` уже действуют

Согласованный потолок — `rotate 14`, `maxsize 50M`, `compress`. Измерено: для
любого `/var/log/nginx/*.log` первые два уже в силе из системного
`/etc/logrotate.d/nginx` (`daily`, `rotate 14`, `compress`, `delaycompress`).
Новый `crawl.log` попадает под это правило сам, и **отдельный файл
logrotate для него создавать нельзя**: два правила на один файл logrotate
считает дублирующей записью и отказывается работать.

Не хватает только `maxsize 50M`, и добавить его можно ровно в одном месте — в
том же системном файле. Это заодно ограничит и действующие журналы, которые
сегодня растут до 278 МБ между суточными оборотами:

```bash
# host: claude-control-01, от root. Одна строка в существующий блок.
cp -a /etc/logrotate.d/nginx /etc/logrotate.d/nginx.bak.$(date -u +%Y%m%dT%H%M%SZ)
sed -i 's/^\trotate 14$/\trotate 14\n\tmaxsize 50M/' /etc/logrotate.d/nginx
logrotate --debug /etc/logrotate.d/nginx | head -20     # проверка без действий
```

## Порядок (root на `claude-control-01`)

```bash
REPO=/home/claude/wt-nova-publish-memory-02

# 1. Формат и объявление. Проверка ДО перезагрузки — обязательна.
install -m 0644 -o root -g root $REPO/automation/host/nginx/00-crawl-log.conf \
    /etc/nginx/conf.d/
nginx -t

# 2. Восемь блоков, по одному файлу, с копией рядом.
for f in animedia-02 lords-01 lords-02 lords-03; do
  cp -a /etc/nginx/lords/$f.conf /etc/nginx/lords/$f.conf.bak.$(date -u +%Y%m%dT%H%M%SZ)
  diff -u /etc/nginx/lords/$f.conf $REPO/var/staged-nginx-crawl/$f.conf
  install -m 0644 -o root -g root $REPO/var/staged-nginx-crawl/$f.conf /etc/nginx/lords/
done
for f in yummyani.biz yummyani.org yummyani.site; do
  cp -a /etc/nginx/sites-enabled/$f.conf /etc/nginx/sites-enabled/$f.conf.bak.$(date -u +%Y%m%dT%H%M%SZ)
  install -m 0644 -o root -g root $REPO/var/staged-nginx-crawl/$f.conf /etc/nginx/sites-enabled/
done

# 3. Проверка и перезагрузка — в этом порядке.
nginx -t && systemctl reload nginx

# 4. Через несколько минут: журнал появился и в нём есть домен.
ls -l /var/log/nginx/crawl.log
tail -3 /var/log/nginx/crawl.log
awk '{for (i=1;i<=NF;i++) if ($i ~ /^host=/) print $i}' /var/log/nginx/crawl.log \
  | sort | uniq -c | sort -rn | head
```

Откат — копии сняты на шагах 1–2:

```bash
rm -f /etc/nginx/conf.d/00-crawl-log.conf
install -m 0644 -o root -g root /etc/nginx/lords/<файл>.conf.bak.<дата> \
    /etc/nginx/lords/<файл>.conf
nginx -t && systemctl reload nginx
```

Снять объявление недостаточно без удаления строк из восьми блоков: `access_log`
со ссылкой на формат, которого больше нет, снова уронит проверку. Поэтому
откат идёт в обратном порядке — сначала блоки, потом объявление, и `nginx -t`
один раз после всего.

## Чего эта запись не делает

Не меняет конфигурацию живых сайтов и не создаёт журнал: правка `/etc/nginx` и
`/etc/logrotate.d` — root. Не включает полную копию потока: только обращения
роботов. Не трогает партию K2 — у неё свой узел.
