# Раскатка исправления данных Lords

**Все команды ниже помечены `DO_NOT_RUN_WITHOUT_SEPARATE_OWNER_AUTHORIZATION`.**
Ни одна из них в рамках задачи не выполнялась. Данные на живой витрине не
менялись, дефект владельца остаётся открытым.

## Что именно меняется

Один файл на витрину: боковой файл подробностей `{site}-details.json`, который
читает рендерер. Шаблон, HTML, CSS, плеер, видеопоток, манифест релиза, DNS и
счётчики не затрагиваются.

## 0. Предпроверка

```
# DO_NOT_RUN_WITHOUT_SEPARATE_OWNER_AUTHORIZATION
systemctl is-active lords-01 nova-lords-02 nova-lords-03
curl -s -o /dev/null -w '%{http_code}\n' https://lordfilm47.space/
python3 automation/host/lords-details-backfill.py --help
```

Условия входа: витрина отвечает 200; снимок каталога свежее суток; свободного
места не менее 500 МБ; чужие прогоны не идут.

## 1. Образ «до»

```
# DO_NOT_RUN_WITHOUT_SEPARATE_OWNER_AUTHORIZATION
cp -a <путь>/lords-01-details.json /srv/site-factory/backups/lords-01-details.$(date -u +%Y%m%dT%H%M%SZ).json
```

Без образа дальше не идти: откат — это возврат файла, а не обратный расчёт.

## 2. Сухой прогон на production-снимке

```
# DO_NOT_RUN_WITHOUT_SEPARATE_OWNER_AUTHORIZATION
python3 automation/host/lords-details-backfill.py \
  --snapshot  /srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json \
  --render-state /srv/site-factory/repo/var/lords/render-state/lords-01.titles.json \
  --detail-cache /srv/site-factory/repo/var/lords/detail-cache \
  --target <путь>/lords-01-details.json \
  --run-id prod-dry-$(date -u +%Y%m%dT%H%M%SZ)
```

Записи не будет: `--apply` не указан. Проверить в отчёте: `production_mutations: 0`,
`written_entries` близко к числу отрисованных slug, `stats.изменено` объяснимо.

## 3. Канарейка

Шесть карточек из `canary-plan.json`, среди них — контрольная
`chas-rasplaty-2`, которая **не должна измениться ни одним полем**.

```
# DO_NOT_RUN_WITHOUT_SEPARATE_OWNER_AUTHORIZATION
python3 automation/host/lords-details-backfill.py ... --limit 200 --apply \
  --run-id canary-$(date -u +%Y%m%dT%H%M%SZ)
```

## 4. Проверка канарейки

```
# DO_NOT_RUN_WITHOUT_SEPARATE_OWNER_AUTHORIZATION
curl -s https://lordfilm47.space/title/dni-sakamoto-chast-2/ | grep -o 'rate--kp[^<]*'
curl -s https://lordfilm47.space/title/chas-rasplaty-2/    | grep -o 'rate--kp[^<]*'
```

Ожидается: у первой появилось число 7.363; у контрольной осталось 7.042.

## 5. Пороги остановки

Прекратить и откатиться, если выполнено хотя бы одно:

* контрольная карточка изменилась;
* непустое значение стало пустым;
* slug сменил каноническую сущность;
* число записей уменьшилось более чем на 1%;
* витрина отвечает не 200;
* инструмент вернул `CONTRACT_VIOLATION`.

## 6. Полная раскатка

```
# DO_NOT_RUN_WITHOUT_SEPARATE_OWNER_AUTHORIZATION
python3 automation/host/lords-details-backfill.py ... --apply \
  --run-id rollout-$(date -u +%Y%m%dT%H%M%SZ)
```

Перезапуск витрины не требуется: рендерер читает файл при обращении.

## 7. Проверка после раскатки

Повторить замер `live-baseline.json` и сравнить: доля карточек с оценками
обязана вырасти с 1/48 примерно до 10–11/48 по КП и до 15/48 по IMDb —
ровно на те записи, у которых значение есть upstream.

## 8. Сверка

`upstream-vs-served-coverage.json` пересчитать; потери upstream → served по
оценкам, постерам и привязке к источнику обязаны стать нулевыми.
