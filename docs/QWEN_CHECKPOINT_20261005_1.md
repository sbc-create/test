# Checkpoint 2026-10-05 (1): один домен открыт, три ждут обновления исполнителя

Продолжение `docs/QWEN_CHECKPOINT_20261004_3.md`. Доказательства —
`docs/verification/eight-domains-20261004.md` и
`docs/verification/launch-lordserials22-20261005.md`.

## Что сделано

Согласие владельца зарегистрировано на четырёх доменах (якорь root:0444 +
объявление в реестре, идентификаторы совпадают).

| домен | релиз | режим | чем подтверждено |
| --- | --- | --- | --- |
| `lordserial33.biz` | `01164651b61f` | **OPEN** | `confirmed: true`, заявка `lords-02-idx-open` (`applied`), публичные проверки главной, раздела, карточки, robots.txt, карты и браузерного воспроизведения |
| `yummyani7.info` | `ec24cb7cfe97` | CLOSED | операция остановлена ДО единой записи |
| `yummyani7.site` | `676fd01329f1` | CLOSED | то же |
| `yummyani.biz` | `de93d72656c5` | CLOSED | то же |

## Единственный блокер трёх доменов Yummy

Установленная КОРНЕВАЯ копия исполнителя старше операции:

    grep ОПЕРАЦИИ /usr/local/lib/site-factory-cell/factory/cell/queue.py
    -> ("activate","update","deliver","rollback","editorial","access-check",
        "indexing-nginx","owner-consent")          # indexing-core нет
    ls /usr/local/lib/site-factory-cell/factory/cell/indexing_core.py
    -> No such file or directory

Отказ наступил до записи: домен остался CLOSED, запись реестра ядра не
тронута (`policy_revision 1`, `owner_authorization_id BOOTSTRAP-CLOSED`).

Нужна одна команда владельца — обновление корневой копии:

    sudo bash /home/claude/wt-portable-site-cell-01/automation/host/install-cell-executor.sh

Сухой прогон этой команды выполнен: доходит до конца, ничего не меняет.
Повторная установка — штатный способ обновить исполнителя (так он и
задуман: правка в рабочем каталоге не должна становиться исполнением от root).

После неё открытие трёх доменов идёт без новых согласий и без новых выпусков:

1. `indexing-set --mode open` (операция сама подаст заявку `<site>-core-open`
   и перезапустит юнит — режим резолвится при импорте точки входа);
2. `confirm_indexing`;
3. карта: у Yummy ждать `sitemapindex` вместо пустого `urlset`;
4. воспроизведение переподтверждать не нужно — проверено в браузере на всех
   трёх до открытия и от режима индексации не зависит.

## Запуск lordserials22.site и lordserials22.space

Состояние и доказательства — `docs/verification/launch-lordserials22-20261005.md`.
Коротко: оба домена отвечают `NXDOMAIN` от авторитетного сервера зоны TLD, то
есть имён нет в родительской зоне; сервер размещения —
**45.131.182.225** (подтверждён инвентарём и A-записями семи работающих
доменов проекта).

Порядок (каждый шаг зависит от предыдущего):

1. владелец, root — юниты и nginx:

       sudo bash /home/claude/wt-portable-site-cell-01/automation/host/launch-new-site.sh --site lords-06
       sudo bash /home/claude/wt-portable-site-cell-01/automation/host/launch-new-site.sh --site lords-07

   Шаг HTTPS внутри будет ПРОПУЩЕН с названной причиной: без записи DNS
   `certbot` подтвердить владение не может. Это не отказ установки.

2. я — выпуск через очередь исполнителя и проверка доступности ЧЕРЕЗ ЦЕЛЕВОЙ
   СЕРВЕР до переключения DNS (`curl --resolve` с заголовком Host на
   45.131.182.225). Индексация остаётся закрытой: `indexing` в пакете пуст;
3. владелец — записи DNS (таблица в отчёте);
4. владелец, root — сертификат:

       sudo bash /home/claude/wt-portable-site-cell-01/automation/host/install-site-tls.sh --site lords-06
       sudo bash /home/claude/wt-portable-site-cell-01/automation/host/install-site-tls.sh --site lords-07

5. я — проверка HTTPS, затем разрешение выпуска отдельным выпуском ПОСЛЕ
   проверки реализации, регистрация согласия владельца, штатное открытие и
   live-подтверждение.

## Найденный дефект учёта, не исправленный сознательно

`config/site-cells.json: cells[].indexing.desired_state` НЕ поддерживается
операцией и расходится с фактом: у `lords-05` (домен открыт и отдаёт
`index, follow`) там записано `CLOSED`, у `lords-01`, `lords-02` и `zona-02`
(тоже открыты) поля нет вовсе. Авторитетны файл состояния `/srv/sites/indexing/`
и реестр ядра у Yummy, а это поле — устаревшее зеркало.

Почему не исправлено здесь: писать его из операции значит писать в файл,
который в тот же момент перезаписывает `authorize-indexing.sh` целиком (с
резервными копиями), — гонка потеряла бы чужие записи. Варианты: либо
маршрутизировать запись через привилегированную операцию, либо убрать поле из
схемы как необязательное зеркало. Решение за владельцем; подставлять значение
«чтобы совпало» нельзя — это и есть дефект учёта.
