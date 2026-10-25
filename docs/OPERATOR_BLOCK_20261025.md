# Операторский блок 25.10.2026: четыре остановки и узкие права для пятёрки

Один блок, всё проверяемо и обратимо. Команды даны полностью; ни одна не
требует прав шире перечисленных. Агент их не выполняет: `systemctl` и правка
`inventory/ssh-hosts.yaml` закрыты профилем сессии, и обходить это нельзя.

## A. Остановить выделенные службы четырёх выведенных домéнов

Распоряжение владельца 2026-10-25. Сохранность проверена ДО остановки:
каталог сошёлся с отпечатками у всех четырёх домéнов (3 + 3 + 2 + 2 файла, ноль
расхождений), накладки скопированы. Файлы ТЕКУЩЕГО состояния (номера серий,
события, состояние эпизодов — 9 файлов) меняются, пока службы работают; их
окончательный снимок берётся ПОСЛЕ остановки, шагом A.3.

**Состояние на 25.10 ~23:0xZ, измерено, а не предположено.** Из четырёх
выведенных домéнов службы РАБОТАЮТ у двух, и ровно столько памяти они держат:

| домен | порт | состояние | держит памяти |
| --- | --- | --- | --- |
| animedia.space | 9122 | слушает, процесс жив | **958 МиБ** |
| lordfilm47.space | 9110 | слушает, процесс жив | **1 252 МиБ** |
| lordserials22.site | 9116 | не слушает (ячейка `planned`, служба не заводилась) | 0 |
| lordserials22.space | 9117 | не слушает (ячейка `planned`, служба не заводилась) | 0 |

Измерено по `/proc/<pid>/status` (`VmRSS`) для процессов с нужным портом.
Поэтому **фактически освобождено пока 0 МиБ**, а шаг A.1 освобождает
**2 210 МиБ** — на узле, где доступно около 1 130 МиБ. Это и есть цена
невыполненного шага: больше, чем весь текущий запас узла.

Выполнять на управляющем узле (45.131.182.225) от root:

```bash
# A.1. Остановить и отключить, чтобы перезагрузка их не подняла
systemctl disable --now nova-animedia-space.service \
                        nova-animedia-space-candidate.service \
                        animedia-space-update.timer \
                        animedia-space-update.service \
                        nova-lordfilm47-space.service \
                        nova-lordfilm47-space-candidate.service \
                        nova-lordserials22-site.service \
                        nova-lordserials22-site-candidate.service \
                        nova-lordserials22-space.service \
                        nova-lordserials22-space-candidate.service \
                        lords-01.service

# A.2. Убедиться, что общие службы и действующие сайты не затронуты
systemctl is-active nginx \
    nova-animedia-icu.service nova-an1mego-site.service nova-an1meg0-site.service \
    nova-animeg0-site.service nova-zonafilm-space.service nova-zonafilm-cc.service \
    nova-zonafilm12-site.service nova-lordserial33-biz.service \
    nova-lordserials22-info.service nova-1lordserials1-online.service
free -m
```

```bash
# A.3. Окончательный снимок состояния ПОСЛЕ остановки (от учётной записи claude)
cd /home/claude/wt-nova-publish-memory-02
python3 automation/local/withdrawal-preserve.py \
    --domain animedia.space --domain lordfilm47.space \
    --domain lordserials22.site --domain lordserials22.space \
    --out artifacts/withdrawal-20261025-final
```

**Что должно получиться.** `free -m` показывает прирост доступной памяти около
**2,4 ГиБ** (измерено по RSS: nova-lordfilm47-space 1 270 МиБ,
nova-animedia-space 950 МиБ, animedia-space-update 152 МиБ, lords-01 9 МиБ).
Все перечисленные в A.2 службы остаются `active`. Данные и каталоги НЕ
удаляются: распоряжение велит сохранить их для переезда.

**Чего делать нельзя.** Не трогать `/srv/lords/.frontend` (общий рантайм
действующих витрин) и не удалять каталоги `/srv/animedia-space`,
`/srv/lordfilm47-space`, `/srv/lordserials22-site`, `/srv/lordserials22-space`.

## B. Узкие права для пяти новых витрин на k2-zomro-01

Размещение выбрано измерением (ниже, §C). Пять новых витрин получают свои
юниты `nova-<домен с дефисами>.service`, и выпуск обязан уметь их перезапускать.
Сейчас `sudo_allowlist` узла перечисляет только восемь юнитов партии K2,
поэтому выпуск пятёрки упрётся в права.

Правка файла `inventory/ssh-hosts.yaml` (агенту запись в него закрыта), секция
`hosts[ref: k2-zomro-01].sudo_allowlist` — ДОБАВИТЬ пять строк, ничего не
удаляя:

```yaml
      - "/usr/bin/systemctl restart nova-lordserials1-cc.service"
      - "/usr/bin/systemctl restart nova-lordserials1-info.service"
      - "/usr/bin/systemctl restart nova-lordserials21-cc.service"
      - "/usr/bin/systemctl restart nova-lordserials21-info.service"
      - "/usr/bin/systemctl restart nova-lordserials21-mobi.service"
```

И соответствующая правка `/etc/sudoers.d/k2deploy` на узле (от root):

```bash
# B.1. Проверить текущее правило, не меняя его
sudo -n -l -U k2deploy | sed -n '1,40p'

# B.2. Добавить ровно пять команд (пример строки; синтаксис существующего файла
#      сохранить — он уже содержит восемь таких же для партии K2)
visudo -f /etc/sudoers.d/k2deploy
#   k2deploy ALL=(root) NOPASSWD: /usr/bin/systemctl restart nova-lordserials1-cc.service
#   … и так для остальных четырёх

# B.3. Проверка синтаксиса обязательна: ошибка в sudoers лишает узел sudo целиком
visudo -c -f /etc/sudoers.d/k2deploy
```

**Границы.** Ни `systemctl start/stop` вообще, ни `nginx -s reload` без
проверки, ни права на другие юниты. Только `restart` пяти названных служб —
ровно то, что нужно выпуску, и ничего сверх.

## C. Почему размещение — k2-zomro-01 (измерено 25.10 ~22:0xZ)

| Узел | Память всего | Доступно | Витрин запущено | RSS одной витрины | Диск свободно | Нагрузка |
| --- | --- | --- | --- | --- | --- | --- |
| управляющий 45.131.182.225 | 30 075 МиБ | **1 130 МиБ** | 13 | 440–1 641 МиБ | 14,2 ГиБ (7 %) | 0,72 на ядро |
| **k2-zomro-01** 145.63.129.86 | 9 945 МиБ | **5 876 МиБ** | 8 | **440–447 МиБ** | **58,0 ГиБ (86 %)** | 0,01 на ядро |

Пять витрин по измеренному расходу 447 МиБ — это **2 235 МиБ**; на k2 останется
около **3 641 МиБ** (37 % памяти узла) и 56,5 ГиБ диска. На управляющем узле
столько памяти нет даже после остановки четырёх выведенных витрин (1,13 + 2,4 =
3,5 ГиБ при потребности 2,2 ГиБ у витрин с расходом 447 МиБ, но действующие
витрины этого узла стоят 0,9–1,6 ГиБ каждая, и запаса на обновления не
остаётся).

Поэтому пятёрка размещается на k2-zomro-01, а DNS переключается ПОСЛЕ
готовности: сейчас все пять A-записей указывают на управляющий узел
(45.131.182.225), новый адрес — 145.63.129.86.

## D. Поднять пятёрку на k2-zomro-01 (всё, что требует root)

Что уже сделано агентом и проверено на узле (к этому блоку готово всё, кроме
самих привилегированных действий):

| Шаг | Чем проверено |
| --- | --- |
| комплект данных и кода пяти витрин доставлен в `/home/k2deploy/stage` | `sha256sum -c` НА УЗЛЕ: по 4 файла на витрину, `rc=0` ×5 |
| юниты, конфигурации nginx, включаемые файлы режима и точки upstream доставлены | `sha256sum -c` НА УЗЛЕ: 31 файл, `rc=0` |
| опись узла знает пятёрку | `MANIFEST.json`: ячеек 13 (8 действующих записей дословно прежние) |
| общий `site-cells-upstreams.conf` собран на ВЕСЬ состав узла | `diff` с файлом узла: ровно +5 блоков, ни один прежний не изменён |
| выпуск кода опознаёт витрину | `k2-release-code.sh lords-18 --dry-run` → «домен lordserials1.cc, учётка lordserials1-cc, порт 9136» и дальше честный отказ «витрина не запущена, это задача k2-launch-site.sh» |
| запуск готов по комплекту и памяти | `k2-launch-site.sh <site> --dry-run` ×5 → «комплект на месте, память 5879 МиБ, плеер нет» |

Почему дальше нужен оператор: `sudo -n -l` у `k2deploy` разрешает ровно
`nginx -t`, `systemctl reload nginx` и `restart` восьми действующих юнитов.
Ни `useradd`, ни `install` в `/etc`, ни `daemon-reload` там нет — и расширять
это самому агенту нечем.

```bash
# ВСЁ НИЖЕ — от root на 145.63.129.86. Пять учётных записей, пять маршрутов.
set -eu
acc_list="lordserials1-cc lordserials1-info lordserials21-cc lordserials21-info lordserials21-mobi"

# --- D.1. Учётные записи и каталоги (образец 14.10, те же режимы) --------
# Код — 2775 с группой витрины (выкладку делает k2deploy), данные — 0750:
# постоянные данные принадлежат только самой витрине.
for acc in $acc_list; do
  id -u "$acc" >/dev/null 2>&1 || useradd --system --home-dir "/srv/$acc" --shell /usr/sbin/nologin "$acc"
  install -d -m 2775 -o "$acc" -g "$acc" "/srv/$acc"
  install -d -m 0750 -o "$acc" -g "$acc" "/srv/$acc/data"
  usermod -aG "$acc" k2deploy
done

# --- D.2. Юниты ТОЛЬКО пяти новых витрин --------------------------------
# Глобом `nova-*.service` не ставить: он переустановит юниты восьми
# действующих витрин, которых эта задача не касается.
cd /home/k2deploy/stage/units
install -m 0644 -o root -g root \
  nova-lordserials1-cc.service nova-lordserials1-cc-candidate.service \
  nova-lordserials1-info.service nova-lordserials1-info-candidate.service \
  nova-lordserials21-cc.service nova-lordserials21-cc-candidate.service \
  nova-lordserials21-info.service nova-lordserials21-info-candidate.service \
  nova-lordserials21-mobi.service nova-lordserials21-mobi-candidate.service \
  /etc/systemd/system/
systemctl daemon-reload

# --- D.3. Общий файл объявлений upstream --------------------------------
# Доставленный файл собран на все 13 ячеек узла и отличается от стоящего
# ровно пятью новыми блоками (сверено diff'ом). Порядок важен: без него
# `nginx -t` на новом маршруте упадёт на неизвестном upstream.
cp -a /etc/nginx/conf.d/site-cells-upstreams.conf /root/site-cells-upstreams.conf.before-20261025
install -m 0644 -o root -g root /home/k2deploy/stage/nginx/site-cells-upstreams.conf /etc/nginx/conf.d/
nginx -t && systemctl reload nginx

# --- D.4. Права на перезапуск пяти служб (§B этого же документа) ---------
# Выполнить D.4 ДО первого запуска: иначе выпуск кода упрётся в права.

# --- D.5. Запуск витрин ПОСЛЕДОВАТЕЛЬНО, с проверкой памяти -------------
# k2-launch-site.sh сам: ставит робот-файл и точку upstream (существующие НЕ
# трогает), ставит конфигурацию домена, проверяет `nginx -t` и при провале
# снимает ТОЛЬКО свою, перезагружает nginx, раскладывает данные каталога с
# правами витрины, разворачивает выпуск из бандла — и останавливается перед
# службой с кодом 3, потому что publisher_id не передан. Это не ошибка
# прогона, а защита: чужой или выдуманный номер подставлять запрещено.
for site in lords-18 lords-19 lords-20 lords-21 lords-22; do
  awk '/^MemAvailable:/{print "доступно памяти, МиБ: " int($2/1024)}' /proc/meminfo
  bash /home/k2deploy/stage/k2-launch-site.sh "$site" || echo "код $? (3 = нет плеера, маршрут настроен)"
done
systemctl list-units --type=service --state=running --no-pager | grep -c nova-   # было 8

# --- D.6. Когда владелец назначит publisher_id пяти доменам -------------
# По одному файлу на витрину, 0640 владельцу витрины, значение из Secret Hub:
#   /home/k2deploy/stage/player/<site>-player.json  →  {"publisher_id":"<номер>","source_mode":"provider-id"}
# затем повторно: k2-launch-site.sh <site>  (он доложит healthz и RSS)
```

```bash
# --- D.7. Сертификаты — ПОСЛЕ переключения DNS, по одной витрине ---------
# Сценарий уже на узле и держит порядок, который нельзя переставлять: certbot
# подтверждает владение по HTTP (путь .well-known в конфигурации порта 80 уже
# работает), блок 443 ставится только ПОСЛЕ выпуска — ssl_certificate на
# несуществующий файл роняет проверку конфигурации вместе с СОСЕДНИМИ
# витринами. При неудаче файл 443 убирается сам.
for site in lords-18 lords-19 lords-20 lords-21 lords-22; do
  bash /home/k2deploy/stage/k2-enable-tls.sh "$site" --dry-run
  bash /home/k2deploy/stage/k2-enable-tls.sh "$site"
done
```

**Чего ждать от домена ДО сертификата.** Конфигурация порта 80 новой витрины
не отдаёт содержимое: она держит путь ACME, `/healthz` и перенаправление на
HTTPS. Поэтому между D.5 и D.7 домен по HTTP отвечает 301 на адрес, которого
ещё нет, а по HTTPS — сертификатом сервера по умолчанию (соседней витрины).
Это ожидаемое промежуточное состояние, а не поломка; содержимое домен начинает
отдавать после D.7 и появления publisher_id (D.6).

**Чего в блоке нет намеренно.** Сертификатов (TLS-конфигурации витрин
доставлены, но ставятся после выпуска сертификата: `nginx -t` на конфигурации
с несуществующим сертификатом падает), переключения DNS и правки режима
индексации: витрина рождается закрытой, и открытие — отдельное решение
владельца отдельной операцией.

**DNS.** Переключение A-записей пяти доменов с 45.131.182.225 на 145.63.129.86
агент выполнить не может: `inventory/dns-zones.yaml` содержит `zones: []`, то
есть фабрике не выдано ни одной зоны. Это вход владельца — либо запись в
инвентарь с токеном, ограниченным зоной, либо переключение у регистратора.
