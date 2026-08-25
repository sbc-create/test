# seo-operator

Автономный SEO-оператор и главный редактор для портфеля из 15–20 сайтов:
ежедневный сбор данных, диагностика, редакционный календарь, эксперименты
с контролем и откатом, накопление доказанного опыта.

## Что это делает

- Собирает Search Console, Яндекс Вебмастер, Метрику, логи и CMS — с обязательными
  метаданными свежести, потому что сравнивать неполные дни с полными нельзя.
- Классифицирует запросы по интенту, находит каннибализацию внутри сайта и между сайтами.
- Считает opportunity для новых тайтлов; отсутствие прав обнуляет приоритет, а не понижает его.
- Ведёт редакционный календарь: анонс → релиз → истечение, со снятием просроченных
  обещаний с главной.
- Проводит эксперименты на канарейке с holdout, stop-loss и доказанным откатом.
- Копит паттерны только из зрелых экспериментов и хранит опровергнутые гипотезы.

## Чего это не делает

- Не создаёт комментарии, отзывы, голоса и оценки. Никогда, ни в каком режиме.
- Не выдумывает даты, факты, рейтинги и доступность.
- Не обещает рост без просадок: алгоритмы, спрос и конкуренты вне управления.
  Обещание — измеримый рост на сопоставимых периодах, ограниченный масштаб неудачи
  и доказанный откат.

## Установка

```bash
python3 -m pip install -e .    # или просто export PYTHONPATH=$PWD/src
```

Зависимость одна: `PyYAML`.

## Команды

```bash
seo northstar [--dedup none|estimated|exact] [--overlap 0.15]   # organic_daily_unique
seo forecast [--capacity N]        # достаточно ли сайтов для 7 млн уников/сут
seo access audit                   # матрица доступов, ТЗ §3.3
seo monthly-report                 # прогноз в трёх сценариях
seo checkpoint [--no-tests]        # финальный отчёт и критерии приёмки
seo portfolio validate|status|report
seo daily-run [--apply] [--site ID] [--date YYYY-MM-DD]
seo weekly-report
seo experiment status|evaluate|rollback --id EXP-...
seo editorial discover --site ID
seo cms-mutate --site ID --target T --action A --tier N --experiment E [--apply]
seo audit list|verify
seo guardrails baseline|verify
seo secrets check
seo permissions test
```

Коды выхода: `0` ok, `1` ошибка, `3` BLOCKED_AUTHORIZATION, `4` BLOCKED_PROTECTED_GUARDRAIL —
планировщик различает их без разбора текста.

## Тесты

```bash
python3 -m pytest tests/ -q
```

550 тестов: permission corpus (27 разрешённых + 45 запрещённых + попытки обхода),
mutation-тесты защищённого ядра, определение `organic_daily_unique` и дедупликация
между доменами, прогноз числа сайтов, difference-in-differences, Action Ledger,
Secret Hub, квоты и деградация на 100+ сайтах, изоляция tenant, зрелость и конфаундеры
экспериментов, provenance, межсайтовые дубли, отказ от фиктивной активности,
технический SEO-аудит, сквозной прогон цикла и CLI.

## Развёртывание

```bash
deploy/install.sh --repo <git-url> --commit <SHA>   # чистый хост
deploy/restore-drill.sh --target /var/lib/seo-operator-drill
```

Расписание (`deploy/systemd/`) устанавливается, но **не включается** автоматически:
планировщик на непроверенном хосте начнёт писать раньше, чем человек посмотрит
на первый dry-run.

## Документация

- `CLAUDE.md` — правила работы контура
- `seo/NORTH_STAR_DEFINITION.md` — определение целевого показателя
- `seo/UNKNOWNS.md` — что нужно от владельца, одним пакетом
- `seo/BASELINE_REPORT.md` — почему baseline ещё не установлен
- `seo/reports/CHECKPOINT.md` — статус по критериям приёмки ТЗ §17
- `docs/WORKTREES.md` — запуск двух окон
- `docs/UNATTENDED_SAFE.md` — модель разрешений
- `docs/RESTORE.md` — восстановление на чистом хосте, RPO/RTO
