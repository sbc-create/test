# Владение

У каждой таблицы, файла, очереди и маршрута есть один владелец. Владелец —
единственный, кто пишет; остальные читают через контракт.

## Файлы состояния

| Объект | Владелец | Читатели |
| --- | --- | --- |
| `var/lords/lords/catalog-cache/*.json` | Content Engine | Site Engine, ворота, быстрый путь |
| `var/lords/detail-cache/*.json` | Content Engine (обогащение) | быстрый путь, ворота |
| `var/lords/playability.json` | Content Engine (проверка потока) | быстрый путь, ворота |
| `var/lords/render-state/*.fingerprint.json` | ворота рендера | ворота |
| `var/lords/render-state/*.titles.json` | быстрый путь | быстрый путь |
| `var/lords/routes/*.json` | Site Engine (реестр адресов) | рендер, ворота |
| `/srv/lords/<site>/releases/*` | Publishing Engine | nginx |
| `/srv/lords/<site>/current` | Publishing Engine | nginx |
| `/var/cache/nginx/yummy-posters` | Media Engine (nginx) | браузеры |
| `/var/lib/yummy/catalog-index/*.json` | Scheduler Engine (фоновая синхронизация) | сторож |
| Redis `catalog:year-index:*` | фоновая синхронизация Yummy | витрины Yummy |
| `config/site-profiles/*.json` | Site Engine | все движки |

## Модули кода

| Модуль | Владелец | Граница |
| --- | --- | --- |
| `factory/site_engine/contracts.py` | Site Engine | общий словарь; менять только версионированно |
| `factory/site_engine/profiles.py` | Site Engine | `SiteProfile` |
| `factory/site_engine/fingerprint.py` | Publishing Engine | отпечаток входа |
| `factory/site_engine/incremental.py` | Publishing Engine | связанные копии релизов |
| `factory/site_engine/publish.py` | Publishing Engine | атомарная подмена |
| `factory/site_engine/access.py` | Control Plane | права |
| `factory/site_engine/commands.py` | Control Plane | команды |
| `factory/site_engine/audit.py` | Control Plane | аудит |
| `factory/site_engine/api/*` | Control Plane | внешний договор |
| `factory/site_engine/cms/*` | Control Plane | интерфейс |
| `factory/lords/render.py` | Site Engine (Lords) | построение страниц |
| `factory/lords/fast_path.py` | Publishing Engine (Lords) | точечная пересборка |
| `factory/seo/*` | SEO Engine | документы SEO |

## Правило импорта

Импорт внутренностей чужого движка запрещён и проверяется автоматически
(`factory/site_engine/boundaries.py`). Текущее число нарушений: **0**.

Пакет `api` объявлен приватным: снаружи движка его не импортируют.

## Кто с кем разговаривает

Измеренная карта зависимостей (число импортов):

```
factory → paths 18   secret_hub → errors 14   factory → errors 13
factory → seo 11     factory → lords 11       lords → paths 9
analytics → errors 6 factory → redaction 5    recs → lords 3
lords → seo 3
```

`lords → seo` — рендер обращается к SEO-документам. Это единственное место, где
слои соприкасаются, и оно намеренно однонаправленное: SEO не знает о рендере.
