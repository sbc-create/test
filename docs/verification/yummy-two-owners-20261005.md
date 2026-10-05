# Yummy: у режима индексации два владельца. Измерено 2026-10-05

Задание: открыть `yummyani.biz`, `yummyani7.info`, `yummyani7.site` штатной
операцией после обновления корневой копии исполнителя. Один домен открыть не
удалось, два не открывались; причина установлена и доказана.

## 1. Установленный исполнитель операцию поддерживает

    grep ОПЕРАЦИИ /usr/local/lib/site-factory-cell/factory/cell/queue.py
    -> (..., "indexing-nginx", "indexing-core", "owner-consent")
    ls /usr/local/lib/site-factory-cell/factory/cell/indexing_core.py  -> есть
    sha256 indexing_core.py, executor.py, queue.py, protected.py
    -> совпадают с репозиторием ПОБАЙТОВО

Операция исполнилась по-настоящему, и это проверено не текстом ошибки, а
файлом результата: `started_at 2026-10-05T07:41:00`, то есть новая попытка, а
не прежний `rejected`. Прежние отказы в тексте сообщения операции —
действительно СТАРЫЕ; разбирать их по времени начала обязательно.

## 2. Что произошло на yummyani.biz

Операция сделала свою часть:

* запись реестра ядра переписана: `desired_state OPEN`, ревизия 2,
  `owner_authorization_id 52799b26-…` (из якоря согласия владельца);
* юнит перезапущен, `/healthz` ответил за 3 с;
* заголовок `X-Robots-Tag: noindex, nofollow` ИСЧЕЗ.

И отказалась считать режим применённым:

    yummy-biz: реестр переписан и юнит перезапущен, а приложение на порту 9130
    по-прежнему отдаёт X-Robots-Tag None. Режим не применён

Причина — в ТЕЛЕ страницы:

    https://yummyani.biz/   -> <meta name="robots" content="noindex, follow">
    https://yummyani.org/   -> <meta name="robots" content="index, follow">
    https://yummyani.site/  -> <meta name="robots" content="index, follow">

## 3. Откуда берётся тег в теле

Ячейка Yummy — ПРОКСИ перед контейнером Next.js:

    /srv/yummyani-biz/current/config/site.json
      environment.LORDS_LEGACY_UPSTREAM = 127.0.0.1:3103

Запрос напрямую в контейнеры, минуя ячейку:

    127.0.0.1:3103 (yummyani-staging-web-biz-1)  -> noindex, follow
    127.0.0.1:3102 (yummyani-staging-web-org-1)  -> index, follow

Их переменные (`docker inspect`, то есть ФАКТИЧЕСКИ запущенное):

| домен | контейнер | служба | SEO_INDEXING_ENABLED | compose |
| --- | --- | --- | --- | --- |
| yummyani.site (открыт) | `yummyani-staging-web-site-1` | web-site | **true** | `/home/claude/wt-yummy-actual-shelf-01` |
| yummyani.org (открыт) | `yummyani-staging-web-org-1` | web-org | **true** | `/home/claude/wt-yummy-mail-org` |
| yummyani.biz | `yummyani-staging-web-biz-1` | web-biz | **false** | `/home/claude/wt-yummy-mail-biz` |
| yummyani7.info | `yummyani7-info-web-1` | web | **false** | `var/site-repos/yummyani7-info/deploy` |
| yummyani7.site | `yummyani7-site-web-1` | web | **false** | `var/site-repos/yummyani7-site/deploy` |

Вывод: у режима ДВА владельца. Ячейка решает заголовок и `robots.txt` по
реестру ядра; тело страницы решает контейнер по `SEO_INDEXING_ENABLED`.
Открытым домен является только при согласии обоих — именно поэтому у двух
открытых доменов переменная равна `true`.

## 4. Моя ошибка и её исправление

Первой правкой я заставил ячейку ПОДМЕНЯТЬ тег в теле по своему режиму, то
есть в том числе снимать чужой `noindex`. Это неверно: витрина противоречила бы
приложению, которое страницу и отдаёт, а расхождение двух владельцев стало бы
невидимым вместо того, чтобы быть названным. Правка переделана на
односторонность: ячейка вправе только ДОБАВИТЬ запрет, когда закрыта сама.

## 5. Два дефекта, найденных по пути, и оба исправлены

1. `nginx: [emerg] unknown "cell_robots_yummy_biz" variable`. Объявление
   `map` ставилось в `/etc/nginx/sites-available/yummyani.biz.conf` — файл,
   который nginx не включает, — а использование переменной в загружаемый
   `sites-enabled`. Откат отработал верно: конфигурации восстановлены,
   перезагрузки не было, соседние домены не задеты. `sites-available` исключён
   из «живых» каталогов (D170). Исправление в корневой копии исполнителя ещё
   НЕ установлено.
2. Проверка запрета в теле искала слово `noindex` подстрокой; во встроенном
   JSON приложения есть `"noindex":false`. Теперь разбирается сам тег (D171).

## 6. Теневые конфигурации nginx: НЕ устранено

`nginx.conf` включает `sites-enabled/*` без фильтра, и четыре резервные копии
загружаются как конфигурация:

    /etc/nginx/sites-enabled/yummyani.biz.conf.bak.20260910T093711Z
    /etc/nginx/sites-enabled/yummyani.org.conf.bak.20260910T0940Z
    /etc/nginx/sites-enabled/yummyani.site.conf.bak.20260910T0940Z
    /etc/nginx/sites-enabled/yummyani.site.conf.bak.cr06.20260920T203413Z

Каждая объявляет те же `server_name` на тех же портах. Сейчас порядок спасает:
`yummyani.biz.conf` сортируется раньше `…conf.bak.…`, и выигрывает рабочий
файл — что подтверждено фактическими ответами (`X-Site-Factory-Build-Id`
называет ячейку, а не прежний маршрут). Но копии содержат ПРЕЖНИЙ маршрут
прямо в контейнер, и любое имя, которое отсортируется раньше рабочего, молча
вернёт трафик на старый адрес.

Проблема НЕ устранена: убрать копии из загрузки может только root —
`sudo bash automation/host/nginx-shadow-configs.sh --fix` (переносит в
`/var/backups` с сохранением пути, `nginx -t` до reload, при отказе возвращает).

Кроме того у трёх витрин Yummy есть незагружаемые двойники в
`sites-available`, уже РАСХОДЯЩИЕСЯ с рабочими файлами (sha256 различаются у
всех трёх). Это отдельный учётный долг; он назван, но не правится.
