# Два окна: development и SEO

## Порядок

Выполнять только после того, как текущая работа закоммичена и выбран принятый base commit.

```bash
cd /path/to/repo
git status --short                  # должно быть пусто
git fetch --all --prune
git log -1 --format=%H              # это и есть ACCEPTED_BASE_COMMIT

git worktree add ../repo-dev -b claude/development <ACCEPTED_BASE_COMMIT>
git worktree add ../repo-seo -b claude/seo-operator <ACCEPTED_BASE_COMMIT>
```

Либо поддерживаемый режим Claude Code из корня принятого репозитория:

```bash
claude --worktree development
claude --worktree seo-operator
```

Пути, ветки и существующие worktree проверить read-only **до** выполнения.
Не создавать worktree от незакоммиченного состояния. Если push заблокирован —
сначала сделать резервный bundle:

```bash
git bundle create ../backup-$(date +%Y%m%d).bundle --all
```

## Разделение

| | Development | SEO Operator |
|---|---|---|
| Ветка | `claude/development` | `claude/seo-operator` |
| Меняет | CMS, frontend, factory, схемы, инфраструктуру | аналитику, эксперименты, SEO-модули, playbooks, разрешённые CMS-изменения |
| Права | write на инфраструктуру | read analytics + узкий CMS/deploy scope |
| Приоритет | schema migrations | не применяет несовместимую миграцию во время deploy |

Общий deployment lock не даёт двум контурам выпускать production одновременно.
Контракты CMS/API версионируются; SEO-контур проверяет совместимость до мутации
(`CMSAdapter._check_contract`) и отказывается работать при расхождении major-версии.

## Общее и раздельное

**В git общее:** `CLAUDE.md`, `.claude/`, схемы, инвентарь без секретов, sites/tenant
manifests, knowledge, PAGE_MATRIX, deploy/rollback automation, тесты, ADR.

**Вне git общее:** SSH-ключи, DNS credentials, GSC/Вебмастер/Метрика OAuth, CMS
credentials, БД, мониторинг, runtime state, бэкапы.

Секреты настраиваются один раз в secret store и выдаются по least privilege.
`.env` между worktree не копируется и в git не попадает. DNS и root SSH ежедневному
SEO-процессу не нужны — соответствующие обёртки отказывают по построению.

## Короткие ветки

Бесконечная SEO-ветка с сотнями непроверенных изменений не ведётся:

```
claude/seo-operator
├── seo/experiment-YYYYMMDD-NNN
└── seo/module-<name>-YYYYMMDD
```

CMS-контентные операции git-коммита не требуют, но всегда имеют audit record,
before/after snapshot, experiment ID и rollback payload.
