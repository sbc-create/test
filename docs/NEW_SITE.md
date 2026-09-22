# Ввод нового сайта

## 1. Подготовь каталог

```
sites/<site_id>/
├── package.yaml              # манифест по schemas/site-package.schema.json
├── brand/                    # логотип, favicon (переданные файлы)
├── legal/                    # утверждённые тексты правовых документов
├── media/                    # изображения из пакета (копируются в /assets/media/)
└── content/
    ├── catalog.json          # выгрузка каталога
    ├── rights-manifest.yaml  # права: правообладатель, срок, территория, способы
    └── vk-player-contract.yaml
```

## 2. Заполни манифест

Обязательный минимум, который **никогда** не подставляется по умолчанию: `domain`,
`canonical_url`, `environment`, `target_ref`, `dle_license_ref` (для production),
`brand`, `theme_ref`, `metadata`, `seo`, `navigation`, `legal`, `content_source`,
`runtime`, `backup_policy`, `monitoring_policy`, `retention_policy`, `acceptance`,
`rollback_policy`, `requested_by`.

Секреты задаются только через `secret_ref`: `env:NAME`, `file:/path`, `vault:path`.

## 3. Проверь и поставь в очередь

```bash
python3 -m factory validate --site <site_id>        # точный список ошибок по полям
python3 -m factory plan     --site <site_id>        # план, mutations применено: 0
python3 -m factory queue enqueue --site <site_id> --action create --environment staging
python3 -m factory resume                            # обработать очередь
```

## 4. Разбор блокеров

| Статус | Что значит | Что сделать |
|--------|------------|-------------|
| `BLOCKED_INPUT` | не хватает переданных данных | получить данные у заказчика; `factory input-request` соберёт полный список |
| `BLOCKED_RIGHTS` | нет подтверждения прав/происхождения контента | rights manifest, версия и SHA-256 каталога, contract плеера |
| `BLOCKED_LICENSE` | нет лицензии DLE на домен второго уровня | запись в `inventory/dle-licenses.yaml` |
| `BLOCKED_ACCESS` | цель, хост или зона отсутствуют в inventory | добавить запись; список хостов не расширяется самой фабрикой |
| `BLOCKED_SECRET` | `secret_ref` не резолвится или секрет задан значением | положить значение в хранилище, оставить в пакете только ссылку |
| `BLOCKED_SEO` | конфликт с матрицей индексируемости | привести пакет или матрицу в соответствие через `/research-freeze` |
| `BLOCKED_AUTHORIZATION` | production не авторизован | `production_authorized: true`, `authorized_by`, `authorized_at` и флаг `--allow-production` |

## 5. Приёмка

```bash
python3 -m factory verify   --site <site_id>
python3 -m factory seo-report --site <site_id>
npx playwright test
```

Сайт считается принятым, когда все критические проверки зелёные, бэкап снят и
восстановление подтверждено, а отчёт задания прошёл собственную схему.

## Publisher ID нового сайта семейства

Сайт семейства не получает Publisher ID вручную. Значение семейства описано один
раз в `config/publisher-ids.yaml`, и оттуда его читают все четверо: генератор
профиля, гейт, операция подключения плеера и релизная проверка. Своей копии
значений нет ни у кого — две копии одного числа расходятся молча, а
обнаруживается это чужим каталогом на живой витрине.

```bash
python3 -m factory publisher-ids     # релизная проверка: профили против политики
```

Что это означает на практике:

* семейство задаётся полем `family` в профиле тенанта. Генератор по нему сам
  проставляет блок `player` со ссылкой на пару Secret Hub;
* домен, закреплённый в разделе `onboarding`, задаёт семейство сам — называть
  его второй раз не нужно, а назвать другое нельзя;
* значение другого семейства и любое из `retired` отвергаются гейтом **до**
  сборки, а не при выкладке;
* один домен принадлежит одному тенанту: второй профиль с тем же доменом не
  проходит `gate.run`;
* сайт без `family` заводится как прежде. Политика не имеет мнения о витринах,
  которых она не ведёт, и в релизном отчёте о них молчит.

Пустое поле здесь — `BLOCKED_INPUT`, а не разрешение подставить умолчание:
Publisher ID без названного семейства проверить не с чем, а семейство без записи
в файле не имеет значения, которое можно было бы выдать.
