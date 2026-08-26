# Гейт хоста и сборка портфеля из нескольких источников

## Зачем

Аудит инфраструктуры, выполненный не на том хосте, хуже отсутствия аудита: он
выглядит завершённым. Предыдущий прогон в эфемерном контейнере дал
`PORTFOLIO_SITES_TOTAL=1` и вывод «нет production/staging» — оба утверждения
неверны для `claude-control-01`.

Две причины, обе устранены в коде:

1. **Реестр читал один файл.** `config/portfolio.json` пуст, и это принималось
   за весь портфель. При этом `config/analytics.json` содержит три домена Yami
   с рабочими счётчиками.
2. **Недоступный источник считался пустым.** Отсутствие `/etc/nginx` в
   контейнере трактовалось как «на хосте нет nginx».

## Гейт хоста

```bash
bin/seo-operator host-verify        # 0 = pass, 3 = BLOCKED_WRONG_HOST
```

Проверяет hostname, IPv4 и наличие `/srv/site-factory/repo`, читая `/proc` и
файловую систему — без внешних утилит, которых может не быть в урезанном
окружении. Ожидаемые значения зашиты в `seo_operator/hostcheck.py`, а не берутся
из окружения: хост, который сам себя объявляет целевым, проверкой не является.

Гейт подключён как `ExecStartPre` к `site-factory-analytics-collect.service`:
unit, скопированный на другую машину, остановится до первого запроса к API.

## Сборка портфеля

```bash
bin/seo-operator portfolio-reconcile           # 0 = чисто, 3 = блокирующий drift
bin/seo-operator portfolio-reconcile --json
```

Источники: `config/portfolio.json`, `config/analytics.json`,
`config/directions/*.json`, `inventory/targets.yaml`, статус Secret Hub, а на
целевом хосте дополнительно nginx, systemd, deployment-манифесты и live HTTPS.

### Виды INVENTORY_DRIFT

| Вид | Что означает |
|---|---|
| `ORPHAN` | домен известен ровно одному реестру |
| `MISSING_IN_SOURCE` | есть в одних источниках, нет в других |
| `FIELD_CONFLICT` | источники дают разные значения одного поля (блокирующий) |
| `UNREACHABLE_SOURCE` | источник не прочитан — это не то же самое, что «пуст» |

`CONFLICT` отделён от `None`: «источники не согласны» и «источник сообщил, что
значения нет» — разные факты. `webmaster_host_id: null` — это подтверждённое
отсутствие хоста в Вебмастере, а не пробел в данных.

## Что переносилось из ветки-сироты

`claude/seo-operator-portfolio-vvmcj7` не имеет общего предка с `main` и не
сливается. Из неё выборочно перенесены модули, которых в `main` не было:
`hostcheck`, `inventory`, `north_star`, `capacity`, `ledger`, `attribution`,
`planner`, `quotas`, `statuses`.

Не переносилось, потому что в `main` уже есть своя реализация: guardrails,
audit, permission model, technical SEO, editorial, pipeline, reporting,
Secret Hub, systemd-юниты аналитики.

Дублирование backoff устранено: `scheduler.Worker` теперь обращается к
`quotas.classify_exception` и `quotas.backoff_seconds` вместо собственной
формулы. Повторять имеет смысл не всякий отказ — истёкший токен и отсутствие
прав ожиданием не чинятся.
