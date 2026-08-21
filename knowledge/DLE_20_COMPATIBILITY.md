# DLE_20_COMPATIBILITY — совместимость и требования DataLife Engine 20.0

Статус документа: **частично заполнен**. Официальная документация DLE
(`https://dle-news.com/extras/online/`) и лицензионное соглашение недоступны из этой
сессии: egress-политика организации отвечает 403 на CONNECT к `dle-news.com` (см. F3.3).
Мастер-промпт запрещает подменять официальный факт блогом или пересказом, а правило §3.8
запрещает угадывать writable-пути. Поэтому все поля, требующие первоисточника, оставлены
как **обязательные к заполнению** и подключены к машинно-проверяемому профилю
`blueprints/dle20/profiles/paths.template.yaml`.

## 1. Что зафиксировано

| Пункт | Значение | Источник |
|-------|----------|----------|
| Квалифицируемая версия | DataLife Engine 20.0 (релиз 29.05.2026) | утверждение пользователя (F5.1) |
| Автоматический переход на более новую версию | запрещён; требуется отдельная compatibility-проверка и новый knowledge freeze | §3.1 мастер-промпта |
| Источник дистрибутива | только официальный лицензионный архив, переданный пользователем; поиск и скачивание сторонних/nulled-сборок запрещены | §3.2 |
| Контроль целостности | SHA-256 каждого дистрибутива фиксируется в `inventory/dle-distributions.yaml`; сам архив в git не попадает (`.gitignore`: `blueprints/dle20/dist/`) | §3.3 |
| Лицензионное покрытие | одна лицензия = один домен второго уровня + его поддомены | утверждение пользователя (F5.2) |
| Модификация ядра | запрещена без отдельного документированного решения; расширения — через официальную plugin system / virtual file system, шаблоны и поддерживаемые точки расширения | §3.5 |
| Изоляция | отдельные database/schema и DB user на каждый сайт; там, где позволяет инфраструктура — отдельные Unix users, PHP-FPM pools, каталоги, логи и лимиты | §3.6, §3.7 |
| Права доступа | world-writable в production запрещены; веб-процессу выдаётся минимально необходимое и проверяется автотестом | §3.9 |
| Backup | перед установкой, обновлением, миграцией и переключением релиза; восстановление проверяется регулярно, наличие файла бэкапа доказательством не считается | §3.10, §8.8 |
| Идемпотентность | повторный запуск не создаёт дубль сайта, БД, cron job, сертификата или DNS-записи | §3.11 |
| Installer | удаляется/блокируется сразу после успешной установки согласно официальной документации | §3.12 |
| Cron | только из декларативного manifest, без дублей, с lock, timeout, логом и контролируемым retry | §3.13 |

## 2. Что обязано быть получено из официального источника

Эти значения **не заполняются по догадке**. До их получения `factory` возвращает
`BLOCKED_INPUT` на шаге установки DLE.

| Поле профиля | Что требуется | Куда |
|--------------|---------------|------|
| `php.min_version`, `php.required_extensions`, `php.forbidden_settings` | системные требования DLE 20.0 | `profiles/paths.yaml: runtime.php` |
| `database.engine`, `database.min_version`, `database.charset`, `database.collation` | требования к СУБД | `profiles/paths.yaml: runtime.database` |
| `writable_paths[]` | полный перечень изменяемых каталогов и файлов | `profiles/paths.yaml: writable_paths` |
| `immutable_paths[]` | код релиза, который остаётся неизменяемым | `profiles/paths.yaml: immutable_paths` |
| `shared_paths[]` | uploads, cache, logs, config — переживают смену релиза | `profiles/paths.yaml: shared_paths` |
| `installer_entrypoints[]` | точки входа установщика, которые удаляются/блокируются после установки | `profiles/paths.yaml: installer_entrypoints` |
| `public_deny_paths[]` | пути, закрываемые от публичного доступа (конфиги, бэкапы, служебные manifest, логи, debug) | `profiles/paths.yaml: public_deny_paths` |
| `cron_jobs[]` | штатные cron-задачи DLE, их расписание и точки входа | `blueprints/dle20/cron/jobs.yaml` |
| `template_structure` | структура каталога шаблонов и перечень обязательных файлов | `profiles/paths.yaml: template_structure` |
| `plugin_api` | контракт plugin system / VFS для белого VK-плеера | `profiles/paths.yaml: plugin_api` |
| `update_procedure` | официальная процедура обновления и миграций БД | `docs/UPDATE.md` |
| `webserver.nginx`, `webserver.apache` | официальные рекомендации по конфигурации, включая SEO-URL | `blueprints/dle20/webserver/` |

## 3. Как проверяется

```bash
python3 -m factory blueprint check --blueprint dle20     # профиль заполнен и непротиворечив
python3 -m factory validate --site <site_id>             # BLOCKED_INPUT, если профиля нет
pytest tests/unit/test_blueprint_profile.py -q
```

Тест `tests/unit/test_blueprint_profile.py` гарантирует, что шаблон профиля содержит
только пустые значения с флагом `source_required: true` и что фабрика отказывается
устанавливать DLE по незаполненному профилю. Это защищает правило §3.8 от «тихого»
заполнения догадками.
