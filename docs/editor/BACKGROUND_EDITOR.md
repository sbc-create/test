# Фоновый редактор сети и переключение на одного основного редактора

Введено 2026-10-08 по решению владельца: основной исполнитель редакционной
работы — Claude.

## Как устроено

| часть | где | что делает |
| --- | --- | --- |
| расписание | `automation/host/editor/editor-run.timer` | 03/09/15/21:15 UTC, `Persistent=true` |
| запуск | `automation/host/editor/editor-run.sh` | блокировка `flock`, Claude Code без интерфейса (`claude -p`), предел 25 мин, запись `var/editor-runs/<run_id>.*` |
| ход работы | `docs/editor/EDITOR_RUN_PROMPT.md` | ≤ 2 материала Animedia: задание из очереди или из `var/seo-regular/editor-candidates.json` → источник → текст → `prepare` → `publish` → результат → проверка страницы → строка журнала изменений |
| правила текста | `docs/editor/EDITORIAL_RULES.md` | без внутренних слов, без чисел серий у выходящих, сюжет только из синопсиса |
| проверка | `seo_operator/editor_run.py` | пять следов: выдача задания, чтение источника (журнал моста), результат TEXT_WRITTEN, запись `publish` автора в history.jsonl, текст на публичной странице |
| статус | `python3 -m seo_operator.cli editor-run-status` | запуски по расписанию и ручные — раздельно; `confirmed` только при полном запуске по расписанию |

Имя владельца каждого запуска — `editor/claude-auto/run-<run_id>`: по нему
запуск находится в журнале очереди и в истории публикаций без доступа к
планировщику.

Проверено без модели (подставной исполнитель, `trigger=wrapper-test`): обёртка
пишет запись, проверка по следам выставляет `NO_PUBLICATION`, код выхода 0.
Настоящий запуск модели из сессии агента профиль не разрешает — он возможен
только из службы.

## Установка (одна команда владельца)

```bash
sudo bash /home/claude/wt-portable-site-cell-01/automation/host/install-seo-regular.sh
```

Ставит и SEO-расписание, и фоновый редактор. Подтверждение:

```bash
python3 -m seo_operator.cli editor-run-status      # confirmed: true после первого полного запуска
cat /home/claude/wt-portable-site-cell-01/var/editor-runs/runs.jsonl
```

## Переключение на одного редактора — ТОЛЬКО после `confirmed: true`

### Что отключается

1. **Автоматизации Qwen на srv-qwen** — доступа к их планировщику нет (хоста нет
   в `inventory/`). Известный идентификатор один:
   `533bbc0b-0421-4aa0-a917-ee731d050abd` (редактор, сетка 30 минут). По журналу
   очереди за 48 часов до 2026-10-08 13:30Z задания брали 45 разных имён
   владельцев; повторяющиеся ряды, похожие на расписание:
   * редакторы: `editor_automation` (24 выдачи), `editor-automation`,
     `editor-automation-01`, `editor_automation_30min`, `editor-automation-30min`,
     `editor_auto_30min`, `editor_bot`, `editor_bot_01`, `editor_bot_001`,
     `editor_bot_30min`, `editor-bot`, `editor_script`, `editor_session_1`;
   * SEO-анализ, берущий редакционные задания: `seo-analysis-<дата>`,
     `seo-analyzer-<дата>`, `seo-analyzer-2025`, `seo_audit_<дата>`,
     `seo-audit-<дата>`, `seo-analyst-*`, `qwen-seo-check`, `seo_bot_*`.
   Однозначно сопоставить имена с автоматизациями отсюда нельзя: имя меняется от
   запуска к запуску.
2. **Местный `seo-content-operator.timer`** (05:30 UTC, yummyani.site) — каждое
   утро упирается в `NO_ACCESS_AUTHORING`. Его отчётный таймер
   `seo-content-operator-report.timer` не трогать до выбора канала отчёта.

### Запрос к Qwen (один, коротко)

> Отключи (не удаляя историю) все свои повторяющиеся автоматизации, которые
> вызывают `editorial_queue_next`, `editorial_queue_result`, `publish_material`
> или `publish_post`, включая 533bbc0b-0421-4aa0-a917-ee731d050abd. Текущую
> публикацию доведи до конца. Пришли список отключённых: id, название,
> расписание, время последнего запуска. Чтение (`audit_page_seo`,
> `analytics_data`, `editorial_status`) можно оставить.

### Местная команда (после ответа Qwen)

```bash
sudo systemctl disable --now seo-content-operator.timer
```

### Проверка переключения

Через сутки — журнал очереди: выдачи заданий только владельцам
`editor/claude-auto/run-*` и `editor/claude-indexing-operation-02`:

```bash
python3 automation/local/editor-run-audit.py --since "<UTC>" --until "<UTC>" --grid 60
```

До этой проверки переключение не объявляется.

### Откат

`sudo systemctl disable --now editor-run.timer` — фоновый редактор остановлен,
история и журналы сохраняются. Автоматизации Qwen включаются обратно на
srv-qwen.
