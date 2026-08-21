# ADR-0002. Закрытый режим данных

- Статус: принято, 2026-08-21

## Контекст

Массовая фабрика легко превращается в генератор мусора: недостающие данные подставляются
«разумными умолчаниями», картинки берутся откуда придётся, тексты дописываются моделью.
Это и есть scaled content abuse, а в случае VK-контента — ещё и нарушение прав.

## Решение

После `knowledge/KNOWLEDGE_FREEZE.yaml` фабрика работает только на: замороженной базе
знаний, коде и шаблонах, явно переданном site package и endpoint из `network_allowlist`.

Технические следствия, каждое из которых закреплено тестом:

| Правило | Реализация | Тест |
|---|---|---|
| Пустое обязательное поле — блокер, а не умолчание | `factory/validation.py` | `test_validation.py::test_empty_required_field_is_not_defaulted` |
| Нет alt — материал не публикуется | `factory/render.py::_image` | `test_content_rights.py::test_material_without_alt_is_not_published` |
| Пустой раздел не публикуется как indexable 200 | `_render_listing` + матрица | `test_content_rules.py::test_empty_category_is_not_published_as_indexable_200` |
| Недоступное видео → состояние, а не подмена | `render._render_episode` | `test_content_rules.py::test_unavailable_video_renders_status_not_substitute` |
| Сеть по умолчанию закрыта (fail-closed) | `.claude/hooks/guard_rules.py::closed_world` | `test_guard_rules.py::test_closed_world_is_fail_closed` |
| Каталог проверяется по SHA-256 независимо от типа | `validation._check_content_rights` | `test_validation.py::test_catalog_checksum_mismatch_is_blocked_rights` |

## Альтернативы

«Мягкий режим» с предупреждениями вместо блокеров отвергнут: предупреждение в массовом
конвейере read-only — оно ничего не останавливает, а сайт всё равно публикуется.
