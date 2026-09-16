# Откат

## Что вообще было изменено

**Ничего в production.** Ни одной записи в боевую БД, Redis, CMS или файлы
сайтов. Ни одного применённого ChangeSet, ни одного deploy, ни одного
перезапуска контейнера. Плеер не тронут.

Изменения живут в отдельной ветке `claude/core-content-identity-resolution-19`
и в отдельном рабочем каталоге `/home/claude/wt-identity-19`. Боевой checkout
`/srv/site-factory/repo` остался на `claude/day05-lords-merged`.

## Порядок отката

### 1. Код

```
git branch -D claude/core-content-identity-resolution-19
git worktree remove /home/claude/wt-identity-19
```

Ветка ни во что не влита. Удаление ветки — полный откат: ни один потребитель
на неё не переключён.

### 2. Изолированная база

```
rm -f /tmp/identity-isolated.db
```

Либо обратимой миграцией, если базу нужно сохранить пустой:

```
python3 -c "
import importlib.util, sqlite3
s=importlib.util.spec_from_file_location('m','migrations/0001_content_identity.py')
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
m.downgrade(sqlite3.connect('/tmp/identity-isolated.db'))"
```

Обратимость проверена тестом `TestМиграция::test_обратима`: после `downgrade`
таблиц `content_identity` и `rating_discovery` не остаётся.

### 3. Полная выгрузка

```
rm -rf /home/claude/identity-19-full
```

Лежит вне репозитория намеренно: 280 МБ в git не читаются и не сравниваются.

## Чего откатывать не нужно

`config/identity-resolution.yaml` помечен `status: proposal`. Пороги не
применены ни к одному потребителю: контракт передан handoff, а решение о
принятии — за владельцем получающего контура.

## Если контракт всё же будет принят

Откат после принятия — возврат потребителя к `seo-content-contract/1.0.0`,
где `contentKind` выводится потребителем самостоятельно. Данные при этом не
меняются: `content_identity` — отдельная таблица, и её удаление не трогает
каталог. Это и было причиной делать её отдельной, а не колонками в
существующей.
