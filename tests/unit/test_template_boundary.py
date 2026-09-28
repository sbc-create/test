"""REQ-TEMPLATE-BOUNDARY: шаблон остаётся слоем представления.

Один `import pg` в шаблоне выглядит безобидно и работает — до дня, когда шаблон
нужно собрать без базы, откатить отдельно от платформы или отдать другой ленте.
Тогда выясняется, что слоем представления он не был, и цена перехода уже
уплачена. Правило держится проверкой, а не уговорами.
"""

from __future__ import annotations

from factory.contracts.template_boundary import check_source, check_tree, main


def rules(violations) -> set[str]:
    return {v.rule for v in violations}


def test_direct_database_driver_is_rejected() -> None:
    found = check_source('import { Client } from "pg";')
    assert "прямой драйвер БД" in rules(found)


def test_cache_and_queue_clients_are_rejected() -> None:
    assert "клиент кэша или очереди" in rules(check_source('import Redis from "ioredis";'))
    assert "клиент кэша или очереди" in rules(check_source('const q = require("bullmq");'))


def test_infrastructure_modules_are_rejected() -> None:
    assert "инфраструктурный модуль" in rules(check_source('import fs from "node:fs";'))


def test_server_secrets_are_rejected() -> None:
    assert "секрет в шаблоне" in rules(check_source("const url = process.env.DATABASE_URL;"))


def test_raw_http_to_cms_is_rejected() -> None:
    found = check_source('const r = await fetch("https://public-api.cdnvideohub.com/api/v1/titles");')
    assert "raw HTTP к CMS или источнику" in rules(found)


def test_sdk_usage_is_allowed() -> None:
    """То, ради чего запрет и существует, обязано проходить чисто."""
    allowed = """
    import { getTitleCard } from "@platform/sdk";
    const card = await getTitleCard(id);
    """
    assert check_source(allowed) == []


def test_ordinary_fetch_to_own_api_is_not_flagged() -> None:
    """Запрещён поход в CMS, а не любой сетевой вызов — иначе правило обойдут."""
    assert check_source('await fetch("/api/search?q=" + query);') == []


def test_comments_are_not_violations() -> None:
    """Наказывать за документацию нельзя: упоминание запрета — не нарушение."""
    documented = """
    // Никогда не делайте так: import { Client } from "pg";
    /* process.env.DATABASE_URL здесь запрещён */
    """
    assert check_source(documented) == []


def test_violation_names_the_place_and_the_remedy() -> None:
    """Запрет без замены обходят, а не выполняют."""
    found = check_source('import { Client } from "pg";', path="src/card.tsx")
    assert found[0].path == "src/card.tsx"
    assert found[0].line == 1
    assert "SDK" in found[0].remedy


def test_tree_walk_skips_dependencies_and_build_output(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "card.tsx").write_text('import { Client } from "pg";', encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text('import Redis from "ioredis";', encoding="utf-8")
    (tmp_path / ".next").mkdir()
    (tmp_path / ".next" / "chunk.js").write_text('import fs from "node:fs";', encoding="utf-8")
    (tmp_path / "readme.md").write_text('import { Client } from "pg";', encoding="utf-8")

    found = check_tree(tmp_path)

    assert len(found) == 1, [str(v) for v in found]
    assert found[0].path == "src/card.tsx"


def test_clean_template_passes(tmp_path) -> None:
    (tmp_path / "card.tsx").write_text('import { getTitleCard } from "@platform/sdk";', encoding="utf-8")
    assert check_tree(tmp_path) == []
    assert main([str(tmp_path)]) == 0


def test_cli_exit_code_counts_violations(tmp_path) -> None:
    (tmp_path / "a.tsx").write_text('import { Client } from "pg";', encoding="utf-8")
    (tmp_path / "b.tsx").write_text('import Redis from "ioredis";', encoding="utf-8")
    assert main([str(tmp_path)]) == 2
