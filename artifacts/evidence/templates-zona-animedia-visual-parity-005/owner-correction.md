# Коррекция предыдущего статуса

Владелец переоткрыл визуальную приёмку. Принято и зафиксировано:

| статус | значение |
| --- | --- |
| `ZONA_OPERATIONAL_RELEASE_STATUS` | `PASS` (сохраняется) |
| `ZONA_REFERENCE_PARITY_STATUS` | `FAIL` |
| `ANIMEDIA_REFERENCE_PARITY_STATUS` | `FAIL` |
| `OVERALL_VISUAL_ACCEPTANCE` | `REOPENED` |
| `TEMPLATES_ACCEPTED` | `NO` |

Предыдущая приёмка (`TEMPLATES-ZONA-CANARY-R2-VERIFY`) проверяла маршруты, коды
ответа, `H1`, отсутствие soft-404, canary, откат и restore-forward. Она не
доказывала визуального и структурного соответствия оригиналам и таким
доказательством не объявляется. Её вывод о завершении шаблонного этапа отменён.

Свидетельства той задачи остаются на месте и не перезаписаны:
`artifacts/evidence/templates-zona-canary-r2-verify/`.
