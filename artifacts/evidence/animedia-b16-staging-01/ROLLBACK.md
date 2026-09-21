# Откат B16 на animedia.space

Цель отката проверена: релиз
`/srv/lords/.frontend/releases/20260921T154512Z-8966632-animedia-rollback`
содержит артефакт `d2e9628f…` — ровно тот, который `animedia.space` отдаёт
сейчас. Это не «какая-то прежняя сборка», а именно текущая.

Откат нужен только если после перезапуска `nova-animedia-02.service` витрина
не совпала с ожидаемым: другой `build_id`, другой `artifact_sha256`,
изменившаяся индексация, 5xx или пустая выдача.

## Порядок

Шаги 1 и 2 выполняются до перезапуска; сам перезапуск — шаг 3.

**1. Вернуть назначение.** Ссылка переставляется через временное имя и
`mv -T`, а не удалением и созданием заново: между `rm` и `ln` витрина остаётся
без назначения, и перезапуск в этот момент поднял бы её на запасном пути.

```bash
ln -sfn ../../releases/20260921T154512Z-8966632-animedia-rollback \
        /srv/lords/.frontend/sites/animedia-02/current.new
mv -T /srv/lords/.frontend/sites/animedia-02/current.new \
      /srv/lords/.frontend/sites/animedia-02/current
```

**2. Вернуть манифест.**

```bash
cp /srv/lords/.frontend/template-manifest-animedia-02.json.before-b16 \
   /srv/lords/.frontend/template-manifest-animedia-02.json
```

**3. Перезапустить.**

```bash
systemctl restart nova-animedia-02.service
```

## Проверка отката

```bash
python3 scripts/reconciliation/animedia_state.py
```

Ожидается на порту 9122:

| Поле | Значение |
| --- | --- |
| `build_id` | `20260920T102102Z-89666321-nova` |
| `artifact_sha256` | `d2e9628f2a4b14c56ef28a6814b53f49cdb4017db1ab8ddebebb79aaad39e908` |
| `revision` | `89666321093651d4bd5b06a00645fdf903124810` |
| `X-Robots-Tag` | `noindex, nofollow` — не меняется ни при выкладке, ни при откате |

## Чего откат не касается

`animedia.icu` (`animedia-01`, порт 9121) уже работает на B16 и в откате не
участвует. Ссылка и манифест у него отдельные, поэтому откат `animedia-02`
физически не может его задеть — ровно ради этого загрузчик и разделил витрины
по `sites/<витрина>/current`.

Ни DNS, ни TLS, ни индексация в откате не участвуют.
