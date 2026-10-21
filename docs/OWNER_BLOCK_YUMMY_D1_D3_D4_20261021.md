[//]: # (Блок владельца: два собранных и проверенных образа Yummy с исправлениями D1, D3, D4. Условие эксперимента B031 сохранено и проверено хешем.)

# Блок владельца — выпуск D1/D3/D4 на Yummy: образы собраны и проверены

Собрано в ночь 21→22.10 по разрешению владельца «подготовку и выпуск разрешаю в
рамках действующих прав доступа, выпуск отдельный, условия B031 сохранить».
Сборка и проверка в моих правах оказались, **пересоздание контейнера — нет**:
`docker compose` требует пароли баз (`PG_SITE_PASSWORD`, `PG_ORG_PASSWORD`,
`PG_BIZ_PASSWORD`, `PG_YUMMY08_PASSWORD`), которых у моей сессии нет и которые я
не ищу. Это единственный недостающий шаг.

## Что собрано

| образ | кому | что внутри |
| --- | --- | --- |
| `yummyani/web:d3d4-944c932e76ff` | `.biz`, `.org`, `7.site`, `7.info` | D3 + D4 |
| `yummyani/web:d1d3d4-9cbfac20fbe8` | `yummyani.site` | D1 + D3 + D4 |

Оба собраны **ОТ работающих образов**, а не из ветки: ревизий `944c932e76ff` и
`9cbfac20fbe8` в локальных копиях исходников нет вовсе
(`git cat-file -t` → «could not get object info»), и сборка «из ветки» принесла
бы на витрины две недели чужой работы вместе с правкой. Исходники взяты из самих
образов (`docker create` + `docker cp`, образ не запускался).

**Условие эксперимента B031 сохранено и проверено хешем, а не обещанием:** в
новом образе `.site` файл обрезки заголовка совпадает с прежним
(`sha256` начинается на `61755fd0f9ec7e2c`) и НЕ совпадает с версией B031.
Заголовки контроля остаются обрезанными.

### Что исправлено, с файлом и строкой

| дефект | файл | было | стало |
| --- | --- | --- | --- |
| **D1** / MOD-103 | `src/lib/seo/sitemap-catalog.ts` | `DETAIL_LIMIT = 40` (строка 33): подробности только у первых сорока работ обхода | перенесены шесть файлов карты с исправленного образа: инкрементное хранилище подробностей, 800 работ за сборку, TTL 30 суток |
| **D3** / MOD-122 | `src/lib/seo/sitemap-detail-order.ts`, `sitemap-catalog.ts` | свежесть по условию `record.f < at` — время выборки против времени наблюдения | свежесть по СОСТАВУ (`missingObserved`) плюс множество незавершённых задач `seo:sitemap-pending:v1`, живущее между сборками |
| **D4** / MOD-108 | `src/modules/catalog/catalog-query.ts`, новый `walk-budget.ts` | `MAX_WALK_REQUESTS = 80` × `API_WALK_LIMIT = 100` = 8 000 записей | бюджет считается от запрошенной страницы (`walkBudget`), верхний предел 400 запросов = 40 000 записей, плюс защита от повтора курсора |

### Чем проверено ДО выпуска

Внутри сборки, то есть образ, не прошедший проверку, не появляется:

* **13 тестов** — 6 на бюджет обхода (D4) и 7 на свежесть (D3), оба набора
  воспроизводят дефект условием, которое его вызывало: «плоский предел 80 не
  покрывает объявленную страницу 350» и «серия, названная наблюдением и
  отсутствующая в записи, делает работу свежей, хотя выборка была позже
  наблюдения»;
* **`next build`** прошёл на обоих образах — значит перенос шести файлов карты
  в дерево `.site` проходит проверку типов (у приложения `ignoreBuildErrors` не
  выставлен);
* предел проверки назван прямо: `vitest` в этом образе не читает файл
  конфигурации (проверено опытом с невозможным `include`), поэтому тесты идут по
  производной копии дерева, где `@/` заменён абсолютным путём. Копия сверена с
  оригиналом обратной подстановкой — хеш дерева совпадает побайтно
  (`9e6fe94bc232552b` для `.site`, `250df1f6bcebf232` для остальных).

## Состояние ДО выпуска, снятое сегодня

| витрина | просмотр каталога | карта |
| --- | --- | --- |
| `7.info` | объявлено 350 страниц, содержимое кончается на **334-й** (8 карточек), охват **8 000** записей, страницы 335–350 пусты с кодом 200 | части `seasons`/`episodes` от 20.10, журнал наблюдений ПУСТ (MOD-121) |
| `.site` | то же | сезонов **37**, серий **1 644** при каталоге 8 378 работ |
| `.org` | то же | нет 24 серий, 7 из них стоят в карте `.biz` с 17–19.10 |

## Команды

```bash
# ---------- 1. ПРОВЕРКА ДО (только чтение) ----------
cd /home/claude/wt-nova-publish-memory-02
docker image inspect yummyani/web:d3d4-944c932e76ff --format '{{.Id}}'
docker image inspect yummyani/web:d1d3d4-9cbfac20fbe8 --format '{{.Id}}'
python3 automation/local/catalog-pager-reach.py yummyani7.info
# ожидание: «доходит до 334», «охват 8000», страницы 335–350 пусты

# ---------- 2. КАНАРЕЙКА: одна витрина, 7.info ----------
# Пароль берётся из вашего окружения; в команду его подставлять не нужно, если
# он уже экспортирован. Я его не читаю и не печатаю.
cd /home/claude/wt-nova-publish-memory-02/var/site-repos/yummyani7-info/deploy
cp compose.yaml compose.yaml.before-d3d4
sed -i 's|image: yummyani/web:rel-944c932e76ff|image: yummyani/web:d3d4-944c932e76ff|' compose.yaml
docker compose -p yummyani7-info up -d --no-deps web
docker inspect yummyani7-info-web-1 --format '{{.Config.Image}} {{.Created}}'

# ---------- 3. ПРОВЕРКА КАНАРЕЙКИ НА САЙТЕ ----------
cd /home/claude/wt-nova-publish-memory-02
python3 automation/local/catalog-pager-reach.py yummyani7.info
# признак D4: «доходит до» перестаёт быть 334, охват перестаёт быть 8000,
# страницы, объявленные листалкой, либо несут карточки, либо отвечают 404

curl -sS https://yummyani7.info/catalog/?page=340 | grep -c '/anime/'
# ожидание: больше нуля

python3 automation/local/sitemap-chain.py --domain yummyani7.info
# отрицательный контроль: число адресов в titles.xml не уменьшилось (8 378)

curl -sSL https://yummyani7.info/anime/science-saru-x-mbs-krupnomasshtabnaya-operatsiya/season/1/episode/2 \
  | grep -o '<title>[^<]*</title>'
# отрицательный контроль B031: заголовок НЕ обрезан (эта витрина — подопытная,
# у неё так и было до выпуска)

# ---------- 4. ОСТАЛЬНЫЕ ТРИ НА ТОМ ЖЕ ОБРАЗЕ ----------
# Только после приёмки канарейки.
cd /home/claude/wt-nova-publish-memory-02/var/site-repos/yummyani7-site/deploy
cp compose.yaml compose.yaml.before-d3d4
sed -i 's|image: yummyani/web:rel-944c932e76ff|image: yummyani/web:d3d4-944c932e76ff|' compose.yaml
docker compose -p yummyani7-site up -d --no-deps web

# .biz и .org живут в проекте yummyani-staging одним набором файлов:
WEB_BIZ_IMAGE=yummyani/web:d3d4-944c932e76ff \
WEB_ORG_IMAGE=yummyani/web:d3d4-944c932e76ff \
docker compose \
  -f /home/claude/wt-yummy-mail-biz/compose.staging.yaml \
  -f /home/claude/wt-portable-site-cell-01/automation/host/yummy-biz-indexing.override.yaml \
  -f /home/claude/wt-portable-site-cell-01/automation/host/yummy-overlays.override.yaml \
  -p yummyani-staging up -d --no-deps web-biz web-org
# ВАЖНО: у этого проекта образ задаётся переменной `WEB_*_IMAGE`, и без неё
# compose возьмёт `yummyani/web:staging` — именно так .site однажды и уехала на
# устаревший образ. Переменную подставлять обязательно.

# ---------- 5. yummyani.site, отдельным шагом ----------
WEB_SITE_IMAGE=yummyani/web:d1d3d4-9cbfac20fbe8 \
docker compose \
  -f /home/claude/wt-yummy-mail-biz/compose.staging.yaml \
  -f /home/claude/wt-portable-site-cell-01/automation/host/yummy-biz-indexing.override.yaml \
  -f /home/claude/wt-portable-site-cell-01/automation/host/yummy-overlays.override.yaml \
  -p yummyani-staging up -d --no-deps web-site

# приёмка .site: D1 — сезоны и серии появляются; кеш карты TTL 3600 с, поэтому
# первый замер сразу после пересоздания может дать прежние числа
python3 automation/local/sitemap-chain.py --domain yummyani.site
python3 automation/local/episode-sitemap-coverage.py yummyani.site yummyani.biz
# ожидание: ни одной работы в состоянии «НЕ НАЗВАНЫ»; сезонов и серий — порядок
# тысяч и сотен тысяч вместо 37 и 1 644

# отрицательный контроль B031 на .site: заголовок ОБЯЗАН остаться обрезанным
curl -sSL https://yummyani.site/anime/science-saru-x-mbs-krupnomasshtabnaya-operatsiya/season/1/episode/2 \
  | grep -o '<title>[^<]*</title>'
# ожидание: «Science SARU x MBS: Крупномасштабная — 1 сезон, 2 серия | YummyAnime»
# то есть С обрезкой. Полный заголовок здесь означал бы, что эксперимент сломан.
```

## Откат

```bash
# для любой витрины: вернуть прежний образ тем же путём
cd /home/claude/wt-nova-publish-memory-02/var/site-repos/yummyani7-info/deploy
cp compose.yaml.before-d3d4 compose.yaml
docker compose -p yummyani7-info up -d --no-deps web

# для проекта yummyani-staging — прежние теги:
WEB_SITE_IMAGE=yummyani/web:rel-9cbfac20fbe8 \
WEB_BIZ_IMAGE=yummyani/web:rel-944c932e76ff \
WEB_ORG_IMAGE=yummyani/web:rel-095aecc7ca27 \
docker compose -f … -p yummyani-staging up -d --no-deps web-site web-biz web-org
```

Прежние образы на узле есть — они работают прямо сейчас, поэтому откат сборки не
требует.

## Чего эти образы НЕ чинят

**D2 (MOD-121) — пустой журнал наблюдений у `7.info` и `7.site`.** Это не код:
писатель журнала (`yummy-episode-watcher`) настроен на каталог проекта
`yummyani-staging`, а у двух витрин `7.*` объявлены СВОИ каталоги, и под них
экземпляра наблюдателя нет. Пока журнала нет, D3 на этих двух витринах
бесполезен: очередь свежих работ будет пуста по-прежнему. Решение — отдельным
пунктом в итоговом списке.
