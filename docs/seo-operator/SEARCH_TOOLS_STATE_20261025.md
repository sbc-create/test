# Топвизор, Яндекс.Вебмастер, Search Console: фактическое состояние сети (25.10.2026)

Проверено 25.10 21:40–21:46Z. Всё ниже — только чтение. Ни одного платного действия, ни одного нового проекта или кабинета.

Артефакты:
- `artifacts/evidence/topvisor-inventory-20261025.json`;
- `artifacts/evidence/search-split-20261025.json`;
- `var/analytics/cabinet-latest.json` (штатный сборщик, 25.10 05:05Z).

## Короткий вывод

1. **Позиций нет ни по одному сайту, ни за один день.**
   - Топвизор: у всех 17 проектов `last_position_at: null`, поисковики и регионы пусты, баланс 0, тариф XS.
   - Действующий SEO-процесс Топвизор не читает: ни один модуль `seo_operator` к нему не обращается.
   - Задач, выбранных по данным Топвизора, **не было ни одной**.
2. **Вебмастер подтверждён, но данных нет.** В реестре 15 сайтов из списка владельца значатся VERIFIED. Данные не собирались ни разу: TCP 443 до `api.webmaster.yandex.net` даёт тайм-аут (B023, воспроизведено 25.10 21:43Z).
3. **Search Console не подключена.** Нет ни одного property и нет сервисного аккаунта (B024). Сеть до API открыта.
4. **Работает только Метрика**, причём это визиты, а не позиции. Она показывает, что запросы Топвизора стоят у сайтов почти без поискового трафика. А сайты с трафиком в Топвизоре без запросов, кроме yummyani.site, у которого всего 39 запросов.

## Топвизор

Источник — ежедневная синхронизация инвентаря только на чтение: пользовательский таймер `seo-engine-topvisor-inventory`, 04:20 UTC, стек `wt-seo-operator-v2-01`.
- **Свежесть.** Последний прогон 25.10 04:23:42Z, бесплатный, 46 успехов подряд. Ответ аккаунта побайтно совпадает с опубликованным 28.09 (`identical payload; published last-good reused`), поэтому числа 28.09 действуют и на 25.10.
- **Позиции** этот сборщик не читает вовсе (`position_state: NOT_READ_SAFETY`).
- **Собственная проверка фабрики** (`topvisor-check.service`) таймера не имеет. `var/topvisor/check-latest.txt` пуст со 2 октября, последний вывод — `check-after-connect.txt` от 28.09.
- **Доступ.** Сессии ключ недоступен (`BLOCKED`: каталог секрета закрыт группой). Работать с аккаунтом могут только службы `topvisor-check` и `topvisor-connect` (LoadCredential).

| Домен | Проект | Групп / запросов | Поисковики, регион, устройство | Расписание | Последний съём | В SEO-процессе |
| --- | --- | --- | --- | --- | --- | --- |
| yummyani.site | 32531550 | 5 / 39 | не заданы (пусто) | нет | никогда | нет |
| yummyani.org | 32531569 | 14 / 50 | не заданы | нет | никогда | нет |
| yummyani.biz | 32531595 | 10 / 82 | не заданы | нет | никогда | нет |
| 1lordserials1.online | 32531542 | 8 / 41 | не заданы | нет | никогда | нет |
| lordserial33.biz | 32531521 | 8 / 41 | не заданы | нет | никогда | нет |
| lordfilm47.space | 32531504 | 8 / 42 | не заданы | нет | никогда | исключён 25.10 |
| yummyani7.site | 33762615 | 0 / 0 | — | — | — | нет |
| yummyani7.info | 33762646 | 0 / 0 | — | — | — | нет |
| animeg0.site | 33751974 | 0 / 0 | — | — | — | нет |
| an1mego.site | 33751941 | 0 / 0 | — | — | — | нет |
| an1meg0.site | 33768290 | 0 / 0 | — | — | — | нет |
| lordserials22.info | 33762550 | 0 / 0 | — | — | — | нет |
| zonafilm.space | 33238820 | 0 / 0 | — | — | — | нет |
| zonafilm.cc | 33768310 | 0 / 0 | — | — | — | нет |
| zonafilm12.site | 33762526 | 0 / 0 | — | — | — | нет |
| animedia.icu | **проекта нет** | — | — | — | — | нет |
| lordserials22.site / .space | 33762569 / 33762590 | 0 / 0 | — | — | — | исключены 25.10 |

Наблюдение владельца подтверждено: запросы есть ровно у шести проектов — yummyani.biz/.org/.site, 1lordserials1.online, lordserial33.biz, lordfilm47.space. Но и у них нет поисковика, региона и съёма, то есть это записанные запросы, а не настроенные проверки. У animedia.icu проекта в аккаунте нет вовсе: в манифесте `factory/topvisor/manifest.py` его нет.

**Цена съёма не подтверждена** (U8 в `knowledge/UNKNOWNS.md`): `topvisor.com` не внесён в разрешённые источники, автоматический лимит трат — 0 ₽. Расчёт возможен только формулой: проверок в месяц = запросы × поисковики × регионы × устройства × съёмов в месяц, стоимость = проверок × цена одной проверки в выбранном режиме. Цену и режим Яндекса должен назвать владелец.

## Яндекс.Вебмастер (B023 проверен заново)

Сборщик — `analytics-cabinet.timer` (05:00Z), из этого дерева. Выгрузка 25.10 05:05Z: по всем сайтам `webmaster: сеть недоступна (URLError)`. У lordserials22.site/.space, lordserial101.site и lordfilm077.site Вебмастер выключен в реестре.

Причина установлена — **подключение**, а не права, настройка или квота. Воспроизведение 25.10 21:43Z с этого узла:

```
python3 -c "import socket;socket.create_connection(('api.webmaster.yandex.net',443),8)"
api.webmaster.yandex.net 213.180.193.61 / 2a02:6b8::2:61  → TimeoutError 8 с (IPv4 и IPv6)
webmaster.yandex.ru      87.250.251.217                  → ok 0,03 с
api-metrika.yandex.net   87.250.251.47                   → ok 0,03 с
```

Яндекс доступен, Метрика собирается. Закрыт путь к одному адресу API Вебмастера — это инфраструктура узла, передано Архитектору. Запись `config/data-sources.json` («сеть до endpoint открыта», «ни один домен не развёрнут») устарела и исправлена по этому замеру.

Подтверждение прав (`config/analytics.json`, последняя сверка 08.10): VERIFIED у animedia.icu, an1mego.site, animeg0.site, an1meg0.site, lordserial33.biz, 1lordserials1.online, lordserials22.info, yummyani7.site, yummyani7.info, yummyani.biz/.org/.site, zonafilm.space/.cc/12.site. Свежесть подтверждения проверить нельзя по той же причине — API недоступен.

## Google Search Console (B024 проверен заново)

`config/data-sources.json`: `missing_credentials` — сервисный аккаунт и карта property не выданы. Сеть открыта: `searchconsole.googleapis.com` и `oauth2.googleapis.com` — ok 0,00 с. Нужна операция владельца.

Google при этом — заметная доля поиска на части сети: lordserials22.info — 854 из 928 поисковых визитов за неделю, zonafilm.space — 643 из 643, zonafilm.cc — 941 из 3 612.

## Метрика: единственные рабочие поисковые данные

Сборщик `analytics-cabinet`, период 18–24.10 (`7daysAgo`–`yesterday`). Это визиты из поиска, а не клики и не позиции.

| Домен | Яндекс | Google | Главный вход из поиска |
| --- | --- | --- | --- |
| yummyani.site | 14 903 | 4 | главная; «Невероятное приключение ДжоДжо: Гонка Стальной…» |
| yummyani7.site | 4 113 | 12 | /anime/pererodivshayasya-velikaya-svyataya-skryvaet-chto… |
| animedia.icu | 3 759 | 51 | /title/bezzhalostnaya-ledi-niya-liston…; /title/ya-vstrechayus-s-temnym-prizyvatelem/ |
| zonafilm.cc | 2 494 | 941 | главная (Я 2 289, G 505); G: /title/taynyy-dnevnik-veriti/ |
| lordserials22.info | 74 | 854 | G: /title/100-atletov-italiya/, /title/k-vostoku-ot-edema/ |
| zonafilm.space | 0 | 643 | G: /title/chernyy-klever/season-2/episode-4/ (552) |
| yummyani7.info | 534 | 19 | /anime/poschadi-menya-velikiy-gospodin-3 |
| zonafilm12.site | 56 | 89 | Я: /title/chuzhaya-zhizn/ (319) |
| animeg0.site | 0 | 50 | — |
| an1meg0.site / an1mego.site | 0 / 0 | 24 / 14 | — |
| yummyani.org / .biz | 2 / 0 | 29 / 22 | — |
| lordserial33.biz / 1lordserials1.online | 5 / 1 | 0 / 0 | — |

## Охват: список владельца и реестр

Канонический реестр — `config/site-cells.json`: 25 ячеек, четыре из них тестовые (`*.localhost`). Все 15 сайтов списка владельца в нём есть. Остальные ячейки:

| Домен | Почему не в активном съёме |
| --- | --- |
| lordfilm47.space | исключён владельцем 25.10, переезд на lords3rial.site, serverHold с 23.10. Платных проверок не было (баланс 0, съёмов не было). Проект 32531504 и его 42 запроса сохраняются для истории |
| animedia.space, lordserials22.site, lordserials22.space | исключены владельцем 25.10 |
| lordserial101.site, lordfilm077.site | заморожены, `planned`, счётчиков и Вебмастера нет |
| K2: lordfilm.group, lordfilm.spb.ru, lordfilm.msk.ru, lordserial.su, lordserial.group, lordserial.spb.ru, lordserial.msk.ru, lordserial.net.ru (lords-10…17) | в реестре этого дерева их нет: они в реестре ветки Архитектора, индексация CLOSED, вне продвижения. Готовность измерений там не проверялась, индексацию не открываю |
| lords3rial.site | serverHold с 25.10 06:20Z, не разрешается — подключение только после снятия hold и запуска; историю lordfilm47.space за неё не выдавать |
| lordserials1.cc, lordserials1.info, lordserials21.cc, lordserials21.info, lordserials21.mobi | нет ни в одном реестре — `BLOCKED_INPUT` до регистрации ячеек |

## Действия владельца — один список

Сессия не может выполнить эти шаги: ключи Топвизора, Вебмастера и Google ей недоступны по построению, а службы запускает root. Бесплатная подготовка идёт без них.

1. **Топвизор — бюджет и режим съёма.** Назвать:
   - месячный лимит трат на позиции;
   - режим Яндекса и его цену за проверку одного запроса (U8);
   - нужен ли Google;
   - регион (сейчас в манифесте — Москва, 213).

   До этого съём не включается: `MAX_AUTOMATED_SPEND_RUB = 0`, баланс 0.
2. **Топвизор — применить подготовленное ядро.** После того как сессия обновит манифест запросов (бесплатная подготовка, следующий шаг), выполнить `sudo systemctl start topvisor-connect.service`. Служба применяет только бесплатные действия (группы и запросы), платные она перечисляет и не выполняет. Итог — `var/topvisor/connect-latest.txt` и `check-after-connect.txt`.
3. **Search Console (B024).**
   - Добавить property 15 доменов, начать с lordserials22.info, zonafilm.space, zonafilm.cc — у них Google даёт заметную долю.
   - Подтвердить права.
   - Выдать сервисный аккаунт с правом чтения, ключ — файлом вне репозитория через secret_ref.
   - Приёмка: ответ Search Analytics API за 28 дней.
4. **Вебмастер (B023).** Открыть исходящий HTTPS с узла до `api.webmaster.yandex.net:443` (213.180.193.61, 2a02:6b8::2:61). Если закрыт фаервол узла — делает Архитектор, ему передано; если провайдер — владелец. Приёмка — `measured: true` у `popular_queries` и `pages_in_search` в следующей выгрузке `analytics-cabinet`.

## Передано Архитектору

B023 с воспроизводимым примером (выше): адрес, команда, контроль соседних хостов. Это инфраструктура узла. По lords3rial.site и новой пятёрке подключения готовятся после регистрации ячеек и снятия serverHold; это его линия.
