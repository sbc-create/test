# Передача: изменения общих контрактов очереди, моста и доставки

Кому: Архитектор (контракты редакционной очереди, моста MCP, доставки).
От кого: SEO-модуль, ветка `claude/indexing-operation-02`.
Дата: 2026-10-08.

Файлы очереди (`wt-seo-index-audit-20260930`, `seo_engine/content_operator`) и
моста (`factory/qwen/mcp.py`) я НЕ менял: это общие контракты. Ниже — что
найдено на реальных данных, что нужно и как проверить. Обнаружение всех
случаев уже работает в SEO-модуле (`seo_operator/regular.py::queue_hygiene`,
`verify_task_targets`) и попадает в суточный отчёт — после вашего изменения
отчёт сам покажет, что дубли пропали.

## 1. Нормализация адреса при регистрации задания (MOD-08, MOD-09)

**Пример.** `/var/lib/seo-content-operator/registry.json`:

| content_id | canonical_url | статус | ответ сайта |
| --- | --- | --- | --- |
| request-fa190135f85d72c9 | https://yummyani.org/anime/ledyanaya-stena-2 | BLOCKED_INSUFFICIENT_FACTS | 200 |
| request-b74982172ba225a2 | /anime/ledyanaya-stena-2 | READY_VERIFIED | (та же страница) |
| request-61ce6f9a15437cba | https://yummyani.site/anime/neveroyatnoe-priklyudenie-…/season/7/episode/3 | NEEDS_UPDATE | **404** (опечатка) |
| request-d95607c97ecfdd6a | /anime/neveroyatnoe-priklyuchenie-…/season/7/episode/3 | NO_TARGET_PAGE | **200** |
| request-01b4575857beada5 | https://lordfilm47.space/title/specnaz-novobrancy | NEEDS_UPDATE | **308** → форма со слешем |

**Нужно.** `editorial_queue_register` приводит адрес к абсолютной канонической
форме семейства (`factory.qwen.registry.адрес_тайтла`, 308 — заменить целью
редиректа), ищет существующее живое задание по нормализованному ключу и
отклоняет адрес, который не отвечает 200, с названной причиной.

**Проверка.** Повторная регистрация `/anime/ledyanaya-stena-2` для yummyani.org
возвращает `task_register_existing` с `request-fa19…`; регистрация 404-адреса —
отказ. В суточном отчёте SEO: «живых дублей одной страницы: 0».

## 2. Роль владельца при выдаче задания (MOD-10)

**Пример.** `queue_events.jsonl`, сутки до 2026-10-08T11:16Z: 46 выдач
(`task_claimed`) владельцам `seo-analysis-*`, `seo-audit-*`, `seo-analyzer-*`;
18 из 25 адресов брали несколько владельцев. Адрес
`yummyani.site/anime/asy-i-malenkaya-lindan` с 2026-10-06 брали 17 владельцев.

**Нужно.** Распределение принято в `docs/SEO_REGULAR_RUN.md` §3: SEO-исполнитель
регистрирует и ищет, берёт и закрывает только редактор. В контракте —
обязательное поле роли у `editorial_queue_next` (`editor`) с отказом для иной
роли; имя владельца вида `<роль>/<автоматизация>/run-<id>`.

**Проверка.** Суточный отчёт SEO: «заданий, взятых SEO-владельцами: 0».

## 3. task_id в публикации (MOD-11)

**Пример.** animedia.space/title/detektivnoe-agentstvo-li/ опубликован
2026-10-07T09:32:13Z (`/srv/sites/animedia/runtime/overlays/animedia.space/history.jsonl`),
задание на этот адрес зарегистрировано в 09:31; в `registry.json` последний
`published_at` — 2026-09-21. `publish_material`/`publish_post` не принимают
`task_id` и в журнал очереди не пишут.

**Нужно.** Необязательный `task_id` в `publish_material`/`publish_post`; при
наличии — событие `task_published` в `queue_events.jsonl` с адресом, отпечатком
тела и `generation_id`.

**Что уже сделано на стороне SEO.** Каждая публикация, впервые подтверждённая
на сайте, получает исходные показатели из снимка до публикации и оценку через
7 дней по непересекающемуся окну (`state.changes`). Связь с заданием появится,
когда мост начнёт её писать.

## 4. zonafilm.cc: каталог не доставляется с 2026-09-28 (доставка)

**Обнаружено** суточным шагом sitemap (`SITEMAP_LASTMOD_OLD`, MOD-07):
`https://zonafilm.cc/sitemap-1.xml` — 53 916 адресов, самый свежий `lastmod`
2026-09-27; у zonafilm.space и zonafilm12.site — 2026-10-08, 60 707 адресов.

**Причина на диске** (`ls -la --time-style=long-iso`, 2026-10-08 ~11:30Z):

| файл | изменён |
| --- | --- |
| `/srv/zonafilm-cc/data/zona-02-catalog.json` | **2026-09-28 03:56** |
| `/srv/zonafilm-cc/data/zona-02-details.json` | 2026-09-29 07:46 |
| `/srv/zonafilm-space/data/zona-01-catalog.json` | 2026-10-08 04:01 (root) |

Таймера обновления у ячейки `zona-02` нет (в `/etc/systemd/system` есть
`*-update.timer` только у AnimeGo и Animedia). Это тот же класс, что D197
(«каталог ячейки доставляет её обновлятор»): каталог zonafilm.space кто-то
кладёт ежедневно, а zonafilm.cc в этот круг не входит.

**Нужно.** Доставка каталога `zona-02` тем же механизмом, что у `zona-01`, или
обновлятор ячейки по D197. Данные ячейки я не трогал: каталог — постоянные
данные сайта, сборка и SEO-модуль их только читают.

**Проверка.** Суточный отчёт SEO перестаёт называть zonafilm.cc в разделе
«Остановившиеся обновления»; `lastmod` в sitemap не старше суток.

## Чего я не делал

Не менял очередь, мост, реестры, журналы и данные сайтов; не снимал аренды;
не регистрировал и не брал задания.
