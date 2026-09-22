# ROLLBACK — откат канарейки animedia.space

Откат нужен только при функциональной аварии: 5xx, недоступность маршрутов,
пропажа контента, поломка плеера или нарушение индексации. Визуальное
несогласие — не авария: тогда канарейка остаётся, а правка идёт следующим
релизом.

`animedia.icu` в этой стадии не менялась и откату не подлежит.

## Куда откатываем

| Что | Значение |
| --- | --- |
| Витрина | animedia-02 (animedia.space), `nova-animedia-02.service` |
| Релиз отката | `20260921T214937Z-fac5643-animedia-parity` |
| Артефакт отката | `826f54a2c8a743fb517852917aa713c579d1be38848d2c0ee3c26cc82e0e425f` |
| Резерв манифеста | `/srv/lords/.frontend/template-manifest-animedia-02.json.before-ux-rebuild.20260922T123345Z` |

## Порядок

Первые два шага выполняются без root — это файлы контура.

```bash
# 1. Вернуть манифест из резерва
cp /srv/lords/.frontend/template-manifest-animedia-02.json.before-ux-rebuild.20260922T123345Z \
   /srv/lords/.frontend/template-manifest-animedia-02.json

# 2. Вернуть assignment на прежний релиз
ln -sfn ../../releases/20260921T214937Z-fac5643-animedia-parity \
   /srv/lords/.frontend/sites/animedia-02/current.tmp
mv -T /srv/lords/.frontend/sites/animedia-02/current.tmp \
      /srv/lords/.frontend/sites/animedia-02/current
```

Третий шаг — действие владельца под root:

```bash
systemctl restart nova-animedia-02.service
```

## Проверка после отката

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://animedia.space/
curl -s -H 'Host: animedia.space' http://127.0.0.1:9122/__template_version
```

Ожидается код 200 и `build_id` = `20260921T214937Z-fac5643-animedia-parity`.

## Что откат не трогает

Каталог релиза остаётся на диске: релизы неизменяемы, и удалять тот, на
который можно вернуться, нельзя. Снимки каталога, реестр событий и топ по
оценкам лежат рядом со снимком и от версии витрины не зависят — откат их не
затрагивает. Хранилище сообщества живёт в каталоге данных витрины и при
откате сохраняется: голоса и сообщения посетителей не пропадают.
