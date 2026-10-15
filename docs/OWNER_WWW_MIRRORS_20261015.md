# Зеркала `www` трёх живых домен отдают второй сайт: измерение и операция

Запись от 2026-10-15. Пункт заявлялся 12 октября как «www-зеркала четырёх
доменов отдают 200, `index` и self-canonical». Перед просьбой к владельцу
состояние перемерено: за трое суток сеть менялась, и список изменился.

## Что измерено сейчас (14 домен сети, `https://www.<домен>/`, без следования переходам)

| состояние | домены |
| --- | --- |
| **дубль: 200 и canonical на САМ www-хост** | `zonafilm.cc`, `zonafilm12.site`, `lordserials22.info` |
| 200, но canonical на апекс (сигнал верный, адресов два) | `yummyani7.site`, `yummyani7.info` |
| 308 на апекс — норма | `lordfilm47.space`, `lordserial33.biz`, `1lordserials1.online`, `yummyani.site`, `yummyani.org`, `yummyani.biz` |
| имени `www` в DNS нет вовсе — дубля быть не может | `zonafilm.space`, `animedia.icu`, `animedia.space` |

Дефект подтверждён у **трёх** домен, а не у четырёх. Чем он опасен: поисковик
видит два сайта с одинаковым содержимым и сам выбирает, какой считать
основным; у `lordserials22.info` это ещё и домен из партии шести назначений,
то есть страница с плеером доступна по двум адресам.

## Операция владельца (root на `claude-control-01`)

Правильная раскладка в проекте уже есть — её генерирует
`automation/local/stage-k2-cell-artifacts.py` для партии K2: `www` стоит
ОТДЕЛЬНЫМ блоком с `301` на апекс, и путь ACME в нём сохранён (подтверждение
владения именем `www` нужно сертификату). Для трёх живых домен нужен тот же
блок. Ниже — готовый текст; `<ВИТРИНА>` в имени переменной режима
индексации подставляется по той витрине, которой домен принадлежит
(`$cell_robots_<site_id с подчёркиваниями>`), как в уже установленных файлах.

```nginx
# /etc/nginx/lords/<site_id>-www.conf — www отдельным блоком, 301 на апекс.
server {
    listen 80;
    listen [::]:80;
    server_name www.<домен>;

    server_tokens off;
    add_header X-Robots-Tag $cell_robots_<ВИТРИНА> always;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type "text/plain";
    }

    location / {
        return 301 https://<домен>$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name www.<домен>;

    ssl_certificate     /etc/letsencrypt/live/<домен>/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/<домен>/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    server_tokens off;
    add_header X-Robots-Tag $cell_robots_<ВИТРИНА> always;

    location / {
        return 301 https://<домен>$request_uri;
    }
}
```

Порядок (по одному домену, чтобы отказ не задел соседей):

```bash
# host: claude-control-01, от root
# 1. Убрать имя www из блока апекса, если оно стоит там (именно это и даёт 200).
#    Файл витрины: /etc/nginx/lords/<site_id>.conf — строка server_name.
# 2. Положить блок выше в /etc/nginx/lords/<site_id>-www.conf
# 3. Сертификат обязан покрывать имя www; если он его не покрывает:
certbot certonly --webroot -w /var/www/certbot -d <домен> -d www.<домен> \
    --cert-name <домен> --non-interactive --agree-tos -m <почта владельца>
# 4. Проверка и перезагрузка — в этом порядке:
nginx -t && systemctl reload nginx
```

Проверка результата (моя сторона, без прав):

```bash
python3 automation/local/public-acceptance.py zonafilm.cc zonafilm12.site lordserials22.info
```
В приёмке теперь есть шаг `www → апекс`: он ждёт `301`/`308` и `Location` на
апекс, и до правки честно показывает расхождение.

## Про пару Yummy

`www.yummyani7.site` и `www.yummyani7.info` отвечают 200, но canonical ведёт
на апекс — поисковику сигнал дан верный, дубля в индексе быть не должно. Это
не дефект того же рода, и в один список с тремя выше он не ставится. Привести
их к `301` всё же стоит (два живых адреса вместо одного), но это правка
контура верхнего приложения, а не nginx витрины, и она идёт отдельно от этой
операции.

## Чего эта запись не делает

Не меняет конфигурацию живых сайтов: правка nginx на управляющем узле — root, и
обходить это нельзя. Не затрагивает работу SEO-сессии: измерение отправлено ей
отдельным сообщением, чтобы правка общих компонентов шла одним порядком, а не
двумя.
