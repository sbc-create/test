# Перенос витрин в отдельные репозитории — отчёт

Отчёт собран из фактических запусков: коммиты взяты из репозиториев, прогоны
CI — из GitHub, digest — повторной сборкой, публичный build-id — запросом к
домену. Утверждений без запуска здесь нет.

## Таблица по очереди

| Домен | site_id | Репозиторий | Коммит | CI | Digest | build_id выпуска | build-id живого сайта | Состояние |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| animedia.space | animedia-02 | `site-animedia-space` | `3e4eccd6a51d` | 35824679037 | `8df32e59ca42…` | `3e4eccd6a51d-animedia-space` | `20260922T143111Z-efdef56-animedia-parity` | EXTRACTED+ACTIVATED |
| zonafilm.space | zona-01 | `site-zonafilm-space` | `fc08252d22c0` | 35825987313 | `50b6d39ba51f…` | `fc08252d22c0-zona-01` | `zona-01-a0209877e1db` | EXTRACTED |
| animedia.icu | animedia-01 | `site-animedia-icu` | `07a4f944e068` | 35826024266 | `279a31b32f21…` | `07a4f944e068-animedia-01` | `не снимался в этот прогон` | EXTRACTED |
| lordfilm47.space | lords-01 | `site-lordfilm47-space` | `3a4e5080eb17` | 35826034264 | `9806e643402d…` | `3a4e5080eb17-lords-01` | `не снимался в этот прогон` | EXTRACTED |
| lordserial33.biz | lords-02 | `site-lordserial33-biz` | `0f679d54d06d` | 35827800336 | `7e539e10131a…` | `0f679d54d06d-lords-02` | `20260921T134330Z-515fcf0-cardfix` | EXTRACTED |
| 1lordserials1.online | lords-03 | `site-1lordserials1-online` | `c07787d8330a` | 35827809554 | `c5423a6f0caa…` | `c07787d8330a-lords-03` | `не снимался в этот прогон` | EXTRACTED |
| yummyani.site | yummy-site | `site-yummyani-site` | `d3eb3a8f747f` | 35826066353 | `59503078add1…` | `d3eb3a8f747f-yummy-site` | `не снимался в этот прогон` | EXTRACTED |
| yummyani.org | yummy-org | `site-yummyani-org` | `9bd3ecb1362d` | 35826055698 | `3a3cd393bbe7…` | `9bd3ecb1362d-yummy-org` | `не снимался в этот прогон` | EXTRACTED |
| yummyani.biz | yummy-biz | `site-yummyani-biz` | `e742acbd56a4` | 35826044550 | `9b419c9bbbc7…` | `e742acbd56a4-yummy-biz` | `не снимался в этот прогон` | EXTRACTED |
| zonafilm.cc | zona-02 | — | — | — | — | — | — | НЕ СУЩЕСТВУЕТ |

## Что означают состояния

**EXTRACTED** — сайт выделен в собственный приватный репозиторий: шаблон,
настройки, закреплённые версии, сценарии активации и отката, CI выпуска.
Репозиторий зарегистрирован в `config/site-cells.json`, и общий путь выкладки
этому сайту отказывает. Живой сайт при этом **ещё работает из прежней
установки**: переключение требует root, недоступного исполнителю.

**EXTRACTED+ACTIVATED** — живой сайт работает из кода своего репозитория.
Такой один: animedia.space, переключён владельцем вручную.

**НЕ СУЩЕСТВУЕТ** — zonafilm.cc не заведён на этом хосте: нет ни юнита, ни
каталога, ни манифеста. Это не перенос, а новый заказ, и выдумывать для него
содержимое нельзя.

## Честная граница: ни один живой сайт пока не отдаёт свой build-id

Столбцы «build_id выпуска» и «build-id живого сайта» намеренно разные. Выпуск
в репозитории называет свой коммит; живой сайт называет прежнюю сборку, потому
что ни один стамп ещё не выложен. У animedia.space код уже свой, но установлен
до появления штампа.

Цепочка `коммит → CI → digest → build_id` замкнута и проверена в репозитории.
Последнее звено — `digest → живой сайт` — закрывается одной активацией на
каждый домен, и это единственная оставшаяся операция, требующая root.

## Что теперь делает попытка выложить витрину старым путём

    $ python3 -m factory build --site lords-01
    [BLOCKED_SITE_EXTRACTED] lords-01: сборка через общий путь запрещена —
    сайт выделен в собственный репозиторий
    https://github.com/sbc-create/site-lordfilm47-space

Тот же отказ — у `factory deploy`, у `finalize-public-sites.sh` и у
`lords-staging-apply.sh`, причём до первой записи на диск.

`lords-content-refresh.sh` отказа не делает намеренно: он доставляет данные,
которых нет в выпуске. Причина записана в самом сценарии.

## Активация: одна команда, ограниченная по входу

    python3 -m factory cell activate --site <site_id> --commit <коммит>   # сухой прогон
    python3 -m factory cell activate --site <site_id> --commit <коммит> --no-dry-run

Команда не принимает ни пути к скрипту, ни пути к артефакту: артефакт
собирается из названного коммита, что возможно благодаря воспроизводимости
сборки. Требует root для самой активации.
