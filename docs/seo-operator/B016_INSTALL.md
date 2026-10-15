# B016 / T081 — постоянное исправление Yummy: установка, проверка, откат

Подготовлено 15.10.2026 сессией SEO. Сессия ничего из этого не выполняла на хосте:
пересоздание контейнеров Yummy — действие владельца (B016).

## Что исправляется

| Патч | Дефект | Где виден сейчас (замер 15.10 07:53Z) |
| --- | --- | --- |
| `b016-sitemap-swr.patch` | Инвентарь карт в Redis с TTL 3600 с строится синхронно в запросе (35–57 с); параллельные запросы строят каждый свой | `titles.xml` холодный: yummyani.site 44 с, .org 48 с, .biz 40 с; yummyani7.site/.info — **504** через 30 с (titles, seasons) |
| `b016-sitemap-cap.patch` | `walkAnimeListItems(maxPages=80)` × 100 = потолок 8000 адресов | у всех `titles.xml` ровно `loc=8000`; 366 живых тайтлов yummyani.site вне карты (12.10) |
| `t081-shelf-canonical-href*.patch` | Полки главной ссылаются на `/anime/<slug>--<uuid>` → 308 | главные: .site 54 из 101 ссылки, .org 36, .biz 54; yummyani7.* — 0 |

После SWR последний исправный инвентарь отдаётся сразу, перестройка идёт в фоне одним
исполнителем. Поэтому поднятие потолка больше не удлиняет ответ. Раньше именно это
запрещало поднимать потолок: «применять ТОЛЬКО вместе с ускорением», 12.10.

## Почему не «один коммит на все» (изменения Архитектора)

Сейчас витрины работают на **разных** образах, и ветки расходятся (`docker inspect`, 15.10):

| Контейнер | Образ | Коммит (ветка) |
| --- | --- | --- |
| yummyani-staging-web-site-1 | `rel-054c6170519d` | 054c617 (`claude/yummy-actual-shelf-01`) |
| yummyani-staging-web-org-1 | `rel-8be8d8b5bdf2` | 8be8d8b (`claude/contact-mail-org-site-01`) |
| yummyani-staging-web-biz-1 | `rel-4c5796eae24c` | 4c5796e (`claude/contact-mail-biz-01`) |
| yummyani7-site-web-1, yummyani7-info-web-1 | `rel-4c5796eae24c` | 4c5796e |

Ветки расходятся: 054c617 и 4c5796e — по 4 и 16 своих коммитов. Прежний план «97c88d2 + патчи»
откатил бы 33 коммита, в том числе c42561b («publisher ID закрепляется за арендатором») и
6c7b383 (откат возвращает витрине её образ). Поэтому каждая витрина получает **свою базу +
те же исправления**, и закрепление издателя не трогается.

`/srv/sites/yummyani-staging/repo` нельзя использовать как источник сборки. Там HEAD 97c88d2,
а в дереве незакоммиченные правки CR-006 от 20.09: Dockerfile, страница тайтла, «community
ratings». `deploy.sh` такое дерево сам отвергает («worktree is dirty»). Сборка идёт из чистых
рабочих копий нужных коммитов (ниже).

Работающие контейнеры подняты **тремя** compose-файлами, а не одним:

```
/home/claude/wt-yummy-mail-biz/compose.staging.yaml          (4c5796e, образ — ${WEB_*_IMAGE})
/home/claude/wt-portable-site-cell-01/automation/host/yummy-biz-indexing.override.yaml
/home/claude/wt-portable-site-cell-01/automation/host/yummy-overlays.override.yaml
```

`deploy.sh` передаёт один `-f` и пересоздал бы витрины без наложений:
- у yummyani.biz пропал бы `SEO_INDEXING_ENABLED=true`, и в тело вернулся бы `noindex` (D169);
- пропали бы накладки заголовков.

Поэтому пересоздание ниже — той же командой, что в этих файлах.

## Что проверено сессией (без хоста)

Копии баз — `git archive` в `var/yummy-check/`; репозиторий владельца не менялся. Зависимости
одинаковы: package.json и pnpm-lock.yaml совпадают у всех баз и у установленного
`node_modules`.

| База | patch (3 шт.) | vitest: падения до → после | новые тесты | tsc ошибок до → после | eslint |
| --- | --- | --- | --- | --- | --- |
| 054c617 | rc 0 | 4 → те же 4 (из 592) | 10/10 | 11 → те же 11 | 0 |
| 8be8d8b | rc 0 | 4 → те же 4 (из 571) | 10/10 | 11 → те же 11 | 0 |
| 4c5796e | rc 0 (T081 — перебазированный) | 4 → те же 4 (из 605) | 10/10 | 11 → те же 11 | 0 |

- **Падения vitest есть и на чистой базе:** genre-canonical, page-matrix ×2, portal-data. Ошибки tsc — `PageProps`/`LayoutProps`: их генерирует сборка Next, в архивной копии их нет.
- **Тест предела** `catalog-walk-cap.test.ts`: прежний код — rc 1, правка — rc 0, на всех трёх базах.
- **T081 на 4c5796e перебазирован.** Там есть полка «Тренды» (`trendingCards`), которая тоже строит ссылки через `hrefOf`. Именно она дала 18 ссылок `--uuid` в карусели yummyani.biz. Исходный патч её не знал, перебазированный канонизирует и её.
- **Миграций БД в патчах нет** (`prisma` — 0 вхождений).
- **Результаты:** `var/yummy-check/verify-result.json`, `var/yummy-check/baseline-compare.json`.

Хеши патчей — `automation/host/yummy-b016/PATCHES.sha256`. Проверки до и после выкладки
выполняет `automation/host/yummy-b016/yummy-b016-check.py`, только чтение. Значения издателя
и настроек он не печатает, сравнивает sha256. Коды выхода: 0 — норма, 1 — отклонение,
2 — не выполнено. Прогон на живом 15.10:
- `snapshot` — rc 0: 5 контейнеров healthy, `data-publisher-id` на странице у всех пяти, meta robots `index, follow`;
- два снимка подряд, `compare` — rc 0;
- `links` — rc 1 (дефект T081 на месте);
- `sitemaps` — rc 1 (дефект B016 на месте).

---

## Часть A. yummyani.site / .org / .biz — блок владельца

Выполняется пользователем с доступом к docker. На хосте это `claude`: `compose.vars`
принадлежит ему (0600). Каждая витрина выкладывается отдельно, в порядке biz → org → site.
Перед следующей витриной предыдущая должна пройти проверки.

### A0. Переменные и проверки до установки (ничего не меняют)

```bash
set -euo pipefail
FACTORY=/home/claude/wt-portable-site-cell-01
APP_REPO=/srv/sites/yummyani-staging/repo
BUILD_ROOT=/srv/sites/yummyani-staging/build-b016
ENV_FILE=/srv/sites/yummyani-staging/runtime/compose.vars
BASE_COMPOSE_DIR=/home/claude/wt-yummy-mail-biz
CHECK="python3 $FACTORY/automation/host/yummy-b016/yummy-b016-check.py"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
STATE_DIR=$FACTORY/var/yummy-b016/$STAMP
mkdir -p "$STATE_DIR"

cd "$FACTORY"
sha256sum -c automation/host/yummy-b016/PATCHES.sha256          # все четыре: OK
test "$(git -C "$BASE_COMPOSE_DIR" rev-parse --short=7 HEAD)" = 4c5796e
test -z "$(git -C "$BASE_COMPOSE_DIR" status --porcelain)"
grep -c '^WEB_\(SITE\|ORG\|BIZ\)_IMAGE=yummyani/web:rel-' "$ENV_FILE"   # 3: все три закреплены
docker inspect -f '{{.Name}} {{index .Config.Labels "org.opencontainers.image.revision"}}' \
  yummyani-staging-web-site-1 yummyani-staging-web-org-1 yummyani-staging-web-biz-1
# ожидается: site 054c6170519d…, org 8be8d8b5bdf2…, biz 4c5796eae24c…  Иначе — стоп: базы сменились,
# сборку надо перепроверить заново (сессия: var/yummy-check/verify_bases.py).
$CHECK snapshot "$STATE_DIR/before.json"                        # rc 0
```

### A1. Сборка трёх образов (контейнеры не трогаются)

Сборка переносит общий тег `yummyani/web:staging`. Это безопасно, пока все три витрины
закреплены своими `WEB_*_IMAGE`, а в A0 это проверено (`grep -c` = 3).

```bash
build_one() {  # build_one <база> <патч T081> → печатает тег rel-<sha12>
  local base="$1" t081="$2" wt="$BUILD_ROOT/$1" sha
  git -C "$APP_REPO" worktree add --detach "$wt" "$base"
  patch -d "$wt" -p1 --no-backup-if-mismatch -i "$FACTORY/var/yummy-patches/b016-sitemap-swr.patch"
  patch -d "$wt" -p1 --no-backup-if-mismatch -i "$FACTORY/var/yummy-patches/b016-sitemap-cap.patch"
  patch -d "$wt" -p1 --no-backup-if-mismatch -i "$FACTORY/var/yummy-patches/$t081"
  git -C "$wt" add -A
  git -C "$wt" -c user.name="yummy-b016" -c user.email="yummy-b016@localhost" commit -q \
    -m "B016/T081 поверх $base: карта без синхронной сборки и без потолка 8000; полки — канонические ссылки"
  sha=$(git -C "$wt" rev-parse HEAD)
  GIT_REVISION="$sha" docker compose -p yummyani-staging --project-directory "$wt" \
    -f "$wt/compose.staging.yaml" --env-file "$ENV_FILE" --profile build build web-build >&2
  test "$(docker image inspect yummyani/web:staging -f '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$sha"
  docker tag yummyani/web:staging "yummyani/web:rel-${sha:0:12}"
  echo "yummyani/web:rel-${sha:0:12}"
}
mkdir -p "$BUILD_ROOT"
IMAGE_SITE=$(build_one 054c6170519d t081-shelf-canonical-href.patch)
IMAGE_ORG=$(build_one 8be8d8b5bdf2 t081-shelf-canonical-href.patch)
IMAGE_BIZ=$(build_one 4c5796eae24c t081-shelf-canonical-href.4c5796e.patch)
printf 'IMAGE_SITE=%s\nIMAGE_ORG=%s\nIMAGE_BIZ=%s\n' "$IMAGE_SITE" "$IMAGE_ORG" "$IMAGE_BIZ" | tee "$STATE_DIR/images.env"
```

Для повторного запуска сначала уберите прежние рабочие копии сборки:
`git -C "$APP_REPO" worktree remove "$BUILD_ROOT/<база>"`.

### A2. Выкладка одной витрины

```bash
recreate() {  # recreate <web-site|web-org|web-biz> — та же команда, что подняла работающие контейнеры
  docker compose -p yummyani-staging --project-directory "$BASE_COMPOSE_DIR" \
    -f "$BASE_COMPOSE_DIR/compose.staging.yaml" \
    -f "$FACTORY/automation/host/yummy-biz-indexing.override.yaml" \
    -f "$FACTORY/automation/host/yummy-overlays.override.yaml" \
    --env-file "$ENV_FILE" up -d --no-deps --force-recreate "$1"
}
wait_healthy() {  # wait_healthy <контейнер>
  local deadline=$((SECONDS + 240)) state
  while :; do
    state=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$1")
    [ "$state" = healthy ] && return 0
    [ $SECONDS -gt $deadline ] && { echo "$1: $state — нет здоровья за 240 с" >&2; return 1; }
    sleep 3
  done
}
pin() {  # pin <ПЕРЕМЕННАЯ> <образ> — как pin_service_image в deploy.sh: строка заменяется целиком
  local tmp; tmp=$(mktemp)
  grep -v "^$1=" "$ENV_FILE" > "$tmp"
  printf '%s=%s\n' "$1" "$2" >> "$tmp"
  cat "$tmp" > "$ENV_FILE"
  rm -f "$tmp"
}
DEPLOYED=()
deploy_one() {  # deploy_one <service> <ПЕРЕМЕННАЯ> <образ> <домен>
  local svc="$1" var="$2" image="$3" domain="$4" ctr="yummyani-staging-$1-1"
  cp -p "$ENV_FILE" "$STATE_DIR/compose.vars.before-$svc"          # копия — без «|| true»
  docker tag "$(docker inspect -f '{{.Image}}' "$ctr")" "yummyani/web:rollback-b016-$svc"
  pin "$var" "$image"
  recreate "$svc"
  wait_healthy "$ctr"
  DEPLOYED+=("$svc")
  $CHECK snapshot "$STATE_DIR/after-$svc.json"
  $CHECK compare "$STATE_DIR/before.json" "$STATE_DIR/after-$svc.json" --changed "${DEPLOYED[@]}"
  $CHECK links "$domain"
  # Ключ Redis прежний: инвентарь отдаётся из кеша. Если ключ уже истёк, первый запрос —
  # единственная общая холодная сборка (35–57 с), поэтому первый проход — с пределом 90 с.
  $CHECK sitemaps --max-seconds 90 "$domain"
  $CHECK sitemaps --max-seconds 5 "$domain"
}
```

`compare` требует от выкладываемой витрины:
- образ сменился, контейнер healthy;
- у прочих четырёх контейнеров образ прежний;
- у всех пяти прежние переменные издателя/CDNVIDEOHUB, `SEO_INDEXING_ENABLED`, `TITLE_OVERLAYS_*`, `SITE_PROFILE` (по sha256) и монтирования;
- на странице тайтла прежний `data-publisher-id` (по sha256);
- прежний meta robots главной и тайтла.

Сравнение идёт с исходным снимком `before.json`, а `DEPLOYED` накапливает уже выложенные
витрины. Поэтому у них смена образа ожидается, у остальных — нет.

```bash
deploy_one web-biz WEB_BIZ_IMAGE "$IMAGE_BIZ" yummyani.biz
deploy_one web-org WEB_ORG_IMAGE "$IMAGE_ORG" yummyani.org
deploy_one web-site WEB_SITE_IMAGE "$IMAGE_SITE" yummyani.site
```

Под `set -e` первая же ненулевая проверка останавливает блок. После остановки откатывается
та витрина, на которой встали (A4); уже прошедшие проверки остаются.

### A3. Проверка, ради которой всё делается (через час, без прогрева)

Инвентарь живёт в Redis 3600 с. Проверка холодного пути — не раньше чем через 65 мин после
последнего пересоздания и при **остановленном** прогреве, иначе он замаскирует результат:

```bash
systemctl is-active yummy-sitemap-warm.timer && systemctl stop yummy-sitemap-warm.timer
# через ≥ 65 мин:
$CHECK sitemaps --max-seconds 5 yummyani.site yummyani.org yummyani.biz   # rc 0
$CHECK sitemaps --max-seconds 5 yummyani.site | grep titles.xml           # loc > 8000
$CHECK links                                                              # rc 0: --uuid 0 на трёх главных
```

Пустой обход провайдера не затирает исправный инвентарь, так задумано в SWR. Если
поставщик недоступен, карта отдаётся из прошлого инвентаря.

### A4. Откат одной витрины (только образ; данные не трогаются)

```bash
rollback_one() {  # rollback_one <service> <домен>
  local svc="$1" domain="$2"
  cp -p "$STATE_DIR/compose.vars.before-$svc" "$ENV_FILE"
  recreate "$svc"
  wait_healthy "yummyani-staging-$svc-1"
  test "$(docker inspect -f '{{.Image}}' "yummyani-staging-$svc-1")" = \
       "$(docker image inspect -f '{{.Id}}' "yummyani/web:rollback-b016-$svc")"
  $CHECK snapshot "$STATE_DIR/rollback-$svc.json"
}
```

После отката всех витрин `$CHECK compare "$STATE_DIR/before.json" "$STATE_DIR/rollback-web-site.json"`
даёт rc 0.

`deploy/staging/rollback.sh` **не применять**. Он восстанавливает базу из дампа, то есть
переписывает постоянные данные сайта из копии. Правила фабрики это запрещают, а патчи
БД не меняют: миграций нет. `compose.vars.before-*` — копия файла настроек выпуска,
снятая этим же блоком минутой раньше. Она возвращает только строку `WEB_*_IMAGE`.

---

## Часть B. yummyani7.site / .info — после фиксации compose Архитектором

Здесь причина 504 та же, и исправление — тот же образ, что у biz (`$IMAGE_BIZ`, база 4c5796e).
Но образ задан **литералом** в `deploy/compose.yaml` репозитория витрины. Сейчас этот файл у
yummyani7.site **незакоммичен**: рабочая копия Архитектора
`/home/claude/wt-nova-publish-memory-02/var/site-repos/yummyani7-site`, правка
`CDNVIDEOHUB_PUBLISHER_ID_PINNED`. Последний коммит 40a73ec называется «откат назначения
publisher_id: у Yummy объявление ломает запуск витрины».

Работающий контейнер уже несёт эту переменную. Пересоздание из закоммиченного файла её снимет,
а из незакоммиченного — закрепит то, что коммит 40a73ec откатывал. Решение за Архитектором,
поэтому порядок такой:

1. Архитектор фиксирует `deploy/compose.yaml` yummyani7-site и yummyani7-info в том виде, в
   каком они должны работать (с закреплением издателя или без него).
2. Отдельным коммитом в каждом — `image: <значение $IMAGE_BIZ>`.
3. Пересоздание только `web`, той же схемой проверок:

```bash
SITE_REPO=<репозиторий витрины yummyani7-site после шага 1–2>
$CHECK snapshot "$STATE_DIR/before-y7.json"
docker compose -p yummyani7-site -f "$SITE_REPO/deploy/compose.yaml" \
  --env-file /srv/sites/yummyani7-site/runtime/compose.vars up -d --no-deps --force-recreate web
wait_healthy yummyani7-site-web-1
$CHECK snapshot "$STATE_DIR/after-y7site.json"
$CHECK compare "$STATE_DIR/before-y7.json" "$STATE_DIR/after-y7site.json" --changed yummyani7-site-web-1
$CHECK sitemaps --max-seconds 90 yummyani7.site && $CHECK sitemaps --max-seconds 5 yummyani7.site
# то же для yummyani7-info (-p yummyani7-info, его compose и compose.vars)
```

**Откат:** `git revert` коммита с образом, затем то же пересоздание. Прежний образ
`rel-4c5796eae24c` остаётся на хосте.

Если Архитектор решит иначе (например, перевести yummyani7 на переменную образа, как у
staging), часть B меняется вместе с этим решением. Сессия её не выполняет.

---

## Временный прогрев — отдельно от устранения причины

`automation/host/yummy-sitemap/yummy-sitemap-warm.{sh,service,timer}`: каждые 5 минут
запрашивает все части карт пяти доменов.

- **Что даёт.** Робот почти всегда попадает в горячий кеш: 0,1–0,8 с вместо 504 или 40–57 с.
- **Чего не делает.**
  - Причину не устраняет: холодная сборка 35–57 с остаётся, её просто запускает таймер, а не робот.
  - На yummyani7.* сам проход прогрева получает 504, когда приходит на истёкший кеш (15.10: 01:11Z, 03:22Z). Следующий проход — 200.
  - Потолок 8000 не трогает.
  - T081 не касается.
- **Когда ставить.** Сейчас, до части A и B. С 15.10 ~03:36Z прогрева нет: его вела сессия, и он упёрся в предел фоновых задач. 07:53Z — холодные 504 на yummyani7.* и 40–48 с на остальных.

```bash
install -m 0644 /home/claude/wt-portable-site-cell-01/automation/host/yummy-sitemap/yummy-sitemap-warm.service \
  /home/claude/wt-portable-site-cell-01/automation/host/yummy-sitemap/yummy-sitemap-warm.timer /etc/systemd/system/
systemd-analyze verify /etc/systemd/system/yummy-sitemap-warm.service /etc/systemd/system/yummy-sitemap-warm.timer
systemctl daemon-reload && systemctl enable --now yummy-sitemap-warm.timer
systemctl list-timers yummy-sitemap-warm.timer --no-pager
```

**Снятие** — после A3 и B с rc 0, то есть когда холодный путь подтверждён без прогрева:

```bash
systemctl disable --now yummy-sitemap-warm.timer
rm /etc/systemd/system/yummy-sitemap-warm.service /etc/systemd/system/yummy-sitemap-warm.timer
systemctl daemon-reload
```
