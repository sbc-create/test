# Транзакция владельца: закрепление границы root

**Не выполнять до отдельной проверки.** Команда подготовлена и проверена в
сухом прогоне; её исполнение — решение владельца.

## Одна команда

```bash
sudo /bin/bash -c 'set -eu
C=12381a7fd388e0a2fb200020db05d2178a352574
S=/root/site-factory-hardening/src
install -d -m 0700 -o root -g root /root/site-factory-hardening
install -d -m 0700 -o root -g root "$S"
git -C /srv/site-factory/repo archive "$C" automation/hardening | tar -x -C "$S"
echo "d7632ad6a512b06e1343e699f60adc1140bc49f9d3cc4e1ef331d2d8d40e69b8  $S/automation/hardening/pin-root-units.sh" | sha256sum -c -
bash "$S/automation/hardening/pin-root-units.sh" \
  --bundle="$S/automation/hardening/release/site-factory-pinned-runtime.tar.gz" \
  --release="$S/automation/hardening/release/release.json" \
  --manifest="$S/automation/hardening/manifest.json"'
```

Сухой прогон — та же команда с `--dry-run` в конце. Он **не требует root** и
ничего не меняет:

```bash
bash /srv/site-factory/repo/automation/hardening/pin-root-units.sh --dry-run
```

## Идентификаторы

| Поле | Значение |
| --- | --- |
| source commit | `12381a7fd388e0a2fb200020db05d2178a352574` |
| ветка | `claude/templates-secret-hub-cloud-access-006` |
| путь установщика в коммите | `automation/hardening/pin-root-units.sh` |
| SHA-256 установщика | `d7632ad6a512b06e1343e699f60adc1140bc49f9d3cc4e1ef331d2d8d40e69b8` |
| бандл | `automation/hardening/release/site-factory-pinned-runtime.tar.gz` |
| SHA-256 бандла | `a7367e26d4e290df27f40d1b6f6898e7956cd34cbfc55f5db7190a9dd278dbbf` |
| release_id | `6fcd33701aef-a7367e26d4e2` |
| файлов в бандле | 168, у каждого записан свой sha256 и коммит-источник |
| закреплённый рантайм | `/opt/site-factory/runtime/6fcd33701aef-a7367e26d4e2` |
| бэкап | `/var/backups/site-factory-hardening/<UTC-метка>` |

### Почему команда устроена именно так

* **`git archive <полный sha>`** — не зависит от того, на какой ветке сейчас
  стоит `/srv/site-factory/repo`. Ветку не переключаем и чужую работу не
  трогаем. Привязка идёт к полному хешу коммита, а не к имени ветки: ссылку
  можно переписать, содержимое коммита — нет.
* **извлечение в `/root/...` с правами 0700** — дальше root исполняет файл из
  каталога, недоступного агенту на запись. Запускать от root файл прямо из
  рабочей копии значило бы повторить ровно тот дефект, который транзакция
  закрывает.
* **`sha256sum -c` до запуска** — закрывает окно между извлечением и запуском.
* **бандл проверяется дважды** — установщиком до копирования в staging и ещё
  раз после (шаги 2 и 5).

## Что изменится

### Юниты (10)

`site-factory-secret-hub.service`, `site-factory-secret-hub-import@.service`,
`nova-daily-refresh.service`, `lords-content-refresh.service`,
`lords-site-render@.service`, `lords-canary-switch@.service`,
`site-factory-health.service`, `site-factory-backup.service`,
`site-factory-restore-proof.service`, `nova-catalog-refresh.service`.

У каждого появляется **один** файл:
`/etc/systemd/system/<unit>.d/20-pinned-runtime.conf`. Базовые unit-файлы не
редактируются.

### Файлы и каталоги

| Путь | Что происходит |
| --- | --- |
| `/opt/site-factory/runtime/<release_id>/bundle` | создаётся: код из отсмотренных коммитов, root:root |
| `/opt/site-factory/runtime/<release_id>/venv` | создаётся: интерпретатор root:root, зависимости проверяются импортом |
| `/opt/site-factory/runtime/relocated/*` | создаётся: три существующих дерева переносятся **байт в байт** |
| `/opt/site-factory/runtime/current` | симлинк на релиз |
| `/etc/systemd/system/<unit>.d/20-pinned-runtime.conf` | создаётся, 10 штук |
| `/var/backups/site-factory-hardening/<метка>` | бэкап юнитов, drop-in'ов и конфигурации nginx |
| `/etc/nginx/sites-available/yummyani.site.conf` | **только на шаге 14**, и только после зелёного аудита |

Версии переносимых деревьев не меняются: `lords-tooling-0b0722f3`,
`lords-tooling-41031da0` и `content-pipeline` копируются как есть. Подменять
содержимое боевого конвейера под видом починки прав нельзя.

### Чего транзакция НЕ трогает

Шаблоны, каталоги, контент, SEO, плеер, DNS, TLS и **значения credentials**.
Ни один `LoadCredential` не добавляется и не убирается. Значения не читаются,
не перевыпускаются и не перемещаются. Меняются только пути, по которым root
берёт **код**; пути к данным (`FACTORY_REPO`, `LORDS_ARTIFACT_ROOT`) остаются
прежними намеренно.

## Порядок и откат

14 шагов: хост → хеши → staging → повторная проверка хеша → бэкап → остановка
только затронутых таймеров → раскладка рантайма → venv → drop-in'ы →
`systemd-analyze verify` и проверка эффективного `ExecStart` → аудит границы →
smoke витрин → возврат таймеров → публикация панели.

**Откат автоматический.** `trap ... ERR` срабатывает на любой ошибке любого
шага: снимаются drop-in'ы, восстанавливаются юниты из бэкапа, выполняется
`daemon-reload`, запускаются обратно остановленные таймеры.

Отдельно: если аудит границы (шаг 11) находит нарушение **в целевых юнитах** —
транзакция отказывает и откатывается. Если нарушения остались только вне
области (юниты Yami), она продолжается с предупреждением.

Ручной откат после успеха: `bash /root/site-factory-hardening/<release_id>/rollback.sh`.

Публикация панели (шаг 14) имеет собственный откат: штатный установщик делает
бэкап vhost, проверяет `nginx -t`, ждёт применения конфигурации, проводит живую
проверку по публичному имени и **снимает панель обратно**, если проверка не
прошла.

## Ожидаемый результат

```
[harden] аудит: нарушений нет во ВСЕЙ цепочке исполнения root-юнитов
[harden] smoke: витрины Lords/Zona/Animedia отвечают 200
[harden] аудит зелёный — можно публиковать панель Secret Hub
[harden] ТРАНЗАКЦИЯ ЗАВЕРШЕНА
```

После этого:

* `ROOT_EXECUTABLES_WRITABLE_BY_CLAUDE` = 0 в целевых юнитах;
* два теста состояния хоста перестают быть SKIPPED и обязаны быть зелёными;
* панель Secret Hub доступна по HTTPS, и появляется проверенная ссылка.

## Известное расхождение — прочитать до запуска

`automation/host/nova-daily-refresh.sh` на хосте **не совпадает** с
закрепляемым коммитом `2bb47de`: файл менялся дважды за время подготовки, его
правит другая сессия.

Закрепляется версия из коммита. После установки `nova-daily-refresh.service`
будет исполнять **отсмотренную** версию, а не ту, что лежит в рабочей копии
сегодня.

Если правка нужна — владеющая сессия обязана её закоммитить, после чего бандл
пересобирается и хеши в этом документе меняются. Если правка не нужна —
запускать можно как есть.

То же с `lords-canary-apply.sh` в `/home/claude/wt-release-03`.

## После транзакции

1. Прислать вывод команды — эта сессия проверит 11 пунктов раздела 3 задания
   (эффективная конфигурация юнитов, отсутствие agent-writable кода во всей
   цепочке, health и fingerprint Lords, неизменность credentials, HTTPS,
   401 без сессии, CSRF, `no-store`, флаги cookie, отсутствие секретов).
2. Ротация токена Lords — `docs/runbooks/lords-credential-rotation.md`.
   Publisher ID не ротируется: контракт классифицирует его как
   `configured_public_value` (D140).
3. Только после этого — ввод credentials Zona и Animedia/AMD.
