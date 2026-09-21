# COMMUNITY-RATINGS-08 — команда владельца

Релиз собран, проверен запуском и лежит в `/srv/lords/.frontend/.cr08-release`.
Осталось ровно одно действие, которое сессия выполнить не может: установка
root-файла и перезапуск двух units.

## Почему сессия не выполнила это сама

| | |
| --- | --- |
| `/srv/lords/.frontend/yummy-frontend.py` | `root:root 0755` — не доступен на запись |
| `sudo` | заблокирован guard'ом: `[factory-guard G-PRIV] Неконтролируемый sudo/su запрещён` |
| `systemctl restart` | требует root |

Каталог `/srv/lords/.frontend` доступен на запись (`claude:claude 0755`), то есть
файл технически можно было бы подменить через unlink+create. Это не сделано
намеренно: так root-файл среды молча стал бы файлом другого владельца, а это
обход привилегированной границы, а не деплой.

## Ровно один unit обслуживает домен

`nova-yummy-site.service` → `yummyani.site` (`YUMMY_VARIANT_DOMAIN=yummyani.site`,
порт 9132). `nova-yummy-org.service` и `nova-yummy-biz.service` не трогаются.

Второй unit в команде — `community-ratings-gateway.service`: он уже работает из
`/home/claude/wt-ratings-ingestion-01`, поэтому новый код у него на диске, но в
памяти до перезапуска остаётся старый. Без перезапуска не появится ни
`/widget-event`, ни запись в metrics store.

## Команда

```bash
install -o root -g root -m 0755 /srv/lords/.frontend/.cr08-release/yummy-frontend.py /srv/lords/.frontend/yummy-frontend.py && install -o root -g root -m 0644 /srv/lords/.frontend/.cr08-release/community_widget_inject.py /srv/lords/.frontend/community_widget_inject.py && install -d -o root -g root -m 0755 /srv/lords/.frontend/community-assets && install -o root -g root -m 0644 /srv/lords/.frontend/.cr08-release/community-assets/community_rating.js /srv/lords/.frontend/.cr08-release/community-assets/community_rating.css /srv/lords/.frontend/community-assets/ && systemctl restart nova-yummy-site.service community-ratings-gateway.service && sleep 3 && systemctl is-active nova-yummy-site.service community-ratings-gateway.service && curl -sS -o /dev/null -w 'title=%{http_code}\n' https://yummyani.site/anime/padshiy-master && curl -sS -o /dev/null -w 'asset=%{http_code}\n' https://yummyani.site/assets/community/community_rating.js && curl -sS https://yummyani.site/anime/padshiy-master | grep -c 'cr-widget-loader'
```

Ожидаемый хвост вывода: `active`, `active`, `title=200`, `asset=200`, `1`.

## Проверяемые digest'ы

| файл | sha256 |
| --- | --- |
| `yummy-frontend.py` | `599c72c03961807dd3288563a134d510f7ed2ef992a18cc2001eda73c779c67a` |
| `community_widget_inject.py` | `b89aa789c9306f0da97c8dc8d43f966b203daec6f609edaab44617711aaf2928` |
| `community_rating.js` | `93fe1b78cfaa604c643ccc3b5773db2c6e12af72633ef44daeb920748b06bf4d` |
| `community_rating.css` | `6ea4dd3898fb2f1b93800482509e34acaaf874bf73eca4fb48d23b039e1ca113` |

`yummy-frontend.py` собран **из живого файла** (база
`60aa6158126f6152f7ec6daeba896196f0fecf53d28caa0b4894e394ded54438`), а не из
копии репозитория. Копия репозитория отстала по другой линии: в ней нет
`nova_core_indexability`, и установка её поверх откатила бы Core-источник правды
об индексации — то есть риск закрыть `yummyani.site`, что этим этапом запрещено.
Добавлено 5953 байта, семь именованных патчей, каждый якорь проверен на
единственность.

## Если restart отвечает `Failed to allocate directory watch: Too many open files`

Это сообщение само по себе не означает провал. Проверить в таком порядке:

```bash
systemctl show -p MainPID -p ActiveState -p SubState -p ExecMainStartTimestamp nova-yummy-site.service
curl -sS https://yummyani.site/anime/padshiy-master | grep -c 'cr-widget-loader'
```

Новый PID, `ActiveState=active`, свежий timestamp и `1` в последней строке
означают, что выкладка прошла. Повторный restart без этой проверки не нужен.

## Откат

Мгновенный, без перезапуска и без прав:

```bash
python3 -c "import sys; sys.path.insert(0,'/home/claude/wt-ratings-ingestion-01'); from factory.community.rollout import trigger_kill_switch; trigger_kill_switch('cr08 rollback')"
```

Проверено: с `KILL_SWITCH=1` инжектор перестаёт отдавать узел (1 → 0), после
снятия — возвращает.

Полный откат бинаря:

```bash
install -o root -g root -m 0755 /srv/lords/.frontend/.rollback/yummy-frontend.py.before-cr08.20260921T141150Z /srv/lords/.frontend/yummy-frontend.py && systemctl restart nova-yummy-site.service
```

## После выкладки

Окно наблюдения **не стартует по факту установки**. Оно начинается только когда
одновременно выполнено: виджет на странице, активы отдаются, 1% когорта реально
его получает, и монитор видит `eligible impression` и `widget rendered`.
Скрипт проверки и запуска окна:

```bash
python3 /home/claude/wt-ratings-ingestion-01/artifacts/evidence/community-ratings-08/06-observation/start_observation.py
```

Он ничего не включает: только проверяет условия и, если все выполнены,
записывает отметку начала в evidence.

## Необязательное усиление

`COMMUNITY_METRICS_PEPPER_FILE` не задан, поэтому HMAC уникальности посетителей
использует dev-значение по умолчанию. Identity id и так непрозрачны и случайны,
так что риск низкий, но при следующей правке
`/usr/local/bin/community-ratings-gateway` стоит добавить:

```
export COMMUNITY_METRICS_PEPPER_FILE=/etc/site-factory/secrets/community_ip_hmac
```

Существующий секрет, новый выдумывать не нужно.
