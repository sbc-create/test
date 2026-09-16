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
Состояние страницы: загрузка дождана инструментом до `load`; ленивые
изображения ниже первого экрана на момент снимка могли не подгрузиться —
это отражено в `page_height` и отмечено здесь, а не скрыто.

Исключения из сравнения: `EXCLUSIONS.md`.
