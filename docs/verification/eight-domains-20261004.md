# Восемь production-доменов: что измерено 2026-10-04

Задание владельца: довести оставшиеся восемь production-доменов до
подтверждённого OPEN штатными средствами. Этот файл — доказательная база
отчёта: только измерения, с командами и путями. Там, где результат не
получен, так и написано.

## 1. Что оказалось настоящим блокером у каждого

| домен | site_id | измерено | блокер |
| --- | --- | --- | --- |
| `lordserial33.biz` | lords-02 | `current -> b929041cc0b9`, читатель режима и читатель правок в выпуске, карта подключена слоем | согласие владельца не зарегистрировано (нужен root) |
| `yummyani7.info` | yummy-08 | ячейка на порту 9115, `current -> ec24cb7cfe97`, режим решает `src/nova_core_indexability.py` | то же |
| `yummyani7.site` | yummy-07 | ячейка на порту 9114, `current -> 676fd01329f1` | то же |
| `yummyani.biz` | yummy-biz | ячейка на порту 9130, `current -> de93d72656c5` | то же |
| `an1mego.site` | animego-02 | жива, `build animego-02-32f05a208b1e`, обслуживается из `/srv/an1mego-site/app` (13 файлов), `managed_by: monolith`, реестр прямо говорит «Отсюда не выкладывается» | сайт ВНЕ очереди выпуска: ни рабочей копии, ни профиля шаблона, ни пути выкладки |
| `animeg0.site` | animego-03 | то же устройство, порт 9151 | то же |
| `lordserials22.site` | lords-06 | `socket.gethostbyname` -> `gaierror`, `/srv/lordserials22-site/app` пуст, `current` нет, порт 9116 не слушается | домена нет в DNS и выпуска нет: сайт не запускался |
| `lordserials22.space` | lords-07 | то же, порт 9117 | то же |

Механизм режима в выложенном коде четырёх последних доменов искался
командой `grep -rlc "indexing_mode\|режим_индексации\|nova_core_indexability"`
по каталогу выкладки — НЕ НАЙДЕН ни у одного.

## 2. Семейство Yummy: механизм найден, подключён, доказан

Прежняя запись контракта называла единственной формой контейнерную. Измерение
на хосте:

    /etc/nginx/cells/yummy-biz.upstream -> server 127.0.0.1:9130
    /etc/nginx/cells/yummy-07.upstream  -> server 127.0.0.1:9114
    /etc/nginx/cells/yummy-08.upstream  -> server 127.0.0.1:9115
    /etc/nginx/cells/yummy-org.upstream -> server 127.0.0.1:9131
    /etc/nginx/cells/yummy-site.upstream -> server 127.0.0.1:9132

Все пять домена — ЯЧЕЙКИ. Каждый выпуск объявляет один и тот же реестр:

    grep INDEXING_CORE_REGISTRY /srv/yummyani*/current/config/site.json
    -> /srv/lords/.frontend/indexing-core-registry.json  (во всех пяти)

Записи этого файла и есть режим: `yummyani.site` и `yummyani.org` имеют
`desired_state: OPEN` и отдают страницы БЕЗ `X-Robots-Tag`, остальные три —
`CLOSED` и отдают `noindex, nofollow`. Это доказательство механизма от конца
до конца, полученное на работающих production-доменах, а не на стенде.

Подключение к штатной операции: `factory/cell/indexing_core.py` +
операция `indexing-core` исполнителя. Проба записи (без изменения файла):

    python3 -c "...indexing_core.переписать(..., dry_run=True)"
    -> verified_by /srv/yummyani7-info/current/src/nova_core_indexability.py
       after: desired_state OPEN, policy_revision 2
       untouched: yummyani.biz, yummyani.org, yummyani.site, yummyani7.site

## 3. Выпуски, сделанные штатным исполнителем

| заявка | исход | этап | build |
| --- | --- | --- | --- |
| `yummy-08-code-ec24cb7cfe97` | ok / activated | live_verified | `ec24cb7cfe97-yummy-08` |
| `yummy-07-code-676fd01329f1` | ok / activated | live_verified | `676fd01329f1-yummy-07` |
| `yummy-biz-code-de93d72656c5` | ok / activated | live_verified | `de93d72656c5-yummy-biz` |
| `lords-02-code-b929041cc0b9` | ok / activated | live_verified | `b929041cc0b9-lords-02` |

Перед выпусками потребовалась свежая проверка доступа
(`refresh_executor_access`): предыдущая была 125 ч назад, и план выпуска
останавливался на этом, а не на коде.

CI всех четырёх ветвей зелёный: прогоны 37233056362, 37233059981,
37233064430 (три Yummy) и 37233872666 (lords-02).

## 4. Вердикты готовности после выпусков

    lordserial33.biz | AWAITING_OWNER | выпуск разрешает True | владелец False | пробел None
    yummyani7.info   | AWAITING_OWNER | выпуск разрешает True | владелец False | пробел None
    yummyani7.site   | AWAITING_OWNER | выпуск разрешает True | владелец False | пробел None
    yummyani.biz     | AWAITING_OWNER | выпуск разрешает True | владелец False | пробел None

`release_gap: None` и пустой список блокеров означают: технически готово всё,
кроме акта владельца в каталоге root.

## 5. Карта сайта

| домен | состояние | чем решено |
| --- | --- | --- |
| `lordserial33.biz` | `/sitemap.xml` -> 404 при закрытом домене (fail-closed), сборщик и слой в выпуске | общее семейное решение: слой `lords_sitemap_layer` в файлах сайта, ядро не правится |
| `yummyani7.info` | `/sitemap.xml` -> 200, пустой `<urlset>` при закрытом домене | решение семейства УЖЕ есть и привязано к режиму: у открытого `yummyani.org` тот же адрес отдаёт `sitemapindex` с пятью картами |
| `yummyani7.site`, `yummyani.biz` | то же | то же |

Разделы `lordserial33.biz` для карты измерены ответами: `/movies/`,
`/series/`, `/animation/`, `/anime/`, `/dorama/` -> 200; `/tv/` -> 404 и в
карту не попал.

## 6. Воспроизведение видео в браузере

`automation/local/playback-check.py` — Chromium, обход теневых корней,
решение по состоянию `<video>`, а не по коду ответа провайдера.

| домен | карточка | currentTime | итог |
| --- | --- | --- | --- |
| `lordserial33.biz` | `/title/100-atletov-meksika/` | 0.11 -> 23.74 | ИДЁТ, 1280x720 -> 1920x1080 |
| `yummyani7.info` | `/anime/chernyy-klever-2` | 0.10 -> 23.23 | ИДЁТ, 4 медиа-ответа |
| `yummyani7.site` | `/anime/mastera-mecha-onlayn-...` | 0.09 -> 23.01 | ИДЁТ, 4 медиа-ответа |
| `yummyani.biz` | `/anime/nesmotrya-na-to-chto-...` | 0.10 -> 24.23 | ИДЁТ, 4 медиа-ответа |
| `yummyani.org` (контроль, уже открыт) | `/anime/chernyy-klever-2` | 0.10 -> 24.27 | ИДЁТ |

Две правки самой проверки, без которых она давала ЛОЖНЫЙ отрицательный ответ
на всём семействе Yummy, и обе — измерения, а не догадки:

1. форма адреса карточки у семейств РАЗНАЯ. Зашитый `/title/` на Yummy не
   находил ссылок вовсе: там карточка живёт по `/anime/<slug>`, а
   `/title/<slug>/` отвечает 308. Префикс берётся из той же проверенной
   таблицы, что `registry.ФОРМА_АДРЕСА`;
2. щелчок по центру кадра со СТРАНИЦЫ до плеера Yummy не доходит. Замер на
   `yummyani.org` (домен открыт и работает): кадр плеера загружен, в нём
   `VK-VIDEO-PLAYER` с настоящим источником («Серия 1, Многоголосый»), а
   элемента `<video>` нет вовсе — плеер VK создаёт его при запуске. Теперь
   при отсутствии `<video>` после щелчка нажимается кнопка запуска ВНУТРИ
   кадра. Щелчок по центру оставлен первым: у семейства Lords работает он.

Ответ провайдера HTTP 200 воспроизведением здесь не считается нигде: вывод
делается по растущему `currentTime` и `readyState == 4`.

## 7. Отдельные находки, не входящие в задание

1. `checks/lords02-taxonomy` у `lordserial33.biz` ОТКАЗЫВАЕТ локально: в живом
   снимке каталога 17 новых рассогласований классификации (запись имеет
   идентификатор аниме-базы, но жанра аниме нет и случай не разобран в
   `config/classification-overrides.json`): `roza-2`, `stich-i-ay`,
   `geroy-vnutri`, `oazis-oskara`, `patrul-dino-...` и ещё 12. В CI проверка
   не воспроизводится: она читает снимок из `/srv`, которого там нет. К
   правкам этого задания отношения не имеет — это дрейф данных конвейера.
2. Доступность серий у семейства Lords берётся из явного перечня номеров
   (`nums`), и спецвыпуск с номером 0 при этом сохраняется. Но измерение
   2026-09-29 показало: в снимках конвейера перечней `nums` нет вовсе, и
   действует прежний смысл `avail` — «серии с первой по avail». Для тайтлов,
   отсутствующих в файле наложения номеров, серия 0 и пропуски нумерации
   по-прежнему недостижимы. Механизм наложения существует и работает;
   недостаёт данных конвейера.
