"""Наборы содержимого витрин-стендов — по запросу HANDOFF-032.

Handoff просил ровно одно: набор записей и его отпечаток, чтобы очередь
разбора перестала быть пустой и путь публикации стал проверяемым. Здесь
закреплены его требования, а не наши удобства.

Отдельно о том, чего эти наборы НЕ означают. Витрины site-a, site-b и site-c
остаются стендами: домены вида `*.localhost`, `production_authorized: false`,
`ssh_host_ref: null`, рантайма и vhost нет. Набор не делает витрину боевой, и
засчитывать его как приёмку на реальном сайте нельзя.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SITES = ("site-a", "site-b", "site-c")


def _package(site: str) -> dict:
    return yaml.safe_load((ROOT / "sites" / site / "package.yaml").read_text(encoding="utf-8"))


def _catalog(site: str) -> dict:
    return json.loads(
        (ROOT / "sites" / site / "content" / "catalog.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("site", SITES)
class TestНаборСодержимогоСтенда:
    def test_пакет_ссылается_на_существующий_файл(self, site):
        pkg = _package(site)
        ref = pkg.get("content_package_ref")
        assert ref, "пакет не объявляет content_package_ref"
        assert (ROOT / "sites" / site / ref).is_file(), f"файла {ref} нет"

    def test_отпечаток_совпадает_с_объявленным(self, site):
        from factory.validation import _resolve_site_file, _sha256

        pkg = _package(site)
        declared = pkg.get("content_package_sha256")
        assert declared, "отпечаток не объявлен: чтение без сверки пропустит подмену"
        path = _resolve_site_file(site, pkg["content_package_ref"])
        assert _sha256(path) == declared

    def test_у_каждой_записи_есть_устойчивый_идентификатор(self, site):
        """Требование handoff, названное прямо: запись без идентификатора
        отвергается целиком. Выдуманный идентификатор нельзя сопоставить ни с
        чем, и первое же обновление создаст дубль."""
        titles = _catalog(site)["titles"]
        assert titles, "набор пуст"
        ids = [t.get("id") for t in titles]
        assert all(ids), "есть записи без идентификатора"
        assert len(ids) == len(set(ids)), "идентификаторы повторяются"

    def test_набор_объявляет_себя_синтетическим(self, site):
        """Запись обязана называть себя фикстурой в тексте, который видит
        читатель.

        Иначе синтетика неотличима от публикации: страница выглядит настоящей,
        и первый же смотрящий примет её за содержимое витрины. Отметка `kind:
        fixture` в заголовке файла этого не решает — её на странице не видно.
        """
        catalog = _catalog(site)
        assert catalog.get("kind") == "fixture"
        for title in catalog["titles"]:
            text = f"{title.get('title','')} {title.get('description','')}".lower()
            assert "фикстур" in text or "синтетич" in text, (
                f"запись {title.get('id')} не объявляет себя синтетической")

    def test_разделы_взяты_из_навигации_витрины(self, site):
        """Категории не придумываются: витрина уже объявила, из чего состоит."""
        package_text = (ROOT / "sites" / site / "package.yaml").read_text(encoding="utf-8")
        for category in _catalog(site)["categories"]:
            assert category["slug"] in package_text, (
                f"раздел {category['slug']} отсутствует в навигации витрины")

    def test_витрина_остаётся_стендом(self, site):
        """Страж против тихого превращения стенда в «принятую витрину».

        Если у витрины появится домен и разрешение на production, набор
        синтетики обязан быть заменён настоящим содержимым — и эта проверка
        заставит об этом вспомнить.
        """
        pkg = _package(site)
        assert pkg.get("production_authorized") is False
        assert str(pkg.get("domain", "")).endswith(".localhost"), (
            "у витрины появился настоящий домен — синтетический набор больше не годится")
