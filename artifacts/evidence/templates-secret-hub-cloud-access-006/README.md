# TEMPLATES-SECRET-HUB-CLOUD-ACCESS-006 — доказательства

Секретов здесь нет и быть не может: ни значения, ни его части, ни отпечатка, ни
хэша. Все файлы этого каталога содержат только коды ответов, заголовки, имена
целей и пути.

## Что установлено о действующем control-plane

Источники — конфигурация и живой runtime, а не переписка.

| Что | Значение | Откуда |
| --- | --- | --- |
| control host | `claude-control-01`, 45.131.182.225 | `knowledge/INFRASTRUCTURE_INVENTORY.yaml`, `docs/INFRASTRUCTURE.md` |
| сервис хаба | `site-factory-secret-hub.service` (root) | `/etc/systemd/system/` |
| сервис панели | `site-factory-secret-panel.service` (`sfpanel`) | там же |
| петлевой адрес панели | `127.0.0.1:8459`, база `/__factory-secrets` | `config/secret-hub.json → public_form`, подтверждено ответом 200 |
| предполагаемый публичный домен | `yummyani.site` | `config/secret-hub.json → public_form.server_name` |
| reverse proxy | nginx 1.18, vhost `/etc/nginx/sites-available/yummyani.site.conf` | живая конфигурация |
| сниппет панели | `/etc/nginx/snippets/secret-hub.d/enroll.conf` — установлен, корректен | живая конфигурация |
| **строка `include` этого сниппета в vhost** | **отсутствует** | `reachability.json` |

## Блокер: публичного HTTPS-адреса панели не существует

Панель жива и отвечает `200` на петле. Наружу её не выводит никто: ни один vhost
не подключает `secret-hub.d`, и `/__factory-secrets` на всех семи обслуживаемых
доменах отдаёт `404` или редирект самого сайта — см. `reachability.json`.

Недостающее действие ровно одно: добавить в HTTPS-блок vhost одну строку
`include /etc/nginx/snippets/secret-hub.d/*.conf;`, проверить `nginx -t` и
перезагрузить nginx. Код для этого в фабрике есть и идемпотентен
(`factory/secret_hub/publish.py::ensure_include` — бэкап vhost, `nginx -t`,
откат при отказе).

Выполнить его из этой сессии нельзя: `/etc/nginx` принадлежит root и закрыт на
запись, а `sudo` и `systemctl` запрещены профилем (`.claude/settings.json →
permissions.deny`). Сам хаб тоже не может: у него `ProtectSystem=full`, и
`/etc/nginx` в его `ReadWritePaths` не входит — там только
`/etc/site-factory/secrets` и `/etc/systemd/system`. Это граница привилегий, а
не пропущенный шаг.

### Единственное действие, требующее прав

```
sudo /srv/site-factory/repo/bin/secret-hub-install
```

Это штатный лончер установки, а не команда, придуманная под случай. Он
идемпотентен: существующий мастер-ключ не перезаписывает, панель публикует
через `ensure_include` (бэкап vhost → `nginx -t` → откат при отказе), ждёт, пока
перезагруженный nginx действительно начнёт отдавать панель, проводит живую
проверку по публичному имени и **снимает панель обратно, если проверка не
прошла** — адрес в этом случае не печатается вовсе. Код первичной регистрации
выпускается, только если passkey ещё не зарегистрирован.

Сухой прогон, ничего не меняющий и не требующий прав, уже выполнен из этой
сессии и прошёл: `bin/secret-hub-install --preflight` → `PREFLIGHT=pass`.

Предусловие, не требующее прав: рабочая копия `/srv/site-factory/repo`, из
которой читают оба unit'а (`Environment=SECRET_HUB_CONFIG=`), должна содержать
эту ветку. Сейчас она занята другой задачей (ветка `claude/day05-lords-merged`,
есть незакоммиченные файлы), и переключать её эта сессия не имеет права — работа
велась в отдельном worktree. Пока ветка не попала в эту рабочую копию,
направления Zona и Animedia не появятся в панели, даже если панель опубликована.

Состояние по классификации задания:

* **не «target отсутствовал только в конфигурации Secret Hub»** — конфигурация
  теперь полна;
* **не «отсутствует production site или unit»** — витрины Zona и Animedia живы
  и обслуживаются (см. ниже);
* **не «отсутствует publisher у внешнего провайдера»** — к провайдеру в этой
  работе не обращались вовсе;
* это **отсутствие публикации панели в reverse proxy**, требующее root.

## Что проверено на живом процессе панели

`panel-security.json` — ответы работающего `site-factory-secret-panel.service`.

| Проверка | Ожидалось | Получено |
| --- | --- | --- |
| неавторизованная страница | только форма входа | `200`, заголовок «Secret Hub — вход» |
| утечка имён направлений и полей в неавторизованном HTML | нет | ни одного из `yami/lords/amedia/zona/animedia/api_token/publisher/Применить/Заменить` |
| `POST /api/portfolio/save` без сессии | `401` | `401` |
| `POST /api/portfolio/apply` без сессии | `401` | `401` |
| те же с сессией, но без CSRF | `403` | `403` |
| те же с сессией и неверным CSRF | `403` | `403` |
| `GET` с query string | `404` | `404` — секрет в URL невозможен |
| `Cache-Control` на всех путях | `no-store` | `no-store, max-age=0` |
| cookie | `__Secure-`, `Secure`, `HttpOnly`, `SameSite=Strict`, `Path` на панель | все пять |

TLS здесь не проверялся и не мог быть проверен: панель слушает петлю открытым
текстом, а терминировать TLS должен nginx — которого на этом пути нет. Заявлять
`HTTPS_STATUS=PASS` по петлевому ответу было бы отчётом о непроведённой
проверке.

## Цели, добавленные в реестр

| Направление | Сайт | Домен | Обслуживающий unit |
| --- | --- | --- | --- |
| `zona` | `zona-01` | zonafilm.space | `nova-zona-01.service` |
| `animedia` | `animedia-01` | animedia.icu | `nova-animedia-01.service` |
| `animedia` | `animedia-02` | animedia.space | `nova-animedia-02.service` |

Site ID и unit'ы взяты из живого runtime: `/etc/nginx/lords/*.conf` проксирует
эти домены на 9120–9122, то есть на `nova-*`, а не на одноимённые старые
unit'ы `zona-01.service`/`animedia-0X.service` (порты 9104–9106), на которые
nginx уже не ходит. Подтверждается профилями сайтов
(`config/site-profiles/*.json`: `family`, `deployment.serving_unit`).

`w140.zona.plus` и `amd.online` целями не стали — это визуальные референсы
(D130), и тест `test_visual_references_are_not_targets` это стережёт.

Lords не тронут: `test_lords_is_untouched` сверяет состав потребителей, способ
доставки, unit'ы, каталоги, режимы и имена credentials.

## Что эти направления не получают

Только **Publisher ID**. API Token хранится и проверяется живым запросом к
провайдеру, но не доставляется: потребителя у него нет. Каталог витрин собирает
`lords-content-refresh.service`, и его список сайтов — `lords-01…03`; юнита
обновления для Zona и Animedia не существует (D132). Это отсутствующий unit, а
не необязательное поле.

## Прогоны тестов

| Команда | Результат |
| --- | --- |
| `pytest tests/unit -k secret_hub` | 444 passed, 1 skipped |
| `pytest tests/unit` (весь набор) | 2551 passed, **1 failed**, 5 skipped |
| `ruff check factory/secret_hub tests/unit/test_secret_hub_showcase_targets.py` | чисто |
| `scripts/validate_registries.py` | `config/secret-hub.json → secret-hub.schema.json` OK |
| `factory knowledge verify` | целостность OK |
| `bin/secret-hub-install --preflight` | PREFLIGHT=pass |

К этому добавлены **два намеренно падающих теста** в
`tests/unit/test_root_units_execstart_ownership.py`: они фиксируют находку о
хосте (root-юниты исполняют файлы, открытые на запись учётной записи агента —
см. `FINDING-root-units-run-agent-writable-scripts.md`). Провал здесь — это
сообщение о дефекте, а не поломка: правило фабрики запрещает гасить такой тест
`xfail`'ом или пропуском. Он станет зелёным, когда `ExecStart` пяти юнитов
переедет в root-owned каталог.

Единственный провал, не относящийся к этой работе, —
`test_job_result.py::test_real_pilot_results_are_schema_valid`.
Он **не** вызван этим изменением и к нему не относится: тест требует
`artifacts/jobs/pilot-local/*.json` — рантайм-артефакты пилота, которые
`.gitignore` не отслеживает. В свежем worktree их нет ни при каком коде.
Проверено прямо: на базовом коммите `a7f7cb6` в другом рабочем дереве падает
ровно этот тест и только он. Скрывать его нельзя, чинить в рамках этой задачи —
тоже: он о состоянии рабочего дерева, а не о Secret Hub.

Пропуски (5) — среды, а не обход: отсутствие `.venv` в дереве, интерпретатор
3.10 и закрытый для этой учётной записи каталог секретов.

## Откат

Изменения этой ветки — только файлы репозитория; на хосте не изменено ничего.

* Откат кода: `git revert` коммита ветки.
* Откат реестра: направления `zona` и `animedia` — отдельные записи
  `config/secret-hub.json`; удаление записи убирает цель и не затрагивает ни
  Lords, ни Yami, ни `amedia`.
* Откат применения (фаза B, ещё не выполнялась): `apply` снимает копию файлов
  потребителя и drop-in до перезаписи и возвращает прежнее состояние при ошибке
  на любом шаге; последняя рабочая версия значения в хранилище не удаляется
  никогда.
* Если публикация панели в nginx будет выполнена: `ensure_include` копирует
  vhost в бэкап до правки и восстанавливает его, если `nginx -t` отверг
  конфигурацию.

## Файлы

| Файл | Что в нём |
| --- | --- |
| `FINDING-root-units-run-agent-writable-scripts.md` | находка: root-юниты исполняют файлы, открытые на запись агенту; не эксплуатировалась |
| `targets.json` | состав целей после изменения: способ доставки, unit'ы, что именно доставляется |
| `reachability.json` | ответы панели на петле и nginx по семи доменам |
| `panel-security.json` | граница аутентификации, CSRF, no-store, флаги cookie |
| `pytest-secret-hub.txt` | прогон `tests/unit -k secret_hub` |
| `pytest-unit-full.txt` | прогон всего `tests/unit` |
