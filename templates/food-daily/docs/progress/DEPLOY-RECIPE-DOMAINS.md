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
