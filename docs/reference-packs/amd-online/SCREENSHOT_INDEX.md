# Снимки референса — Animedia (amd.online)

Статус: **снято**. Прежняя пометка BLOCKED снята замером, а не решением:
доступность проверена 5 последовательными запросами, все вернули HTTP 200
без редиректов при успешной проверке TLS (`availability.json`).

Снимки — полные страницы, по одному файлу на ширину. Внутри пакета лежат
только числа и дайджесты; сами PNG хранятся в evidence-каталоге задания и в
git не попадают (`artifacts/*` в .gitignore) — пакет остаётся свидетельством
о замере, а не копией чужого интерфейса.

| Поверхность | Состояние | URL | Ширина | SHA-256 снимка |
|---|---|---|---:|---|
| home | normal | `https://amd.online/` | 390 | `97560246e10571fb76848b2a8afe736d80fc9247fe39b03c6e04652f49b8bf5d` |
| home | normal | `https://amd.online/` | 768 | `62b6700e86e0719f62d037eee2bc2f86dfb06faca61676fd977427dd4a92932a` |
| home | normal | `https://amd.online/` | 1440 | `484c4dc0e576fa5cd524adde23f3cdf5d09c3a8dde5d179ab28d28a853a8817b` |
| catalog | normal | `https://amd.online/anime/ghanr/3d/` | 390 | `b155cacca7e2ecb1125adece761fdbf953b12ab6c368918001a65e912c53a840` |
| catalog | normal | `https://amd.online/anime/ghanr/3d/` | 768 | `29f19d3a724f67cb48c2a755166a1a01242fa82212e70f15bb88bd085b7ac5f8` |
| catalog | normal | `https://amd.online/anime/ghanr/3d/` | 1440 | `f441c88c5d4a46a64627063b09a96ce9b6ed953c960d53236263440490169c2c` |
| collection_hub | normal | `https://amd.online/anime-collections/` | 390 | `bd601294ea7c00526592b5d4614ca867c8b6d185e04f4e28cfcedce3c2ad6fa6` |
| collection_hub | normal | `https://amd.online/anime-collections/` | 768 | `b658260241fe7ef26a1e06eb53c621d5562b218c4c00e4ee7a4f0cbad5c97e24` |
| collection_hub | normal | `https://amd.online/anime-collections/` | 1440 | `3ea6dbed59cfcc6678e9003bec09b0ac2436991a9ff978f6889d906e2eb97874` |
| title | normal | `https://amd.online/1200-raskolotaja-bitvoj-sineva-nebes-5.html` | 390 | `23c96a746f415282d41377b3e54a6b60f8acf402198bef7b55868ae966469b52` |
| title | normal | `https://amd.online/1200-raskolotaja-bitvoj-sineva-nebes-5.html` | 768 | `2b455c7de21de7b63edd2f7dd57d212762f5303630c8696d3b8edbf9803b9a9a` |
| title | normal | `https://amd.online/1200-raskolotaja-bitvoj-sineva-nebes-5.html` | 1440 | `e01089f3b88fce7ac5b8bb830fb30aa238d603461210317dd154f9861004c950` |
| not_found | not_found | `https://amd.online/nonexistent-refpack-probe-01/` | 390 | `c6b71bf4e0902d4d8b350e938e36e3068f3cbef447b507294a5861b0d08e5eb4` |
| not_found | not_found | `https://amd.online/nonexistent-refpack-probe-01/` | 768 | `268f10c9de1884b0aec1b8303807b5a597456ea8d019de432500d2b8a5126fe0` |
| not_found | not_found | `https://amd.online/nonexistent-refpack-probe-01/` | 1440 | `25d7b5c659acaa862002f0df2f542241e9569db7513bf336c7860864dbb6bb55` |

Время съёмки (UTC): `2026-09-16T16:29:30.260Z`.
Инструмент: `tests/tools/measure_reference.js` (CDP, Chromium из playwright).

## Цветовой прогон 2026-09-16

Отдельный прогон `tests/tools/measure_reference_colors.js`, свои снимки и свои
дайджесты. Снимок делается **до** наведения и клавиатурного фокуса: иначе в
дайджест попало бы состояние, вызванное самим замером, и сверить его было бы
нельзя.

| Поверхность | URL | Ширина | SHA-256 снимка | Снято (UTC) |
|---|---|---:|---|---|
| home | `https://amd.online/` | 390 | `c478649e6d6d9f22307a43b61e1b1ed02713a508d8dafb77885d3134e9319d01` | 2026-09-16T19:48:04.059Z |
| home | `https://amd.online/` | 768 | `fc8a23961140796c7fcfc0e78240182263badfa31208ce6df0c4fdb77746298d` | 2026-09-16T19:48:23.031Z |
| home | `https://amd.online/` | 1440 | `b82711be4175d14436baa84ca774f6fc67da53902c8ea97d9474c65a5d261df0` | 2026-09-16T19:48:41.840Z |
| catalog | `https://amd.online/anime/ghanr/3d/` | 390 | `e30e7ae3b5c7cfb035a33a435ef371db3b906af5b0a1eebc5929824dcce8811c` | 2026-09-16T19:49:05.598Z |
| catalog | `https://amd.online/anime/ghanr/3d/` | 768 | `f4249f7a3d14d01e12024f82fd0fe7a9c6a434adf0b719ad055af56f45de1c77` | 2026-09-16T19:49:25.247Z |
| catalog | `https://amd.online/anime/ghanr/3d/` | 1440 | `728c4e49c67a3a5b1b5dc1100f11df4fa6fd5bf7b3326b8a10c4b37f15fca493` | 2026-09-16T19:49:43.654Z |
| collection_hub | `https://amd.online/anime-collections/` | 390 | `f20b2cba6542b06dc0e2f388503a3b69e93f1b5550d9155b7888a572d29aee73` | 2026-09-16T19:50:08.192Z |
| collection_hub | `https://amd.online/anime-collections/` | 768 | `b658260241fe7ef26a1e06eb53c621d5562b218c4c00e4ee7a4f0cbad5c97e24` | 2026-09-16T19:50:27.099Z |
| collection_hub | `https://amd.online/anime-collections/` | 1440 | `3ea6dbed59cfcc6678e9003bec09b0ac2436991a9ff978f6889d906e2eb97874` | 2026-09-16T19:50:45.193Z |
| title | `https://amd.online/1200-raskolotaja-bitvoj-sineva-nebes-5.html` | 390 | `49295ee18f723a83d6896e9edf2ec1421ddd65fef0021e696dfc91b7902d0fd4` | 2026-09-16T19:51:06.178Z |
| title | `https://amd.online/1200-raskolotaja-bitvoj-sineva-nebes-5.html` | 768 | `ae9943944255ee346776830bdd9fba8beb40707a864a2c49df012ddbd53c0ba4` | 2026-09-16T19:51:23.842Z |
| title | `https://amd.online/1200-raskolotaja-bitvoj-sineva-nebes-5.html` | 1440 | `bdc96ef10afe3f273e95cb50bceb4bd151790e79744803107b974c9c87bc2330` | 2026-09-16T19:51:41.374Z |
| not_found | `https://amd.online/nonexistent-refpack-probe-01/` | 390 | `3b8a7520a284d52ea50ac427846b9babb738cf5b0723b52a5f6bc513bb366b4f` | 2026-09-16T19:52:04.935Z |
| not_found | `https://amd.online/nonexistent-refpack-probe-01/` | 768 | `1deeda9d3c7814f2812abf0f50c2849cdb6bb512683ec3dd16fdb5fab65e0cb6` | 2026-09-16T19:52:17.539Z |
| not_found | `https://amd.online/nonexistent-refpack-probe-01/` | 1440 | `50c10028fbe65a4e6e0f81f5cec9355c1b8f7b30d93bcff5075f528f2cf67264` | 2026-09-16T19:52:30.090Z |

Сами замеры лежат рядом со снимками; дайджест файла замеров позволяет
проверить, что цифры в пакете не разошлись с доказательством:

| Поверхность | Файл замеров | SHA-256 файла |
|---|---|---|
| home | `artifacts/reference-pack-amd-online-01/capture-colors/home/colors.json` | `8bd36b71aa53a070d01e1e37cbdef86d94b19091e15182ca59e3c21fd8218b71` |
| catalog | `artifacts/reference-pack-amd-online-01/capture-colors/catalog/colors.json` | `bb7ed778ec43659ab4d5555d75624bcd2e495559b8f721f509bdfda2169fedc2` |
| collection_hub | `artifacts/reference-pack-amd-online-01/capture-colors/collection_hub/colors.json` | `b4faaa93d030445b3f051153a56360b71a2194129fc007b8dcb9bb892ddee297` |
| title | `artifacts/reference-pack-amd-online-01/capture-colors/title/colors.json` | `832d675c47f206059351048da53f0a2ccffa69f52bcee339ab51d1dbd51450b3` |
| not_found | `artifacts/reference-pack-amd-online-01/capture-colors/not_found/colors.json` | `f6eb3a1c521fc699e437633da58f13f11e80a292f0c080d98a2164d250a0d12e` |
Состояние страницы: загрузка дождана инструментом до `load`; ленивые
изображения ниже первого экрана на момент снимка могли не подгрузиться —
это отражено в `page_height` и отмечено здесь, а не скрыто.

Исключения из сравнения: `EXCLUSIONS.md`.
