# Запрос независимой рецензии — 26.10.2026, вечер

Автор черновиков — seo/claude-session (wt-portable-site-cell-01), исполнитель `editor/claude-session/seo-operator-20261026`. Рецензент должен быть другим исполнителем: автор материала не заменяет рецензента (поручение владельца 26.10, п. 2; задача — `docs/seo-operator/TASK_20261026_SEO_CONTINUATION.md`).

## Предмет

Девять черновиков в хранилищах `/srv/sites/*/runtime/overlays/<домен>/drafts.json`, состояние `verified` (ворота формы пройдены), НЕ опубликованы:

| Домен | Слаг | Что это | Источник фактов | body_digest |
|---|---|---|---|---|
| zonafilm12.site | empatiya-2 | новый | статья Википедии из var/editor-runs/run-session-20261026T1425Z/film-empatiya-2.json | `e21f2050dbdd2700` |
| zonafilm.space | dzho-pera-govorit-s-vami | новый | статья Википедии из var/editor-runs/run-session-20261026T1425Z/film-dzho-pera-govorit-s-vami.json | `2bcb6d2dc153bff0` |
| zonafilm.space | vazhna-tolko-lyubov | новый | статья Википедии из var/editor-runs/run-session-20261026T1425Z/film-vazhna-tolko-lyubov.json | `cc1f47c2f6414d40` |
| animedia.icu | bezdomnyy | правка: убрано «корейский» (страна выведена из манхвы) | shikimori 59868 | `6dc5bcf30a518226` |
| animedia.icu | slabyy-pyatitysyacheletniy-drakon-vegetarianec-2 | правка: «дунхуа» → «сериала» (в каталоге жанр только «аниме») | shikimori 58779 | `2668226672f32ef5` |
| zonafilm.space | povsednevnaya-zhizn-stazhera-muchitelya | правка: убрано «комедийный» (нет в жанрах) | shikimori 61886 | `4d76e936fc457876` |
| animedia.icu | priklyucheniya-digimonov-02-nachalo | правка: «Хикари» → «Кари», «Избранным» → «Дигидестинированным» (как в источнике) | shikimori 49523 | `8e552af7b4347e0b` |
| an1meg0.site | krasnyy-foton-zillion | правка: убрано «инопланетяне» о Нозе (в источнике не сказано) | shikimori 2688 | `8639c720eaffb835` |
| an1mego.site | argonavis-iz-ura-mechte | правка: убрано «о студенческой рок-группе» | shikimori 40677 | `45eb075480514717` |

Тела черновиков — в хранилищах; копии — `var/editor-runs/run-session-20261026T1425Z/body-<слаг>.txt` (новые) и `body-<слаг>-correction.txt` (правки).

## Критерий приёмки

По каждому черновику — четыре проверки операции рецензии (`review-materials-batch.py`): произведение названо; источник записан; посторонних имён нет; качество без замечаний. Плюс сверка каждого имени и подробности с источником в столбце «Источник фактов» (для трёх новых — статья Википедии, у английских статей имена переведены: Marquette → Маркетт, Michigan → Мичиган, Sarah → Сара, Upper Peninsula → Верхний полуостров). Отзыв `review` записывается в черновик с `body_digest`, равным текущему. Отклонённый черновик не публикуется — причина в заметке, правлю адресно.

## Что дальше

После принятого отзыва я публикую тело черновика без единой правки (`publish_material`), закрываю задание очереди и проверяю страницу: 200, текст в основном блоке, canonical на себя, `index, follow`. Правки заменяют прежнюю публикацию (`previous_generation`).

## Дополнение 20:57Z — ещё 2 черновика (та же партия фильмов и сериалов)

| Домен | Слаг | Что это | Источник фактов | body_digest |
|---|---|---|---|---|
| zonafilm.space | parizaad | новый, сериал | статья Википедии `film-parizaad.json` (Naheed → Нахид, Rawalpindi → Равалпинди, Saeeda → Саида) | `f74043209fbd9245` |
| zonafilm12.site | c-o | новый, фильм | статья Википедии `film-c-o.json` (Visakhapatnam → Висакхапатнам, Kancharapalem → Кантчарапалем) | `253572a3706a2795` |

## Дополнение 21:09Z — ещё 2 черновика

| Домен | Слаг | Что это | Источник фактов | body_digest |
|---|---|---|---|---|
| zonafilm12.site | shorsi | новый, сериал | статья Википедии `film-shorsi.json` (Sudbury Bulldogs → «Садбери Бульдогс», Nat → Нэт, Northern Ontario → Северное Онтарио) | `c6de49f3c25603ba` |
| zonafilm.space | sang-e-mah | новый, сериал | статья Википедии `film-sang-e-mah.json` (Laspiraan → Ласпираан, Hilmand → Хилманд, Nasrullah Khan → Насрулла Хан, Haji Marjaan Khan → Хаджи Марджан Хан, Zarsanga → Зарсанга, Hikmat → Хикмат, Gul Meena → Гуль Мина, Zarghuna → Заргуна, Ghag → «Гхаг») | `9c4b5a021cbcae35` |

