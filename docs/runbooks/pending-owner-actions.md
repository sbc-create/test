# Runbook: отложенные действия владельца

**Назначение.** Свести всё, что подготовлено прогоном
`SITE-FACTORY-HARDENING-AND-PARALLEL-TEMPLATES-01`, к упорядоченной
последовательности команд, каждая из которых проверена до записи сюда.
**Последняя проверка.** 2026-09-03. Credential-preflight выкатки прогнан
заранее на работающем образе: оба credential читаются пользователем `node`,
то есть первый шаг выкатки не упадёт.

Порядок не произвольный: он идёт от того, что защищает данные, к тому, что
добавляет содержимое. Действие 1 стоит первым, потому что до него откат
разрушителен, и любая ошибка в действиях 2–4 обойдётся дороже.

---

## 1. Расписание копий баз витрин — СРОЧНО

**Зачем.** Копии баз снимаются только при выкатке; последняя от 31 августа.
`rollback.sh` восстанавливает **парную копию**, то есть откат сегодня уничтожил
бы трое суток данных. Это единственное место, где промедление стоит дороже
всего: чем позже, тем больше теряется при любом откате.

```
sudo bash /home/claude/work-h01/automation/host/install-units.sh \
     yummy-site-backup.service yummy-site-backup.timer
sudo systemctl enable --now yummy-site-backup.timer
```

**Проверить:**

```
systemctl list-timers yummy-site-backup.timer --no-pager
sudo systemctl start yummy-site-backup.service   # первая копия сразу, не ждать ночи
ls -1t /srv/backups/yummyani-staging/ | head -3  # новый набор + latest на него
```

**Что произойдёт.** Юнит снимает копию трёх баз с репетицией восстановления, а
вторым шагом удерживает не больше 14 наборов, никогда не трогая тот, на который
указывает `latest`.

**Откат.** `sudo systemctl disable --now yummy-site-backup.timer`. Снятые копии
удалять не нужно — они и есть польза.

---

## 2. Выкатка исправления серий

**Зачем.** У 105 тайтлов доступно 11 964 серии из 24 068. Замер по всем 105
через API поставщика: исправление возвращает **12 104 серии**.

```
W=/home/claude/work-h01-yummy2
REPO=$W bash $W/deploy/staging/deploy.sh "$(git -C $W rev-parse HEAD)"
```

Ревизия берётся из самого дерева, а не вписана числом. Это не украшение:
`deploy.sh` сверяет переданный SHA с HEAD дерева и **отказывается работать** при
расхождении. Я уже наступил на это, записав сюда `90a65cc`, тогда как ветка
успела уйти вперёд на коммит с инструментированием — команда упала бы на первой
же проверке. Подставленная ревизия расхождения не допускает.

Убедиться, что дерево там, где ожидается:

```
git -C /home/claude/work-h01-yummy2 log --oneline -3
git -C /home/claude/work-h01-yummy2 status --porcelain   # обязано быть пусто
```

**Что делает скрипт сам.** Preflight credential → бэкап трёх БД с репетицией
восстановления → сборка образа с меткой ревизии и сверкой метки с SHA →
повторный preflight → пересоздание **только** трёх web-контейнеров → ожидание
health 180 с → `verify.sh`. При неудаче любого шага откатывается сам на
предыдущий образ. Postgres, Redis, mailpit и proxy не трогаются.

**После выкатки — обязательно:**

```
# кэш индекса переживает подмену образа; без гашения витрины отдают прежний
for db in 0 1 2; do
  docker exec yummyani-staging-redis-1 redis-cli -n $db DEL \
    catalog:anime-ids:v1 catalog:year-index:published:v7 catalog:year-index:version:v7
done
docker exec yummyani-staging-redis-1 redis-cli -n 0 DEL catalog:year-index:stale:v6
sudo systemctl start yummy-catalog-index.service
```

**Проверить снаружи:**

```
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://yummyani.site/anime/boevoy-master/season/1/episode/150   # ожидается 200, было 404
curl -sS https://yummyani.site/anime/boevoy-master | grep -oE 'В каталоге [0-9]+ сери'
                                                                  # ожидается 688, было 100
```

Полную сверку можно повторить скриптом из evidence: `exact-recovery.mjs`.

**Откат.** `bash deploy/staging/rollback.sh site latest` (и так для org, biz).
После действия 1 парная копия будет свежей.

---

## 3. Запуск подтверждённого бэкапа хоста

**Зачем.** Подтверждённой копии за сутки нет с 2026-09-03 03:28. Причины отказа
исправлены (`c713fe8`, `b8d50cb`, `bd17123`), проверка места пройдена: staging
1.76 GB при 9.2 GB свободных.

```
sudo systemd-run --unit=h01-backup-run --collect \
  bash -c "/home/claude/work-h01/automation/host/site-factory-backup.sh"
```

**Успех — это не нулевой код возврата, а файл:**

```
ls -1t /srv/backups/host-*.verified.json | head -1   # должен быть сегодняшний
sudo systemctl start site-factory-health.service
tail -1 /var/log/site-factory/health.log | python3 -m json.tool | head -5   # alerts: 0
```

---

## 4. Контентные юниты — из образа вместо рабочего дерева

**Зачем.** Три контентных юнита исполняются из `/srv/sites/yummyani-staging/repo`,
то есть `git checkout` в этом каталоге молча меняет поведение боевого контента.
Измерено: они шли с ветки, отличной от той, из которой собран образ.

```
sudo bash /home/claude/work-h01/automation/host/install-units.sh \
     yummy-episode-watcher.service yummy-watchdog.service yummy-enrich.service
sudo systemctl daemon-reload
```

**Проверить:**

```
bash /home/claude/work-h01/automation/host/check-unit-provenance.sh \
  $(systemctl cat yummy-episode-watcher | grep -m1 ^ExecStart= | sed 's/ExecStart=//')
# ожидается «ИЗ АРТЕФАКТА», было «ИЗ ДЕРЕВА»
```

**Откат.** Прежние файлы юнитов не версионированы нигде, поэтому перед заменой
сохранить их: `sudo cp /etc/systemd/system/yummy-*.service /root/units-backup/`.

---

## 5. Решения, которые я принять не могу

* **Второй хост.** Все шесть доменов на одном IP, изоляция 0/10. План
  размещения по ячейкам — `adr/0007-cells-and-failure-domains.md`.
* **Показ новых озвучек.** 49 событий `VOICEOVER_ADDED` за наблюдаемое окно
  (28 % всех) обнаруживаются и не видны нигде: сборщика полки нет. Где
  показывать — вопрос раскладки главной.
* **Полка «Новые серии и обновления».** Измерено: 5 из 5 её тайтлов есть в
  «Новых сериях», уникальных ноль. Убрать, переименовать или дать другой
  источник — продуктовое решение.
* **ISR вместо `force-dynamic`.** Чинит CLS (0.2989 desktop / 0.4398 mobile при
  бюджете 0.1) и включает HTTP-кэш. **Но только после** устранения отставания
  списка серий: сейчас ISR сложился бы с ним и ухудшил свежесть.

---

## Чего в этом списке нет намеренно

Диагностика без действия сюда не попала. Осиротевший архив бэкапа на 1.13 GB
удалится сам около 03:24 — проверено на настоящей раскладке. Чужие зомби и
трёхсуточные циклы ожидания оставлены их владельцам. Латентный однопроходный
`listSeasons` не тронут: тайтлов длиннее ста сезонов в парке нет.
