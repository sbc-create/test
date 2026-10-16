# Десять редакционных посадочных Yummy закрыты своей же политикой: причина, правка, проверка

Запись от 2026-10-16. Семейство Yummy даёт 90 % трафика сети, поэтому
причину искала там, где трафик есть. Нашла закрытую поверхность, которую сайт
уже построил и опубликовал.

## 1. Что измерено на живых страницах

15.10 21:05, по всем трём образам семейства (`rel-c23018dd4a3a` на
`yummyani.site`, `rel-536082c25e7e` на `.org`, `rel-a520a24afb20` на `.biz` и
обоих контурах `yummyani7`):

| страница | код | карточек | robots |
| --- | ---: | ---: | --- |
| `/catalog/genre/comedy` | 200 | 24 | **noindex, follow** |
| `/catalog/genre/drama` | 200 | 24 | **noindex, follow** |
| `/catalog/genre/fantasy` | 200 | 24 | **noindex, follow** |
| `/catalog/genre/action` | 200 | 24 | **noindex, follow** |
| `/catalog/genre/romance` | 200 | 24 | **noindex, follow** |
| `/catalog/collection/seasonal-watchlist` | 200 | 24 | **noindex, follow** |
| …ещё четыре коллекции | 200 | 24 | **noindex, follow** |

В `/sitemap/static.xml` — 20 адресов: главная, шесть разделов каталога,
`/sitemap`, `/pages/faq`, `/posts` и статьи. **Ни одной посадочной.**

То есть десять страниц с уникальным вступлением и живой выборкой не
предъявлены поиску вообще: ни тегом, ни картой.

## 2. Причина — в коде, и это снова мера не про то

* строки матрицы `genre-landing` и `collection-landing` параметрические:
  `urlPattern: "/catalog/genre/{genreSlug}"` и
  `"/catalog/collection/{collectionSlug}"` (`src/site-blueprint/page-matrix.ts:353`
  и `:371`), литерального `path` у них нет;
* `staticIndexablePaths("curated")` собирает ТОЛЬКО строки с литеральным
  `path` (`page-matrix.ts:1120`), значит параметрические в этот список не
  попадают никогда;
* `isIndexable` разрешает посадочную единственным предикатом «путь лежит в
  этом статическом списке» (`src/lib/seo/policy.ts:105`).

Матрица при этом объявляет этим же строкам `robotsPolicy: INDEX_ROBOTS`,
`indexability: "only allowlisted curated landings"` и
`sitemapEligible: "when-indexable"`. Разрешение, по смыслу, выдаёт allowlist
(`src/site-blueprint/curated-landings.ts` — десять записей, все `enabled`), а
спрашивают статический список. Правило и проверка разошлись: функция честно
отвечает на свой вопрос, только это не тот вопрос.

Тот же разрыв держал красными три утверждения тестов, написанных, когда
allowlist был пуст. Прогон на НЕПРАВЛЕНОЙ копии выпущенного кода
(`/home/claude/wt-yummy-mail-biz`, `vitest run`, 15.10 21:15):

```
Test Files  3 failed | 66 passed (69)
     Tests  4 failed | 591 passed (595)     exit 1
```

* `page-matrix.test.ts:108` — `expect(CURATED_LANDING_ALLOWLIST).toEqual([])`
  при десяти записях;
* `page-matrix.test.ts:42` — в `docs/SEO-PAGE-MATRIX.md` нет строки
  `collection-landing` (документ не перегенерировали);
* `genre-canonical.test.ts:49` — `isGenreLandingIndexable("drama", 10)`
  ожидался `false`;
* `portal-data.test.ts` — «expected 'editorial' to be 'old.yummyani.me'»,
  к посадочным отношения не имеет; **существовал до правки и остаётся**, он
  записан отдельно.

## 3. Правка (подготовлена, не опубликована)

Восемь файлов, диффы — `var/yummy-landings/{src,tests,docs}.diff` в рабочей
копии `wt-nova-publish-memory-02`; та же папка скопирована в общий чекаут.

1. `src/lib/seo/policy.ts` — `allowlistedLanding()` и
   `ALLOWLISTED_LANDING_PATHS`: разрешение даёт allowlist. Маршрутизированы
   только два вида (`genre`, `collection`); `year`, `type`, `status` страниц не
   имеют и индексируемыми не становятся.
2. `src/lib/seo/sitemap.ts` — те же пути попадают в `xmlSitemapPaths`.
3. `src/app/catalog/genre/[genreSlug]/page.tsx` — метаданные считают
   `hasUsefulContent` по живой выдаче через `isGenreLandingIndexable`:
   посадочная без карточек остаётся закрытой, тонкая страница не открывается.
4. `src/app/catalog/collection/[collectionSlug]/page.tsx` — то же правило.
5. `tests/unit/page-matrix.test.ts` — утверждение переведено на измеренный
   факт: каждая включённая посадочная индексируема и есть в карте, пустая —
   нет, неизвестный slug, вложенный путь и фильтр `?genre=` — нет.
   `staticIndexablePaths("allowlist")` по-прежнему `[]`, и рядом сказано,
   почему это и есть причина дефекта.
6. `tests/unit/genre-canonical.test.ts` — `drama` с карточками индексируема,
   без карточек — нет; `dunhua` закрыт, как и был.
7. `tests/unit/seo.test.ts` — ожидаемая карта сайта содержит десять
   посадочных перечислением (allowlist — редакционное решение, его изменение
   должно быть видно правкой теста).
8. `docs/SEO-PAGE-MATRIX.md` — добавлена строка `collection-landing`; у
   `genre-landing` колонка httpStatus приведена к значению из кода.

Ни одно утверждение не удалено и не ослаблено: каждое поменяло сторону вместе
с фактом, и рядом появилась проверка обратного случая.

## 4. Проверка правки

Прогон полного набора на копии выпущенного дерева с наложенной правкой
(`vitest run`, 16.10 06:54):

```
Test Files  4 failed | 68 passed (72)
     Tests  3 failed | 583 passed (586)     exit 1
```

Три красных — не от правки, и это проверено по именам:

* `env.test.ts` и `publisher-id.test.ts` требуют `.env.example`, а
  `public-https-deploy.test.ts` — `deploy/public/publish-yummy.sh`: этих файлов
  в лабораторной копии нет, скопировать `.env.example` запретил hook
  («обращение к секретному пути»). Это артефакт копии, не кода;
* `portal-data.test.ts` — тот же красный, что был до правки.

Все три прежних утверждения про посадочные — зелёные. Типы:
`tsc --noEmit` даёт 17 ошибок, все — `Cannot find name 'PageProps'/'LayoutProps'`
(кодогенерация Next в лабораторной копии отсутствует); ни одной в правленых
файлах.

## 5. Чего правка НЕ делает и что остаётся

* прироста визитов не обещает. Она открывает десять страниц под жанровый и
  подборочный спрос; переходы считаются после индексации, а индекс не
  измеряется (B023). Проверка эффекта — показы жанровых страниц через 7 и
  28 суток, и она зависит от доступа к Вебмастеру;
* **мягкий 404** остаётся отдельным дефектом (MOD-44): `/catalog/genre/mecha`
  и `/catalog/collection/net-takoy-nikogda` отвечают 200 с телом «недоступно»,
  хотя матрица объявляет 404, а код вызывает `notFound()` — статус уходит
  раньше, чем срабатывает отказ (маршрут `force-dynamic`, ответ стримится).
  Пока страницы закрыты, вред ограничен; после этой правки мягкий 404
  становится видимым поиску, поэтому его надо закрыть в том же выпуске;
* публикация требует сборки образа в репозитории приложения
  (`sbc-create/yummyani`), а git-операции этой сессии ограничены её рабочей
  копией. Выпуск — линия приложения; порядок как у части A/B: канарейка
  `yummyani7.site` → `.info` → `.org`, `.biz` → `yummyani.site`.

## 6. Передача (репозиторий, копия, ветка, коммит)

| что | значение |
| --- | --- |
| репозиторий приложения | `sbc-create/yummyani` (`/srv/sites/yummyani-staging/repo`) |
| дерево, по которому сделана правка | `/srv/sites/yummyani-staging/build-b016/20261015T171031Z/21184803b90f`, коммит `a520a24afb20` (образ `rel-a520a24afb20`) |
| диффы | `var/yummy-landings/src.diff`, `tests.diff`, `docs.diff` |
| моя копия и ветка | `/home/claude/wt-nova-publish-memory-02`, `claude/nova-publish-memory-02` |
| запись в очереди | `var/seo-tech-results/results-20261016T0700Z.json` |

Коммита в репозитории приложения нет намеренно: ветку там эта сессия не
создаёт. Правка накладывается `git apply` на ревизию `a520a24afb20` или на
текущую ветку выпуска — файлы менялись только в перечисленных местах.
