# Checkpoint 2026-10-05 (2): три домена открыты, один ждёт двух действий

Продолжение `docs/QWEN_CHECKPOINT_20261005_1.md`. Доказательства —
`docs/verification/yummy-two-owners-20261005.md`.

## Открыто и подтверждено

| домен | релиз | request_id | подтверждение |
| --- | --- | --- | --- |
| `lordserial33.biz` | `01164651b61f` | `lords-02-idx-open` | `confirmed: true`, карта 57 004 адреса, плеер, служебные пути закрыты |
| `yummyani7.info` | `cfc852f445b3` | `yummy-08-core-open` + `yummy-08-idx-open` | `confirmed: true`, карта 7615 адресов, плеер |
| `yummyani7.site` | `69fb5cd571cf` | `yummy-07-core-open` + `yummy-07-idx-open` | `confirmed: true`, карта 7616 адресов, плеер |

## Чего не хватает `yummyani.biz`

Домен возвращён в исходное CLOSED заявкой `yummy-biz-core-closed-restore`
(`applied`, ревизия 5). Для открытия нужны ДВА действия владельца:

1. **второй владелец режима** — `SEO_INDEXING_ENABLED: "true"` для службы
   `web-biz` в проекте `/home/claude/wt-yummy-mail-biz` и пересоздание
   контейнера. Compose этого домена лежит в ЧУЖОМ рабочем каталоге, поэтому я
   его не правлю. У двух доменов `yummyani7` то же сделано мной: их compose
   лежит в их собственных репозиториях, пересоздание выполнено
   `docker compose -p <проект> --env-file /srv/sites/<учётка>/runtime/compose.vars up -d --no-deps web`
   (секрет остаётся в файле, фабрика его не читает);

2. **обновление корневой копии исполнителя** — иначе слой nginx не
   переключится:

       sudo bash /home/claude/wt-portable-site-cell-01/automation/host/install-cell-executor.sh

   В ней ещё нет исправления D170: объявление `map` попадало в
   `sites-available` — файл, который nginx не читает, — и переключение
   отказывало с `unknown "cell_robots_yummy_biz" variable`.

## Теневые конфигурации nginx: НЕ устранено

Четыре резервные копии загружаются как конфигурация (`include
sites-enabled/*` без фильтра), каждая объявляет те же `server_name`:

    yummyani.biz.conf.bak.20260910T093711Z
    yummyani.org.conf.bak.20260910T0940Z
    yummyani.site.conf.bak.20260910T0940Z
    yummyani.site.conf.bak.cr06.20260920T203413Z

Сейчас порядок спасает (рабочее имя сортируется раньше), и фактические ответы
это подтверждают. Убрать из загрузки:

    sudo bash /home/claude/wt-portable-site-cell-01/automation/host/nginx-shadow-configs.sh --fix

Отдельно: у трёх витрин Yummy есть незагружаемые двойники в `sites-available`,
уже разошедшиеся с рабочими файлами по sha256. Названо, не правится.

## Известная характеристика, не дефект выпуска

Первый запрос к `/sitemap/titles.xml` после перезапуска ячейки Yummy шёл
54,9 с и упирался в 30-секундный таймаут nginx (`504`). Контейнер при этом
отвечал за 0,2 с. Прогретый ответ — 0,2 с и 7615/7616 адресов. Кандидат на
улучшение: прогревать карту вместе с семейными страницами.

## Остаётся из прежнего задания

`lordserials22.site` и `lordserials22.space`: запуск ждёт двух команд владельца
(`launch-new-site.sh --site lords-06` и `--site lords-07`) и записей DNS —
таблица в `docs/verification/launch-lordserials22-20261005.md`.
