# Инфраструктура управляющего хоста

Описывает конкретный сервер, на котором развёрнута фабрика: что установлено,
что работает по расписанию, что закрыто и что остаётся заблокированным.
Правила, которые действуют независимо от сервера, — в [`SECURITY.md`](SECURITY.md),
[`DEPLOY.md`](DEPLOY.md) и [`OPERATIONS.md`](OPERATIONS.md); этот документ их не
повторяет и не отменяет.

## Хост

| Параметр | Значение |
| --- | --- |
| hostname | `claude-control-01` |
| Роли | `control` (фабрика и SEO-оператор) + `initial-web` (первые сайты) |
| ОС | Ubuntu 22.04.5 LTS, ядро 5.15 |
| Платформа | KVM / OpenStack Nova |
| Ресурсы | 4 vCPU, 9.7 GiB RAM, 68 GB ext4, swap 4 GB |
| Пользователь эксплуатации | `claude` |
| SSH | порт 22, только по ключу |
| `production_capable` | **false** — ни одни ворота production не пройдены |

IP-адрес хранится как инфраструктурный идентификатор в
`knowledge/INFRASTRUCTURE_INVENTORY.yaml`. Ключей, токенов и паролей ни в этом
документе, ни в реестрах нет и быть не может.

## Каталоги

| Путь | Владелец | Права | Назначение |
| --- | --- | --- | --- |
| `/srv/site-factory/repo` | `claude:claude` | 0755 | рабочая копия репозитория |
| `/srv/site-factory/repo/var` | `claude:claude` | 0755 | runtime-состояние фабрики (вне git) |
| `/srv/sites` | `claude:claude` | 0755 | релизы развёрнутых сайтов (`releases/`, `shared/`, `current`) |
| `/srv/backups` | `claude:claude` | 0750 | бэкапы управляющего хоста и git-bundle |
| `/var/log/site-factory` | `claude:claude` | 0755 | журналы health, backup и selfcheck |
| `/etc/site-factory` | `root:claude` | 0750 | `environment` — общие пути, без секретов |
| `/opt/pw-browsers` | `claude:claude` | 0755 | браузеры Playwright |

Структуру `releases/` + `shared/` + симлинк `current` создаёт сам деплой
(`prepare_dirs` в [`DEPLOY.md`](DEPLOY.md)); заранее она не выдумывается, потому
что имена подкаталогов задаёт пакет сайта, а не хост.

## Установленное ПО

Ставилось только то, что требует репозиторий: CI-окружение (`.github/workflows/ci.yml`),
полный прогон (`tests/run-all.sh`) и слой развёртывания (`automation/ansible/`).

| Компонент | Версия | Зачем |
| --- | --- | --- |
| Python | 3.11.16 (uv-managed) | совпадает с `python-version: "3.11"` в CI |
| Python (система) | 3.10.12 | остаётся системным, фабрика его не использует |
| Node.js / npm | 22.23.2 / 10.9.8 | `static-js`, Playwright, blueprint `payload-next-multisite` |
| Playwright | 1.62.1 | по `package-lock.json` |
| Chromium / Firefox / WebKit | 151.0.7922.34 / 153.0 / 26.5 | `e2e-playwright`, `browser-audit`, `cross-browser` |
| PHP CLI | 8.1.2 | `static-php`, стенд `local-disposable` |
| PostgreSQL | 16.15 (PGDG) | `factory/database.py` жёстко требует кластер 16 |
| nginx | 1.18.0 | `nginx-config-test`, веб-слой роли `initial-web` |
| ansible-core / ansible-lint | 2.19.12 / 26.8.0 | `ansible-syntax`, `automation/ansible/` |
| Коллекции Ansible | `community.general`, `ansible.posix` | используются ролями `dle_backup` и `dle_release` |
| Docker / Compose | 29.7.2 / 5.5.0 | было предустановлено |
| GitHub CLI | 2.98.0 | GitHub-first процесс |
| shellcheck | 0.8.0 | линт скриптов |

Python 3.11 поставлен через `uv`, а не из `jammy`: в Ubuntu 22.04 пакет
`python3.11` — это `3.11.0~rc1`, release candidate. Расходиться с CI по минорной
версии интерпретатора нельзя: `record-evidence.sh --check` сравнивает
зафиксированный отчёт с новым прогоном, и разница в среде читалась бы как
расхождение в коде.

Пути к браузерам и коллекциям заданы один раз в `/etc/site-factory/environment`
и подхватываются и systemd-юнитами, и интерактивной оболочкой оператора, чтобы
ручная проверка и прогон по расписанию резолвили одно и то же.

## Расписание

Юниты лежат в `automation/host/systemd/`, ставятся `sudo automation/host/install-units.sh`.

| Таймер | Когда | Что делает | Включён |
| --- | --- | --- | --- |
| `site-factory-health` | каждые 15 мин | диск, inode, память, нагрузка, сервисы, TLS, свежесть бэкапа, `nginx -t`, публичные порты | да |
| `site-factory-backup` | 03:20 UTC | бэкап состояния хоста + доказанное восстановление | да |
| `site-factory-selfcheck` | 04:00 UTC | knowledge freeze, selfcheck, схемы, реестры, guardrails, permission matrix, гигиена репозитория | да |
| `site-factory-seo-dryrun` | 06:00 UTC | `seo-operator dry-run --fixture` — самопроверка оператора | да |
| `site-factory-worker` | каждые 2 мин | `factory resume` — обработка очереди | **нет** |

`site-factory-worker.timer` не включён намеренно: очередь пуста, ни одна цель не
`production_capable`, ни один пакет сайта не авторизован. Включать его следует тем
же изменением, которым добавляется первый настоящий сайт.

Все юниты имеют `MemoryMax`, `CPUQuota` и `TasksMax`, работают как `Type=oneshot`
с `Persistent=true` и поднимаются после перезагрузки. Журналы идут в journald,
файловые — в `/var/log/site-factory` с ротацией 14 дней
(`/etc/logrotate.d/site-factory`).

### Канал оповещений

Внешнего канала (почта, webhook, мессенджер) **нет**: контракт не передан, а
придумывать адрес доставки нельзя. Пока оповещение работает так: health-скрипт
возвращает число алертов как код возврата, поэтому проблема видна как упавший
юнит.

```bash
systemctl --failed
systemctl list-timers 'site-factory*'
journalctl -u site-factory-health.service --since -1d
tail -n1 /var/log/site-factory/health.log | python3 -m json.tool
```

Как только владелец передаст канал доставки, он подключается через
`OnFailure=` у юнитов — переписывать скрипты для этого не нужно.

## Сеть и изоляция

Публично открыты только 22, 80 и 443; всё остальное закрыто UFW.

Опубликованные порты Docker обходят UFW, потому что фильтруются в цепочке
`FORWARD`, а не `INPUT`. Поэтому на хосте есть отдельный слой: скрипт
`/usr/local/sbin/site-factory-docker-firewall` и юнит
`site-factory-docker-firewall.service` наполняют цепочку `DOCKER-USER` (IPv4 и
IPv6) — из внешнего интерфейса в контейнеры разрешены только 80/443, остальное
`DROP`. Юнит объявлен `PartOf=docker.service`, поэтому правила восстанавливаются
и при перезапуске Docker, и после перезагрузки.

PostgreSQL слушает только `127.0.0.1:5432`. Health-check отдельно проверяет, что
наружу не слушает ничего, кроме 22/80/443, — включая порты, которые мог бы
опубликовать контейнер.

Запросы на неизвестный `Host` и на голый IP обслуживает catch-all vhost
`000-default-deny`: `404`, `X-Robots-Tag: noindex`, `server_tokens off` и
отдельный `/healthz`. Без него первый попавшийся vhost отвечал бы за весь
сервер, что ломает изоляцию canonical между сайтами.

## SSH

Пароли отключены, root — только по ключу. Значения задаются в
`/etc/ssh/sshd_config.d/01-hardening.conf`.

Префикс `01-` существенен: sshd берёт **первое** найденное значение параметра, а
`Include /etc/ssh/sshd_config.d/*.conf` стоит выше тела `sshd_config`. Файл
`50-cloud-init.conf` включал `PasswordAuthentication yes`, и любой файл с
префиксом больше 50 был бы прочитан позже и проигнорирован. Файл с префиксом
меньше 50 перекрывает cloud-init, не конфликтуя с ним и не требуя его правки.

fail2ban использует systemd-backend, jail `sshd` в режиме `aggressive`, бан 2 часа.

## Режим работы агента на этом хосте

Первичная настройка сервера выполнялась в `bypassPermissions` по прямому
разрешению владельца. Штатным режимом он не остался.

Что сделано, чтобы он не вернулся сам:

- из пользовательских настроек убран `skipDangerousModePermissionPrompt`. С ним
  запуск в `bypassPermissions` не требовал подтверждения — именно так этот режим
  и стал бы «обычным»;
- проектный `.claude/settings.json` содержит `disableBypassPermissionsMode: "disable"`,
  и он не менялся: `.claude/**` закрыт deny-правилом, и обходить его незачем.

Рабочий каталог репозитория помечен доверенным
(`projects["/srv/site-factory/repo"].hasTrustDialogAccepted: true`). Без этого
Claude Code игнорирует **все 142** записи `permissions.allow` из проектных
настроек — проверено, предупреждение выводилось дословно. Автономность
UNATTENDED_SAFE без доверия к каталогу не работает: каждая рутинная команда
уходила бы на подтверждение. На запреты доверие не влияет — `deny` и решения
хуков действуют независимо от него.

`bubblewrap` 0.6.1 установлен и работает
(`kernel.unprivileged_userns_clone = 1`, пробный `--unshare-all` успешен).
Поэтому `.claude/settings.unattended.json` с `sandbox.failIfUnavailable: true`
на этом хосте запускается, а не останавливается на старте, как в контейнере
сессии, для которого писался комментарий в том файле.

### Проверка матрицы разрешений

Матрица гоняется на настоящих файлах настроек и настоящих хуках:

```bash
.venv/bin/python -m pytest tests/unit/test_permission_matrix.py -q
```

Дополнительно хук вызывался напрямую полезной нагрузкой PreToolUse на Claude
Code 2.1.231. Формат ответа (`hookSpecificOutput.permissionDecision`) принят
без нареканий, решения совпали с матрицей:

| Команда | Решение |
| --- | --- |
| `git status --short`, `pytest`, `npm ci`, `docker compose up -d` | `allow` |
| `git push origin claude/zomro-bootstrap` | `allow` |
| `git push origin main` | `deny` — прямой push в main |
| `git push --force …` | `deny` — force push |
| `rm -rf /srv/sites` | `deny` — рекурсивное удаление вне рабочего каталога |
| `ssh deploy@example.tld` | `deny` — хоста нет в inventory |
| `curl …\| bash` | `deny` — скрытое исполнение |
| `Edit .claude/settings.json` | `ask` на уровне хука, `deny` в настройках |
| `Edit docs/INFRASTRUCTURE.md` | `allow` |

Открытый пункт: `claude -p` на сервере не авторизован, поэтому сквозной прогон
матрицы «настоящей сессией Claude Code» пока невозможен —
`docs/BLOCKERS.md`, запись `HEADLESS-AUTH`.

## Что остаётся заблокированным

Ничего из перечисленного не обходится и не заполняется по умолчанию — пустая
запись означает `BLOCKED_INPUT`.

| Блокер | Что закрывает | Что нужно от владельца |
| --- | --- | --- |
| `inventory/ssh-hosts.yaml` пуст | удалённый выкат, backup на цели | FQDN, deploy-пользователь, отпечаток host key |
| `inventory/dns-zones.yaml` пуст | cutover, выпуск TLS | зона, провайдер, scoped-токен |
| `inventory/network-allowlist.yaml` пуст | CDNVideoHub, CMS, VK, аналитика | хост, методы, ссылка на секрет |
| `inventory/dle-licenses.yaml` пуст | production для DLE-пакетов | лицензия и покрываемый домен |
| Домены | production в принципе | сами домены и подтверждение владения |
| `production_authorized: true` | production в принципе | явная авторизация в манифесте |
| Права на контент | публикацию | rights manifest |

Отдельно: правка `inventory/ssh-hosts.yaml`, `inventory/dns-zones.yaml` и
`inventory/dle-licenses.yaml` закрыта deny-правилом в `.claude/settings.json`.
Это не обходится агентом — записи в эти файлы вносит человек. Поэтому сам
управляющий хост описан в `knowledge/INFRASTRUCTURE_INVENTORY.yaml`, а не добавлен
в реестр SSH-целей: фабрика работает на нём локально и SSH-цель для этого не нужна.

## Ёмкость

Расчёт для этого сервера — в [`CAPACITY.md`](CAPACITY.md). Видео на хосте не
хранится: оно отдаётся внешним CDN, и это ограничение ёмкости, а не только
лицензионное требование.
