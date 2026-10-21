# Выкладка bestreciept.site и myfood.mobi на 45.131.182.225 (20.10.2026)

Домены выбраны и выкладка разрешена владельцем 20.10.2026. Индексация на этапе просмотра закрыта.

## Что куда

| домен | шаблон | код (ветка, коммит) | порт | служба | каталог |
| --- | --- | --- | --- | --- | --- |
| https://bestreciept.site | food-daily C «Будни на кухне» (22 рецепта, редактор, база версий) | `claude/template-food-daily-c` `eaa82c9` | 9211 | `recipe-bestreciept-site.service` | `/srv/bestreciept-site` |
| https://myfood.mobi | food-baking B «Тесто и десерты» (13 рецептов выпечки) | `claude/template-food-baking-b` `d29c41a` | 9212 | `recipe-myfood-mobi.service` | `/srv/myfood-mobi` |

Почему food-baking B для myfood.mobi: самостоятельный кулинарный сайт со своим контентом, каталогом, поиском и
оформлением. food-daily B повторил бы те же 22 рецепта на втором домене (дубль), food-weekly зависит от каталога
food-daily, food-appliances — узкая тема (техника). Названия, оформление, конфигурация (`config/site.bestreciept.yaml`,
`config/site.myfood.yaml`), пользователи, каталоги данных и секреты у витрин раздельные.

## DNS (проверено 20.10.2026, публичные резолверы 1.1.1.1 и 8.8.8.8)

Оба домена на Cloudflare (NS `pablo`/`april.ns.cloudflare.com`), запись A без проксирования → `45.131.182.225`;
`www` — CNAME на основной домен → тот же адрес; AAAA и CAA нет. Расхождений нет, HTTP-проверка Let's Encrypt
пройдёт. До выкладки сервер отвечает на эти имена правилом «запретить по умолчанию»: HTTP 404, по HTTPS чужой сертификат.

## Почему нужен шаг владельца

Подключение нового домена (nginx, сертификат, служба, пользователь) на этом сервере — root-действие. По устройству
проекта его выполняет владелец сценарием (`automation/host/README.md`; так подключён zonafilm.cc); исполнитель ячеек
новые сайты и TLS не трогает по замыслу, а сессии sudo запрещён. Сценарии готовы, проверены и идемпотентны.

## Команды владельца (по одной на домен)

```bash
cd /home/claude/wt-template-food-daily-c
sudo bash templates/food-daily/deploy/bestreciept-apply.sh --kit /home/claude/wt-template-food-daily/var/kits/food-daily-eaa82c9

cd /home/claude/wt-template-food-baking-b
sudo bash templates/food-baking/deploy/myfood-apply.sh --kit /home/claude/wt-template-food-daily/var/kits/food-baking-d29c41a
```

Каждый сценарий: проверяет комплект (`sha256sum -c`) → ставит релиз только для чтения → создаёт системного
пользователя и каталоги данных/секретов вне релиза → (bestreciept) один раз восстанавливает редакционную базу
из комплекта с проверкой 24 материалов и 50 версий → создаёт учётку редактора (`/srv/<сайт>/secrets/editor-password.txt`,
0600) → служба на 127.0.0.1 с проверкой `/healthz` (при отказе — возврат прежнего релиза) → nginx: HTTP→HTTPS,
`www` → основной домен, `X-Robots-Tag: noindex`, `/redaktor` снаружи — 404 → сертификат Let's Encrypt (webroot
`/var/www/certbot`, как у соседей) → `certbot renew --dry-run`; продление — существующий `certbot.timer` и хук
`reload-nginx.sh`. Каждая правка nginx проходит `nginx -t`; при отказе файл выключается, соседи не затрагиваются.
Откат кода: тот же сценарий с `--rollback`. Повтор безопасен.

## Проверено до шага владельца

| что | как | результат |
| --- | --- | --- |
| тесты шаблонов с конфигурацией домена | `bash bin/<сайт> test` | food-daily 153 passed, food-baking 42 passed |
| конфигурация домена | `tests/test_domain_config.py` | все URL sitemap: canonical на домене, noindex, нет `127.0.0.1`; robots `Disallow: /`; `SITE_CONFIG` не принимает путь вне `config/` |
| репетиция выкладки без root | scratchpad `rehearse.py`: релиз из комплекта, `var/` вне релиза, восстановление базы, запуск с `SITE_CONFIG`, запросы с `Host` домена | главная, каталог, рецепт, поиск, инструменты — 200, canonical на домене, `X-Robots-Tag: noindex`; 404 — 404; sitemap 53 и 26 адресов на `https://<домен>/`; ресурсы 0 ошибок; редактор без учётки — 401; база: 24 материала, 50 версий |
| сценарии выкладки | `bash … --dry-run`, `bash -n`, `shellcheck -S warning` | exit 0, замечаний нет |

## После шага владельца

`external_check.py` (scratchpad): DNS, сертификаты и их срок, редиректы `http://`, `http://www.`, `https://www.`,
правильный сайт по variant-id, главная/каталог/рецепт/поиск, canonical, noindex, `/redaktor` → 404, ресурсы, мобильная
ширина 390 px в Chromium.

## Контент и Qwen

Используется подготовленный проверенный контент веток. Набор Qwen для рецептов (в том числе «500 вариантов подачи»)
на сервере не найден: в `var/food-daily/qwen/outbox` — 24 экспортированных задания без ответов, `qwen-nightly-drafts`
пуст, остальные каталоги Qwen — SEO, комментарии и индексация других направлений. Выкладка идёт без него.

## Результат после шага владельца (20.10.2026, внешняя проверка по доменам)

Владелец выполнил оба сценария без ошибок. Проверка снаружи через публичный DNS и настоящий HTTPS
(scratchpad `external_check.py`, `deep_check.py`, `final_check.py`; все exit 0):

| что | bestreciept.site | myfood.mobi |
| --- | --- | --- |
| развёрнутый релиз | `releases/eaa82c9de344`, служба active/enabled | `releases/d29c41a68d36`, служба active/enabled |
| сертификат | Let's Encrypt, SAN домен + www, 89 дней | Let's Encrypt, SAN домен + www, 89 дней |
| `http://`, `http://www.`, `https://www.` | 301 → `https://bestreciept.site/` | 301 → `https://myfood.mobi/` |
| правильный сайт | variant `party-list`, «Будни на кухне», чужого названия нет | variant `oven-bench`, «Тесто и десерты», чужого названия нет |
| все адреса sitemap | 53 (22 рецепта): 200, canonical = адрес, `X-Robots-Tag: noindex`, нет `127.0.0.1` | 26 (13 рецептов): то же |
| поиск | «творог» — 3 рецепта | «печенье» — 4 рецепта |
| robots.txt | `Disallow: /` | `Disallow: /` |
| закрытые пути | `/redaktor`, `/.git/config`, `/var/`, `/config/…`, `/secrets/…`, `/.env` — 404 | то же |
| ресурсы | 3 из 3 — 200 | 3 из 3 — 200 |
| мобильно 390 px (Chromium): главная, каталог, рецепт, поиск | 200, без горизонтальной прокрутки, без ошибок консоли и сбоев запросов | то же |
| продление | `certbot.timer` enabled | то же |

Соседние сайты из `sites-enabled` (an1mego.site, animeg0.site, yummyani.biz/.org/.site) по HTTPS — 200.
Ошибок, требующих исправления, не найдено.

## Раунд 2 (20.10.2026): оформление, служебные тексты, приём набора Qwen, подготовка к индексации

### Код

| сайт | ветка, коммит | что изменено |
| --- | --- | --- |
| bestreciept.site | `claude/template-food-daily-c` `8161ada`, `7fe849b` | сетка карточек 1/2/3/4 (560/900/1200 px), новая главная (поиск, разделы с числом рецептов, «на скорую руку», «на компанию», новые рецепты, сезонный блок по подборке ≥3), рецепт: быстрые факты и переходы к ингредиентам и приготовлению; футер; «Конфиденциальность»; `/kontakty/` → 301 на `/o-proekte/`; убраны «ИИ», «редактор не проверил», «редакция не готовила»; WebSite+SearchAction, ItemList; `fooddaily.set_import`; `fooddaily.media` |
| myfood.mobi | `claude/template-food-baking-b` `a74fa9a`, `5e38ec6` | карточки 1/2/3/4 вместо оглавления и таблицы (таблица — вид `?vid=tablica` без canonical), разделы `/recepty/<раздел>/`, `/duhovka/` «по температуре», главная (поиск, разделы, осенняя выпечка, «духовка греется», «к чаю», новые), рецепт: выход, продукты, переходы; футер; «Конфиденциальность»; убраны «рабочее название», «предварительная версия», «с помощью ИИ», «не пекла», «Фото нет», «версия N»; `bakebook.set_import`; `bakebook.media` |
| оба | `claude/template-food-daily` `50e23cb` | `tools/qwen_recipes_intake.py` (приёмник набора), `automation/host/recipe-domains-apply.sh` (одна команда владельца) |

### Проверки до выкладки

| что | команда | результат |
| --- | --- | --- |
| тесты food-daily C | `bash bin/food-daily test` | 167 passed, exit 0 |
| тесты food-baking B | `bash bin/food-baking test` | 55 passed, exit 0 |
| приёмник набора | `pytest tests/unit/test_qwen_recipes_intake.py tests/unit/test_repo_hygiene.py` | 14 passed, exit 0 |
| линтер | `ruff check` (оба шаблона, приёмник) | без замечаний |
| служебные тексты | `test_launch_readiness.py::test_no_technical_text_in_public_html` — все URL карты, поиск, 404 | 0 совпадений |
| переключение индексации | `test_indexing_switch_is_consistent[False/True]` — robots.txt, meta robots, X-Robots-Tag, canonical по всем URL карты через HTTP | согласовано в обоих состояниях |
| внутренние ссылки | scratchpad `crawl.py` | bestreciept 70 адресов, myfood 42 — все 200 |
| вёрстка | scratchpad `shoot.py`, Chromium 1440/1024/768/390/320 | без горизонтальной прокрутки и ошибок консоли |
| репетиция комплектов | scratchpad `rehearse.py` (порты 9241/9242) | обе главные 200, canonical на домене, noindex; карта 53 и 33 адреса; ресурсы 0 ошибок |
| сценарий обновления | `bash automation/host/recipe-domains-apply.sh --dry-run` | exit 0, индексация закрыта в обоих |

### Изображения

Фотографий блюд с установленными правами и средств генерации изображений нет: 0 из 22 и 0 из 13 рецептов
с изображением. Одну картинку на много блюд не ставим. Подготовлено: `data/media/images.json` (вид photo/illustration,
источник, лицензия, alt — без них сайт не запускается), `python3 -m fooddaily.media add` / `python3 -m bakebook.media add`
делают WebP 400/800/1200 в пропорции 4:3; карточка и рецепт выводят `<picture>` с srcset, размерами и lazy loading,
Recipe JSON-LD получает `image` только при такой записи.

### Набор Qwen QWEN-NIGHT-RECIPES-100X5-001

На сервере не найден (по имени и содержимому в /home, /srv, /var/lib, /opt, /tmp, /mnt, /media, /data; каталога
/home/user нет). Каталог приёма: `/home/claude/wt-template-food-daily/var/qwen-intake/` (вне git, 0700) —
положить `QWEN-NIGHT-RECIPES-100X5-001.tar.gz` (или каталог). Дальше: `tools/qwen_recipes_intake.py plan`, пробная
партия `set-import --limit 3`, затем вся партия, снимок, новые комплекты и та же команда владельца.

### Внешняя проверка после обновления раунда 2 (релизы 7fe849b и 5e38ec6)

scratchpad `live_verify.py`, по домену через публичный DNS и HTTPS, exit 0: сертификаты действительны (89 дней,
домен + www), `http://`, `http://www.`, `https://www.` → 301 на основной домен; правильный сайт по variant-id;
все URL карты (53 и 33) — 200, canonical = адрес, `X-Robots-Tag: noindex`; служебных фраз — 0; Recipe JSON-LD
согласован с H1 — 22/22 и 13/13; robots.txt `Disallow: /`; `/kontakty/` → 301 `/o-proekte/` (bestreciept);
Chromium 1440/768/390 — сетка 4/2/1 колонки, без горизонтальной прокрутки, ошибок консоли и сбоев загрузки.

## Раунд 3 (20.10.2026): плитки, поиск «курица», «печень» в импорте

| что | было | стало | коммит |
| --- | --- | --- | --- |
| плитки разделов myfood.mobi | «Заварные пирожные» выше остальных; на 320 px перенос «Завар-ные пирож-ные» | одна высота: 72 px от 480 px, 92 px уже (счётчик под названием); перенос только по словам; 6 колонок от 1200 px | `d83ed7f` |
| поиск «курица» bestreciept.site | 10 результатов, из них 5 только с куриными яйцами (блины, оладьи, ленивые вареники, тефтели, шакшука) | 5 — ровно рецепты с мясом курицы; «куриное яйцо/желток» при сопоставлении = «яйцо/желток» | `8e04898` |
| поиск «курица» myfood.mobi | 10 (вся выпечка на яйцах) | 0 | `d83ed7f` |
| «печень» в приёмнике и импорте выпечки | «Куриная печень» → выпечка / раздел «Печенье» | → bestreciept.site, второе блюдо, тема «курица»; в книгу выпечки не попадает | `98040ca`, `d83ed7f`, `8e04898` |
| повтор импорта | дата получения подставлялась текущим временем — повтор иногда считался обновлением (1 failed в `8e04898`) | дата только из набора; 6 прогонов подряд без сбоев | `3052c6c`, `aa13a3d` |

Проверки: `bash bin/food-daily test` — 169 passed (exit 0); `bash bin/food-baking test` — 57 passed (exit 0);
`pytest tests/unit/test_qwen_recipes_intake.py` — 4 passed; ruff — без замечаний; репетиция комплектов
`food-daily-3052c6c` и `food-baking-aa13a3d` (порты 9241/9242) — главные 200, карта 53/33, «курица» 5/0;
`recipe-domains-apply.sh --dry-run` — exit 0, индексация закрыта в обоих.

Обновление: `sudo bash /home/claude/wt-template-food-daily/automation/host/recipe-domains-apply.sh`
(`var/kits/recipe-domains-current` → `recipe-domains-3`).

## Раунд 4 (21.10.2026): где лежит архив Qwen и почему он не получен

Заявлено Qwen: `/home/user/content/food-daily/authoring/QWEN-NIGHT-RECIPES-100X5-001.tar.gz`, ~110 КБ,
SHA-256 `3e20d2359b6698779df24260225ebd3ef5748f0c81d63dfa41f4c78271a4b64e`. Ниже — только то, что
проверено командами в этой сессии; заявленные Qwen величины не подтверждены, файл не получен.

| проверка | команда / источник | результат |
| --- | --- | --- |
| путь на сервере сайтов (claude-control-01, 45.131.182.225) | `find / -xdev -name 'QWEN-NIGHT-RECIPES*' -o -path '*/content/food-daily/authoring*'` | exit 0, совпадений нет (кроме тестовых фикстур pytest); в `/home` только `claude` и `ubuntu` |
| недавние архивы 90–130 КБ с 18.10 | `find / -xdev -newermt 2026-10-18 -name '*.tar.gz' -size +90k -size -130k` | только собственные комплекты `var/kits/recipe-domains-{2,3}` |
| где работает Qwen | `docs/QWEN_MCP_BRIDGE.md` разд. 6, `docs/QWEN_CONNECTION_CHECKPOINT.md` (ветка интеграции Qwen) | отдельный хост `srv-qwen` (Open WebUI `83.237.185.70`), compose `/opt/qwen/compose.yaml`, контейнеры `qwen-open-webui`, `qwen-site-factory-mcp`; командный инструмент Qwen — контейнер Agent Workspace `6265eddb1580`. `/home/user` — путь внутри контейнера на srv-qwen (по документам; изнутри не проверено) |
| канал srv-qwen → фабрика | там же, разд. 7 | ключ `sfbridge` с `restrict,port-forwarding,permitopen="127.0.0.1:9000",command="/bin/false"` — только проброс к мосту MCP, `scp`/`sftp` невозможны |
| мост MCP | `curl http://127.0.0.1:9000/healthz`, `tools/list` | `ready: true`, 43 инструмента; инструмента приёма файлов или рецептов нет (аниме-витрины, очередь, индексация) |
| канал фабрика → srv-qwen | `inventory/ssh-hosts.yaml` | `hosts: []`; произвольный ssh запрещён правилами |

Отсутствует: экспорт файла с srv-qwen на сервер сайтов. Ни Qwen, ни эта сессия сделать его существующими
доступами не могут — нужен администратор srv-qwen (см. «Команда администратору srv-qwen» ниже).
Импорт не запускался.

### Команда администратору srv-qwen

    P=/home/user/content/food-daily/authoring/QWEN-NIGHT-RECIPES-100X5-001.tar.gz
    for c in $(sudo docker ps -q); do sudo docker exec "$c" test -f "$P" 2>/dev/null && echo "$c"; done
    sudo docker cp <ID_из_вывода>:"$P" . && sha256sum QWEN-NIGHT-RECIPES-100X5-001.tar.gz

Затем файл кладётся на 45.131.182.225 в `/home/claude/wt-template-food-daily/var/qwen-intake/` тем
доступом, которым владелец заходит на сервер сайтов. После этого сессия сама считает SHA-256, сверяет с
заявленным, проверяет состав (100 баз × V1–V5) и только при полном совпадении запускает пробную партию.

## Раунд 5 (21.10.2026): внешний вид, главные, поиск, рецепт на телефоне

Архив Qwen в `var/qwen-intake/` отсутствует (проверено один раз 21.10) — работа шла с рецептами проекта:
bestreciept.site — 22 опубликованных блюда, myfood.mobi — 13. Изображений с подтверждёнными правами — 0/22 и 0/13:
генератора на сервере нет (нет diffusers/torch/GPU и API), внешние фото не берутся (CLOSED_WORLD, права).
Инструмент `media add` готов принять файл с правами (WebP 400/800/1200, alt, источник, лицензия).

| сайт | коммиты | что изменилось |
| --- | --- | --- |
| bestreciept.site | `c19d74a` `b039d58` `fc6bbd5` `03e1f37` `b611ba5` | шрифты Golos Text + Lora (OFL, свои файлы); единая шкала заголовков/отступов/скруглений; разделы в первом экране рядом с поиском; «Быстро: до 30 минут», «На завтрак», «Новые» — без повторов карточек; карточка: время и порции; поиск по началу слова с окончаниями (регистр, «сырник/сырники», «тыква/тыквой»), части слова в середине не совпадают («печень» ≠ «купечески»); пустой поиск предлагает разделы; рецепт на телефоне: сведения в ряд, компактные шаги; первый экран без горизонтальной прокрутки на 320–360 px; каталог 24 на страницу (22 рецепта — одна страница, полные ряды); подвал в две колонки на телефоне; описание /podborki/ |
| myfood.mobi | `ceed9b7` `e2c71d1` `085c4be` `ec17538` | тёплая гамма (сливки/шоколад/карамель) вместо графита; шрифты Nunito + Playfair Display (OFL); светлые плитки разделов одной высоты; названия без переносов внутри слов; главная без повторов (сезон / к чаю / новые), три карточки — ряд из трёх; таблица «Отвесить» на телефоне без прокрутки (% от муки под названием); «Похожие рецепты»; ширина таблицы и шагов для чтения; поиск как у bestreciept, «печень» ≠ «печенье»; пустой поиск → разделы; `.webp`/`.woff2` с правильным Content-Type (раньше octet-stream при nosniff); каталог 24 на страницу; подвал |

Проверки (локально, код из этих коммитов):

| проверка | команда | результат |
| --- | --- | --- |
| тесты bestreciept | `bash bin/food-daily test` | 171 passed, exit 0 (+2 регрессионных: главная без повторов и рабочие ссылки; поиск по формам слова) |
| тесты myfood | `bash bin/food-baking test` | 60 passed, exit 0 (+3: главная без повторов; поиск; похожие рецепты) |
| ruff | `ruff check fooddaily tests`, `ruff check bakebook tests` | без замечаний |
| браузер, 360/390/768/1440 × 6 страниц × 2 сайта | `var/recipe-look/shots.py after-local …` | 48 снимков: 200, без горизонтальной прокрутки, ошибок консоли и выхода за край |
| взаимодействие | `var/recipe-look/interact.py` | порции 2→3→1→2 (190 г → 285 г → 95 г → 190 г, ½ для штук и ложек); якорь «Приготовление»; поиск с главной — 5 («Курица») и 3 («Кексы»); фокус виден на 14/14 первых табуляциях обоих сайтов; плитка раздела ведёт на страницу с карточками |
| SEO и ссылки | `var/recipe-look/seo_check.py` | bestreciept: 59 страниц, 0 битых ссылок, повторов title/description нет, Recipe = видимое (название, ингредиенты, шаги, без рейтингов) 22/22; myfood: 37 страниц, 0 замечаний, 13/13 |
| комплекты | `bin/food-daily kit build`, `bin/food-baking kit build` → `var/kits/recipe-domains-4/` | `food-daily-b611ba5`, `food-baking-ec17538`; суммы сходятся; шрифты внутри; `production_authorized: false` |
| репетиция комплектов | scratchpad `rehearse.py` (порты 9241/9242) | exit 0: база восстановлена (24 материала, 50 версий, расхождений 0), noindex, «Disallow: /», карта 51/32, «курица» 5/0, шрифты `font/woff2` |
| команда владельца, пробно | `bash automation/host/recipe-domains-apply.sh --dry-run` | exit 0, индексация закрыта в обоих |

Данные: релиз содержит снимок содержимого и ставится в отдельный каталог `releases/<коммит>`; редакционная база
на сервере не перезаписывается («уже есть — не трогаю»); `--rollback` возвращает предыдущий релиз вместе с его
содержимым.

Доступность (дополнение той же ночи):

| проверка | команда | результат |
| --- | --- | --- |
| браузерная приёмка bestreciept | `QA_BASE=http://127.0.0.1:9231 python3 -m fooddaily.qa_browser` | exit 0; сценарии все true, axe 4.13.0 — 0 нарушений на 38 просмотрах, контраст — 0, ошибок консоли 0, CLS ≤ 0,0012. Сценарий «на компанию» искал форму на главной (ушла во 2-м раунде) и падал по таймауту — исправлен; кнопка «Собрать список» на главной ведёт к последнему выбору (`b3f9c95`) |
| axe по остальным страницам bestreciept | `var/recipe-look/axe_check.py` (10 страниц × 390/1440) | 0 нарушений |
| axe myfood | `var/recipe-look/axe_check.py` (14 страниц × 390/1440) | было `landmark-unique` (две навигации «Разделы») на каждой странице → подписи «Основное меню» / «Рецепты по разделам» (`92da48c`) → 0 нарушений |
| комплекты | `kit build` → `var/kits/recipe-domains-5/` | `food-daily-b3f9c95`, `food-baking-92da48c`; репетиция exit 0; `recipe-domains-apply.sh --dry-run` exit 0, индексация закрыта |

Обновление: `sudo bash /home/claude/wt-template-food-daily/automation/host/recipe-domains-apply.sh`
(`var/kits/recipe-domains-current` → `recipe-domains-5`). Скриншоты «до»/«после»: `var/recipe-look/{before,after-local}/`.

### Готовность к открытию индексации (21.10.2026, индексация НЕ открыта)

Один флаг `production_authorized` в `config/site.bestreciept.yaml` / `config/site.myfood.yaml` согласованно меняет:
robots.txt (`Disallow: /` → Allow + Sitemap + запрет служебных и `/*?`), meta robots, X-Robots-Tag приложения и
nginx, карту сайта. Оба состояния проверяются тестом `test_indexing_switch_is_consistent` на живом HTTP-сервере —
2 passed на каждом сайте (exit 0).

| условие | bestreciept.site | myfood.mobi |
| --- | --- | --- |
| уникальные title/description, один H1, canonical на домене | да (59 страниц) | да (37 страниц) |
| хлебные крошки + BreadcrumbList | да | да |
| Recipe JSON-LD = видимое, без рейтингов/отзывов/авторов | 22/22 | 13/13 |
| битые внутренние ссылки | 0 | 0 |
| карта без служебных страниц | 51 адрес | 32 адреса |
| axe-core 4.13.0 | 0 нарушений | 0 нарушений |
| изображения блюд | 0/22 — не блокирует индексацию, блокирует «аппетитную» выдачу | 0/13 |

Чего не хватает (решения и данные владельца): решение открыть индексацию; сведения об операторе сайта и контакт
для «О проекте» и «Конфиденциальности» (сейчас контактов нет — не выдуманы); изображения с правами или подключённый
генератор; архив Qwen для расширения каталога.
