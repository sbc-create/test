# Owner summary — COMMUNITY-RATINGS-06

1. **Сайт:** голосование включено на `yummyani.site` (space `yummy`).
2. **Процент:** 1% посетителей (детерминированная когорта).
3. **Идентификация:** сервер выдаёт случайный непрозрачный ID в HttpOnly cookie `yummy_cr_vid`, подписанный HMAC; регистрация не нужна.
4. **Что хранится:** только opaque identity id + оценка + audit; без ФИО/email/телефона.
5. **IP / email / fingerprint:** не хранятся (IP только peppered network bucket для антифрода, с TTL).
6. **Дважды:** нет — один активный голос на тайтл; повтор обновляет.
7. **Изменить/удалить:** да, только свой голос.
8. **Средняя:** S/N по точным сумме и числу; показ с 1 знаком; при N=0 — «Пока нет пользовательских оценок», не 0.
9. **Preview = write:** да, одна библиотечная формула.
10. **Shikimori в публичной оценке Yummy:** нет.
11. **Настоящих голосов сейчас:** 0 (после очистки supervised/live тестов).
12. **Тестовые голоса:** не остались.
13. **Антифрод:** лимиты и quarantine-путь готовы; авто-kill по safety gates.
14. **Ошибки БД / mismatch:** integrity ok, mismatches=0.
15. **Индексация yummyani.site:** OPEN.
16. **Комментарии:** выключены; контракт следующего этапа в COMMENTS_STAGE_NEXT.md.
17. **1%→10%:** ≥24ч наблюдения, security bypasses=0, mismatch=0, ручной owner approval.
18. **Выключить запись одной операцией:** `trigger_kill_switch(...)` или `disable_public_writes()` + overlay flag 0.
19. **Следующее решение владельца:** после 24ч — approve 10% packet (или kill).
20. **Комментарии:** COMMUNITY-COMMENTS-01 по COMMENTS_STAGE_NEXT.md.
