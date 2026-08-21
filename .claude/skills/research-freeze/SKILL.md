---
name: research-freeze
description: Собрать или обновить базу знаний фабрики и зафиксировать freeze. Использовать при появлении новой официальной документации DLE/VK/SEO, новых переданных материалов или перед сменой версии DLE.
allowed-tools: Read, Grep, Glob, Bash(python3 -m factory knowledge *), WebFetch
---

# research-freeze

Единственный разрешённый способ изменить `knowledge/`.

1. **Проверь текущий freeze:** `python3 -m factory knowledge verify`. Расхождение хешей —
   стоп: разберись, кто менял базу мимо этого скилла.
2. **Собери источники.** Для каждого зафиксируй в `knowledge/SOURCE_REGISTRY.yaml`:
   `url`/`path`, владельца, версию, дату обращения, назначение, SHA-256 для файлов,
   статус `approved|rejected|superseded|unavailable_blocked|not_provided`.
   Недоступный источник помечается `unavailable_blocked` с доказательством (код ответа,
   запись из `$HTTPS_PROXY/__agentproxy/status`) — пересказ вместо первоисточника запрещён.
3. **Раздели знание:** подтверждённые факты → `FACTS.md`, решения → `DECISIONS.md`,
   пробелы → `UNKNOWNS.md`, чужие идеи → `THIRD_PARTY_REVIEW.md`.
4. **Обнови доменные пакеты:** `DLE_20_COMPATIBILITY.md`, `VK_CONTENT_AND_ADS_CONTRACT.md`,
   `SEO_KNOWLEDGE_PACK.md`, `SEO_INDEXABILITY_MATRIX.yaml`, `INFRASTRUCTURE_INVENTORY.yaml`.
5. **Заморозь:** `python3 -m factory knowledge freeze --version <YYYY-MM-DD.N>`.
   Скрипт сам пересчитывает SHA-256 и пишет `KNOWLEDGE_FREEZE.yaml` — вручную файл не редактируется.
6. **Проверь:** `python3 -m factory knowledge verify` и `pytest tests/unit/test_knowledge_freeze.py -q`.

Смена версии DLE без отдельной compatibility-проверки и нового freeze запрещена.
