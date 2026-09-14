# Воспроизведение `test_job_result` на обоих коммитах

Раньше этот провал был назван «не относящимся к задаче» по косвенному признаку.
Этого недостаточно: «не относится» — вывод, а не наблюдение, и делать его без
опыта нельзя. Ниже — опыт.

## Постановка

Два чистых worktree одного репозитория, один интерпретатор, одна машина,
запуск подряд:

| | коммит |
| --- | --- |
| base | `a7f7cb6236fbc9770af949ef98eae511cd3c8fc4` |
| task | `a699b461d1525395cf7f9a1c981f6fe0bcc01eaf` |

Проверяется гипотеза: провал вызван отсутствием артефактов пилота
(`artifacts/jobs/pilot-local/*.json`), которые не отслеживаются git и потому
отсутствуют в любом свежем worktree, — а не изменениями задачи.

Опыт поставлен в двух условиях, потому что одного мало: совпадение провалов
доказывает лишь одинаковое поведение при нехватке данных, но не то, что
причина именно в ней.

## Условие 1 — артефактов нет (как в свежем worktree)

| коммит | результат |
| --- | --- |
| base `a7f7cb6` | `1 failed, 9 passed` |
| task `a699b46` | `1 failed, 9 passed` |

Совпадает всё: тест
(`test_real_pilot_results_are_schema_valid`), строка (`test_job_result.py:69`)
и текст (`пилот обязан оставить результат задания`).

## Условие 2 — артефакты одинаковы и присутствуют

В оба дерева скопирован один и тот же каталог `artifacts/jobs/pilot-local`:

| | base | task |
| --- | --- | --- |
| файлов | 270 | 270 |
| совокупный sha256 списка хешей | `2bd265a2be45ac54…` | `2bd265a2be45ac54…` |

| коммит | результат |
| --- | --- |
| base `a7f7cb6` | `10 passed` |
| task `a699b46` | `10 passed` |

## Вывод

Поведение коммитов **идентично в обоих условиях**. Тест падает тогда и только
тогда, когда отсутствуют неотслеживаемые артефакты пилота, и проходит, как
только они на месте, — одинаково на базовом и на задачном коммите.

Регрессии задачи нет. Это дефект не кода, а среды: тест требует данных,
которых в чистом checkout не бывает, и об этом стоит знать отдельно от текущей
работы — но чинить его в рамках транзакции про границу root не следует, он о
другом.

## Воспроизведение

```bash
git worktree add --detach var/worktrees/repro-base a7f7cb6
git worktree add --detach var/worktrees/repro-task a699b46
# условие 1
(cd var/worktrees/repro-base && pytest tests/unit/test_job_result.py -q)
(cd var/worktrees/repro-task && pytest tests/unit/test_job_result.py -q)
# условие 2
cp -a artifacts/jobs/pilot-local var/worktrees/repro-base/artifacts/jobs/
cp -a artifacts/jobs/pilot-local var/worktrees/repro-task/artifacts/jobs/
(cd var/worktrees/repro-base && pytest tests/unit/test_job_result.py -q)
(cd var/worktrees/repro-task && pytest tests/unit/test_job_result.py -q)
```
