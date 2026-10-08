# Фоновый редактор сети и переключение на одного основного редактора

Введено 2026-10-08 по решению владельца: основной исполнитель редакционной
работы — Claude.

## Как устроено

| часть | где | что делает |
| --- | --- | --- |
| расписание | `automation/host/editor/editor-run.timer` | каждые 5 мин лёгкая проверка без модели (`editor-gate`); модель — только если есть работа и с прошлого запуска модели ≥ 55 мин, то есть не чаще раза в час |
| ручной запуск | `editor-run-manual.service` | `sudo systemctl start editor-run-manual.service`, метка `trigger=systemd-manual`, без шлюза |
| запуск | `automation/host/editor/editor-run.sh` | `flock` (пересечения исключены), шлюз, Claude Code без интерфейса (`claude -p`), предел 25 мин, запись `var/editor-runs/<run_id>.*`; пропуски шлюза — `var/editor-runs/gate.jsonl` |
| источники | `automation/local/source_fetch.py` | Shikimori API по ID каталога; официальный сайт по ссылке Shikimori с проверкой robots.txt; MAL не читается (D199) |
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

## Проверка первого полного запуска

1. Ручной запуск службы (метка `systemd-manual`):
   `sudo systemctl start editor-run-manual.service`
2. Запуск таймером (метка `systemd-timer`) — первый после установки, когда шлюз
   ответит «работа есть» (сейчас кандидатов 5); не позже часа после установки.
3. Итог каждого запуска: `python3 -m seo_operator.cli editor-run-status` и
   `var/editor-runs/<run_id>.verify.json`. Полный запуск — `verdict: COMPLETE`,
   все пять шагов `true`: выдача задания, чтение источника, результат
   TEXT_WRITTEN, запись publish автора `editor/claude-auto/run-<run_id>` в
   history.jsonl, текст на публичной странице. `confirmed: true` — только при
   полном запуске с меткой `systemd-timer`.
4. Честный исход без публикации (`NO_PUBLICATION`: SOURCES_MISSING или нет
   задачи) — не сбой, но и не подтверждение полного цикла.

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

### Что уже отключено

По отчёту Qwen владельцу 2026-10-08 отключены три автоматизации описаний:
`533bbc0b-0421-4aa0-a917-ee731d050abd`, `cc8ea6f9-22ed-49ce-9c12-56644b5f335a`,
`0893f3ee-a7d0-4c24-b3fb-749700553d5e`. Обратно не включаются. Активные чужие
аренды не трогаются: шлюз и редактор берут только свободные задания Animedia.

Подтвердить отключение отсюда можно только следами: после установки за сутки
в журнале очереди не должно быть выдач именам вида `editor_automation*`,
`editor_bot*`, `editor_auto*` (список рядов — в истории этого файла).

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
