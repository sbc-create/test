# Открытые блокеры фабрики

Живой список того, что не закрыто. Запись остаётся здесь, пока блокер не снят:
проверка, которая не выполнялась, не должна выглядеть как пройденная.

Формат: что не работает, чем это подтверждено, что блокирует, что нужно для
снятия.

## PC-SITE-D — контракт плеера на site-d-series не проверен

**Статус:** открыт.
**Подтверждение:** задание `site-d-series-create-20260823T060816Z-0c5a63`,
артефакт `artifacts/verify/site-d-series/site-d-series-create-20260823T060816Z-0c5a63/player-contract.json`:

```json
{"pages": 3, "players_rendered": 0, "status": "skipped",
 "reason": "ни на одной странице серии плеер не отрисован"}
```

Проверены три страницы серий (`/catalog/dvenadcat-pisem/season-1/episode-1..3/`).
Плеер не найден ни на одной, поэтому ворота `player-contract` записали
`skipped`, а не `passed`: ноль отрисованных плееров — это непроведённая
проверка, а не «нарушений нет».

**Что блокирует:** `DONE` для `site-d-series` и любой выкат этого сайта на
production. Слияние программного контура он не блокирует — код фабрики и
оператора от него не зависят.

**Что нужно для снятия:** разобраться, почему на странице серии не появляется
элемент плеера в стенде site-d-series (маршрут, данные `videoRef` или условие
показа), затем прогнать `python3 -m factory verify --site site-d-series` и
получить `status: executed` с ненулевым `players_rendered`.

**Чего делать нельзя:** понижать критичность ворот, объявлять `skipped`
успехом или проверять контракт на другом сайте вместо этого.

## HEADLESS-AUTH — `claude -p` на сервере не авторизован

**Статус:** открыт.
**Подтверждение:** `claude -p --bare --settings .claude/settings.json "ok"` на
`claude-control-01` возвращает `{"is_error": true, ..., "result": "Not logged in · Please run /login"}`.
Интерактивная сессия при этом работает: учётные данные существуют, но headless-запуск
их не подхватывает.

**Что блокирует:** запуск оператора по расписанию как Claude-сессии — и Routine,
и резервный вариант из `docs/seo-operator/automation-policy.md`. Не блокирует
ничего из того, что выполняется без Claude: таймеры `site-factory-health`,
`site-factory-backup`, `site-factory-selfcheck` и `site-factory-seo-dryrun`
работают, потому что вызывают Python и shell напрямую.

**Что нужно для снятия:** владелец выполняет авторизацию для headless-режима на
самом сервере. Токен в чат не передаётся и в репозиторий не попадает.

**Чего делать нельзя:** извлекать учётные данные интерактивной сессии из
`~/.claude/.credentials.json` и подставлять их в headless-запуск.

## SANDBOX-NOTE — `settings.unattended.json` теперь применим на сервере

**Статус:** информационный, действия не требует.
**Подтверждение:** `bwrap --version` → 0.6.1, `kernel.unprivileged_userns_clone = 1`,
пробный `bwrap --unshare-all` завершается успешно.

Комментарий в `.claude/settings.unattended.json` говорит, что `bubblewrap`
отсутствует, и это верно для контейнера сессии. На `claude-control-01` он
установлен и работает, поэтому профиль с `sandbox.failIfUnavailable: true`
здесь запускается, а не останавливается на старте. Сам файл не правился:
`.claude/**` закрыт deny-правилом.

## Переданные владельцем данные, которых нет

Не блокеры кода, а отсутствующие входные данные. Полный машинный список —
`docs/INPUT_REQUEST.md` (`python3 -m factory input-request`).

| Чего нет | Что это закрывает |
| --- | --- |
| Домены и цели выката | production для всех сайтов |
| SSH-хосты в `inventory/ssh-hosts.yaml` | удалённый выкат, backup на цели |
| DNS-зоны в `inventory/dns-zones.yaml` | cutover, выпуск SSL |
| Контракты CDNVideoHub, CMS, VK, аналитики и хосты в `inventory/network-allowlist.yaml` | живые источники, health-check боевого сайта |
| Лицензия DLE (`dle_license_ref`) | production для DLE-пакетов |
| Права на контент и rights manifest | публикацию контента |
| `production_authorized: true` в manifest | production в принципе |

Пустая запись в реестре означает `BLOCKED_INPUT`, а не «разрешено всё».
