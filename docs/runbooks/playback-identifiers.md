# Идентификаторы плеера: как посмотреть, изменить и откатить

Отвечает на три вопроса дежурного: чем сейчас разрешено адресовать плеер,
почему у карточки нет видео и как вернуть прежнее состояние.

## Что сейчас разрешено

```
curl -sH "Authorization: Bearer $TOKEN" http://127.0.0.1:8790/api/v1/playback-policy
```

```json
{
  "allowed": ["kp", "mali", "mdl"],
  "baseline": ["kp", "mali", "mdl"],
  "policyVersion": "1.0.0",
  "contractVersion": "CDNVIDEOHUB_KNOWLEDGE_PACK_v1.0",
  "beyondBaseline": [], "disabled": [], "outOfScope": [],
  "flags": [{"identifier": "imdb", "enabled": false, "authorization": "absent"}]
}
```

`allowed` — действующий перечень. `baseline` — что разрешает документ
поставщика. `beyondBaseline` непусто только при наличии записи авторизации.

Ответ **409** `playback_policy_conflict` означает, что настройка противоречит
контракту: включён идентификатор без авторизации или указана чужая версия
документа. Служба при этом продолжает работать на прежнем каталоге — витрина не
страдает, но новые дескрипторы не строятся.

Без Control API то же самое:

```
.venv/bin/python -c "from factory.site_engine import playback_policy as p; print(p.resolve().as_dict())"
```

## Почему у карточки нет видео

```
curl -sH "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8790/api/v1/content-health/lords-01?code=IDENTIFIER_FORBIDDEN_BY_CONTRACT"
```

Замер по всему массиву с разбивкой:

```
.venv/bin/python automation/host/playback-coverage.py --json /tmp/coverage.json
```

Ключевые коды:

| Код | Что делать |
|---|---|
| `IDENTIFIER_FORBIDDEN_BY_CONTRACT` | ничего в коде. Решение владельца контракта |
| `IDENTIFIER_DISABLED_BY_POLICY` | включить в `config/playback-identifiers.yaml`, если так и задумано |
| `IDENTIFIER_OUT_OF_SCOPE` | расширять область только с доказательством отсутствия смешения |
| `MISSING_PROVIDER_ID` | у поставщика нет идентификатора. Ждать |
| `UNSUPPORTED_AGGREGATOR` | наш пробел в сопоставлении |

## Как включить идентификатор

Только при наличии подтверждения от поставщика или владельца.

```yaml
# config/playback-identifiers.yaml
imdb:
  enabled: true
  authorization:
    status: granted
    granted_by: "<кто>"
    granted_at: "<когда>"
    evidence: "<чем подтверждено>"
```

Без `status: granted` ворота отвечают отказом. Переменная окружения
(`PLAYBACK_IDENTIFIER_IMDB=1`) ворота **не обходит**: флаг включает, но не
разрешает.

Порядок: сначала canary, сверка type/title/year на выборке, затем остальные
витрины.

## Откат

Вернуть `enabled: false`. Перезапуск службы не нужен: перечень кэшируется по
времени изменения файла.

Дескрипторы, уже лежащие в каталоге, снимаются при следующей записи каталога —
`content_live.сверить_с_политикой`. Дожидаться полного обхода не требуется:

```
systemctl start lords-content-refresh.service
journalctl -u lords-content-refresh.service | grep playback-policy
# [playback-policy] снято дескрипторов: {'imdb': 645}
```

Проверка, что каталог чист:

```
.venv/bin/python -c "
import json,glob
for f in sorted(glob.glob('var/lords/lords/catalog-cache/*.json')):
    d=json.load(open(f))
    print(f, d.get('playback_policy_stripped'))"
```

Карточки при откате **не исчезают** — снимается только дескриптор, страница
остаётся с заглушкой.

## Чего делать нельзя

Расширять `ALLOWED_AGGREGATORS` в коде, править `allowed` в
`knowledge/*/PLAYER_CONTRACT.yaml` (полученный документ, под freeze),
подставлять идентификатор другого тайтла, включать `cvh` для сериалов —
поставщик возвращает по нему франшизу целиком, и зритель увидит не тот сезон.
