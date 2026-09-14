# Откат исправления данных Lords

**`DO_NOT_RUN_WITHOUT_SEPARATE_OWNER_AUTHORIZATION`.** Не выполнялось.

## Принцип

Откат — возврат сохранённого образа файла, а не обратное вычисление.
Обратный расчёт требует знать, что было до, а это и есть образ; вычислять его
заново — значит доверять тому же коду, из-за которого откатываются.

## Что нужно

Идентификатор запуска (`run_id`) из отчёта и образ `до`, который инструмент
создаёт сам перед записью:

```
<backup-dir>/lords-01-details.json.before.<run_id>
```

## Порядок

```
# DO_NOT_RUN_WITHOUT_SEPARATE_OWNER_AUTHORIZATION
RUN_ID=<из отчёта>
ls -la <backup-dir>/lords-01-details.json.before.$RUN_ID
cp -a <backup-dir>/lords-01-details.json.before.$RUN_ID <путь>/lords-01-details.json.restore
mv -T <путь>/lords-01-details.json.restore <путь>/lords-01-details.json
```

Подмена через `mv -T`, а не копированием поверх: копирование оставляет окно,
в котором файл прочитан наполовину.

## Проверка отката

```
# DO_NOT_RUN_WITHOUT_SEPARATE_OWNER_AUTHORIZATION
curl -s -o /dev/null -w '%{http_code}\n' https://lordfilm47.space/
curl -s https://lordfilm47.space/title/chas-rasplaty-2/ | grep -o 'rate--kp[^<]*'
```

Витрина обязана отвечать 200, контрольная карточка — показывать прежнее
значение.

## Чего откат не делает

Не трогает каталог, кэш подробностей, шаблон, плеер и видеопоток — их backfill
и не менял. Перезапуск витрины не нужен.

## Проверено

Цикл «запись → изменение входа → повторная запись → возврат образа → побайтное
совпадение с первой версией» проверен тестом
`test_откат_возвращает_прежний_файл` на временных копиях.
