# Проверка профиля UNATTENDED_SAFE

Записано вручную по фактическим запускам. Команда, exit code и артефакт
приводятся как есть; пропущенная проверка отмечается как пропущенная.

## Матрица разрешений

| Команда | Exit code | Результат |
| --- | --- | --- |
| `.venv/bin/python -m pytest tests/unit/test_permission_matrix.py -q` | 0 | 154 passed |
| `.venv/bin/python -m pytest tests/ -q` | 0 | 936 passed |
| `.venv/bin/ruff check seo_operator` | 0 | All checks passed |

Матрица считает итог всех слоёв: правила `.claude/settings.json` плюс решения
обоих PreToolUse-хуков, сложенные по порядку `deny` → хук → `ask` → `allow`.

Доказано отсутствие `ask` для: сборки (`npm run build`), тестов (`pytest`),
линтеров (`ruff`), Playwright (`npx playwright test`), установки зависимостей
(`npm ci`, `pip3 install -r`, `composer install`), `git add`, `git commit`,
`git push origin claude/example-branch`, проверки remote SHA
(`git ls-remote origin refs/heads/main`, `git rev-parse origin/main`), а также —
на утверждённом инвентаре — `ssh`, `scp`, `rsync`, `ansible-playbook`, бэкапа
через `ssh … tar`, health-check через `curl`, DNS через `nsupdate` и выката
тестового сайта.

Доказана блокировка: force push во всех формах, push в `main`, удаление
remote-ветки (`--delete` и рефспек `:ref`), неизвестного SSH-хоста, неизвестной
DNS-зоны, вывода секретов, удаления production-базы, удаления бэкапов,
скрытого исполнения (`curl | bash`, `base64 | sh`) и обхода через составные
команды и обёртки (`&&`, `timeout`, `env`, `xargs`, `bash -c`).

## Реальный прогон на disposable/local target

Цель `local-disposable` из `inventory/targets.yaml`: PHP built-in server на
`127.0.0.1`, `production_capable: false`.

| Команда | Exit code | Результат |
| --- | --- | --- |
| `python3 -m factory validate --site pilot-local` | 0 | `READY`, предупреждение о неподтверждённой лицензии DLE |
| `python3 -m factory build --site pilot-local` | 0 | `build_id: b6739e21eb6cbd15`, 48 маршрутов, 2 материала сняты с публикации |
| `python3 -m factory deploy --site pilot-local --environment staging` | 0 | job `pilot-local-create-20260823T091215Z-d31db8`, `DONE`, `http://127.0.0.1:8082` |
| `python3 -m factory rollback --site pilot-local --environment staging` | 0 | job `pilot-local-rollback-20260823T091354Z-77aa49`, `current → 3149938db0d25a4e` |

Ворота выката, прошедшие в этом прогоне: `backup-restore`, `seo-lint`,
`seo-crawl`, `seo-render`, `security-smoke`, `acceptance-routes`,
`major-findings-budget`, `performance-budget` — все `exit=0`, артефакты под
`artifacts/qa/pilot-local/pilot-local-create-20260823T091215Z-d31db8/`.

Откат подтверждён health-check после переключения: `post_rollback_health ok
HTTP 200, 2048 байт`.

## Что не проверялось

* **Выкат на production.** Не запускался: ни одна цель в `inventory/targets.yaml`
  не помечена `production_capable: true`, домены и доступы не переданы. Логика
  ворот проверена на временном пакете в `tests/unit/test_permission_matrix.py`
  (снятие любого из девяти условий возвращает выкат человеку и называет условие),
  но настоящего выката на боевой сервер не было.
* **SSH, SCP, rsync, Ansible и DNS на настоящей цели.** Реестры пусты, целей нет.
  Проверено на временном инвентаре в зоне `.invalid` — она зарезервирована IANA
  как заведомо неразрешимая, поэтому сетевого обращения не происходило.
* **Стадия Lint в `./scripts/verify.sh`.** Падает: `ruff` линтует весь
  репозиторий, включая код фабрики, который в ветке `claude/seo-operator` не
  участвовал. Изменённые здесь файлы линт проходят.
