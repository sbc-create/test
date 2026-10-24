# food-daily — «Будни на кухне»

Первый сайт сети практических сайтов (TEMPLATE-FOOD-DAILY-01). Собственный
SSR-шаблон, импорт фактов рецептов, файловый контур Qwen, сценарии видео.
Всё, что относится к сайту, лежит в этом каталоге; границы — `OWNERSHIP.yaml`.

| документ | о чём |
| --- | --- |
| `REPORT.md` | итог задания: что сделано, цифры, готовность, следующие шаги |
| `docs/audit/competitor-audit.md` | аудит 12 референсов, подсчёт страниц, 3 референса, 5 улучшений |
| `docs/audit/competitor-counts.csv`, `data/inventory/*.jsonl.gz` | таблица подсчёта и реестр URL |
| `data/topic-map.csv` | 153 темы, 134 для food-daily, статус обработки |
| `docs/SEO-MATRIX.md` | типы страниц, canonical, индексация, JSON-LD, дерево сайта |
| `docs/INTEGRATIONS.md` | SEO-движок, Qwen, видео, YouTube-контракт, реклама |
| `docs/ISOLATION.md` | изоляция ресурсов и граница diff |
| `docs/NETWORK-PLAN.md` | реестр 10 сайтов, распределение тем, ТЗ 9 шаблонов |
| `DECISIONS.md` | решения FD-01…FD-12 |

Все команды — из корня worktree через `bash templates/food-daily/bin/food-daily <команда>`.

## Preview (только этот сайт)

```bash
bash templates/food-daily/bin/food-daily start     # http://127.0.0.1:8847/ (только петля)
bash templates/food-daily/bin/food-daily status    # pid и /healthz
bash templates/food-daily/bin/food-daily stop      # останавливает только свой pid (проверка cmdline)
bash templates/food-daily/bin/food-daily editor-init   # учётка редактора: ~/.config/food-daily-preview/ (0600)
```

Редактор: `http://127.0.0.1:8847/redaktor/` (Basic Auth, пароль в
`~/.config/food-daily-preview/editor-password.txt`).
Доступ с рабочей машины — SSH-туннель на порт 8847 (наружу preview не слушает).

## Сбор и импорт (возобновляемые, с лимитами из `config/crawl.yaml`)

```bash
food-daily inventory [--host ID] [--max-sitemaps N] [--max-seconds S]   # карты сайтов → var/food-daily/crawl/<host>
food-daily catalog --host iamcook --max-pages 2500 --max-seconds 5400   # продолжает с catalog-state.json
food-daily counts --export          # docs/audit/competitor-counts.csv + data/inventory/*.jsonl.gz
food-daily verify-sample --hosts eda-rambler --n 12
food-daily topics                   # data/topic-map.csv со статусами обработки
food-daily import plan --hosts eda-rambler --topics 134   # план: по одному URL на тему, без уже импортированных
food-daily import run [--limit N]   # загрузка → факты → закрытое хранилище
food-daily import reextract         # новая версия парсера по закрытому хранилищу, без сети
food-daily import retopic | status | purge-expired
```

Лимиты: 1 запрос на хост, пауза 1,5 с, 3 попытки, Retry-After ≤ 300 с,
ответ ≤ 50 МиБ, ≤ 5400 с и ≤ 1 ГиБ на хост. Хост вне allowlist, не-https,
редирект на петлю/частную сеть — отказ.

## Редакционный цикл и откат

```bash
food-daily qwen export <record_id...>     # задания в var/food-daily/qwen/outbox (повтор → тот же job_id)
food-daily qwen import --inbox <dir>      # проверка и импорт; повтор того же ответа → noop
food-daily editorial publish-preview --all   # ворота публикации; неправдоподобные факты блокируются
food-daily editorial diff <content_id> 1 2
food-daily editorial rollback <content_id> --to 1   # откат = новая версия с содержимым v1
food-daily editorial review <content_id> --status editor_approved --reviewer "<имя человека>" --version N
food-daily editorial snapshot             # data/content-snapshot.json — единственный вход сайта
food-daily restart                        # preview перечитывает снимок
```

## Видео

```bash
food-daily video validate | register | dispatch | status | mark-stale
```

## Проверки и сборка

```bash
food-daily test                           # pytest шаблона, временные файлы — var/food-daily/pytest
python3 -m fooddaily.qa_browser --shots docs/screenshots/<commit> --out docs/verification/browser-qa.json   # из templates/food-daily, при запущенном preview
food-daily build --commit HEAD            # var/food-daily/build/<sha>/ + manifest.json
```
