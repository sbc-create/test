"""Доставка и производитель каталогов не пишут хранилище одновременно, и
свежее поколение не заменяется устаревшим.

Повод — измеренное наложение. 10 октября 2026 доставка через очередь шла
12:22:01–12:23:01, а шаг публикации суточного прогона — 12:20:13–12:32:45, и
обе стороны писали каталог одной и той же витрины (zona-02). В тот раз
обошлось: издатель переписал файл атомарно позже, итог сошёлся побайтно. Но
«обошлось» — не свойство механизма, и полагаться на порядок во времени здесь
нельзя.

Почему собственного замка исполнителя было мало. Он берётся на `site+операцию`
и честно исключает две ЗАЯВКИ по одной витрине. Производитель каталогов
заявкой не является: он приходит мимо очереди, от root, и пишет то же
хранилище. Два разных замка не исключают друг друга — значит замок должен быть
один, тот самый файл, который берёт `nova-catalog-publish.py`.

Второе свойство — про поколение. `снимок_совпадает` отвечает только «то же
самое или нет»; «старее» она считает изменением и пропускает. Заявка на
доставку, собранная до суточного прогона и выполненная после него, откатила бы
витрину на прежнее поколение молча и с исходом `delivered`. Поэтому
сравнивается `builtAt` из самих файлов, а не время файла.

Проверки идут на изолированных данных: свой каталог-источник, своё хранилище
витрины, свой файл замка. Ни хранилищ хоста, ни боевого замка они не касаются.
"""
from __future__ import annotations

import fcntl
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import privileged  # noqa: E402


def снимок(каталог: Path, site_id: str, *, revision: str, built_at: str,
           записей: int = 400) -> None:
    """Файл того же порядка полей и масштаба, что у производителя.

    Масштаб важен: `revision` лежит ЗА записями, то есть в хвосте файла, и
    чтение одной головы его не находит.
    """
    каталог.mkdir(parents=True, exist_ok=True)
    (каталог / f"{site_id}-catalog.json").write_text(json.dumps({
        "builtAt": built_at,
        "count": записей,
        "items": [{"slug": f"z-{i}", "title": "Тайтл " * 12} for i in range(записей)],
        "revision": revision,
        "schema": "nova-catalog/2.0.0",
        "site": site_id,
    }, ensure_ascii=False), encoding="utf-8")
    (каталог / f"{site_id}-details.json").write_text(
        json.dumps({"catalog_revision": revision, "details": {}},
                   ensure_ascii=False), encoding="utf-8")
    assert (каталог / f"{site_id}-catalog.json").stat().st_size > 32768


@pytest.fixture()
def свой_замок(tmp_path, monkeypatch):
    """Файл замка в песочнице: боевой замок проверка не трогает."""
    путь = tmp_path / "nova-catalog-publish.lock"
    monkeypatch.setattr(privileged, "ЗАМОК_ИЗДАТЕЛЯ", путь)
    return путь


def test_замок_берётся_и_отпускается(свой_замок):
    with privileged.замок_издателя() as состояние:
        assert состояние["held"] is True
        assert состояние["lock"] == str(свой_замок)
    # После выхода замок свободен: иначе одна доставка закрыла бы все
    # последующие до перезапуска процесса.
    with privileged.замок_издателя() as снова:
        assert снова["held"] is True


def test_занятый_замок_останавливает_доставку(свой_замок):
    """Главное свойство: пока производитель пишет, доставка не начинается."""
    свой_замок.parent.mkdir(parents=True, exist_ok=True)
    чужой = open(свой_замок, "a+")
    fcntl.flock(чужой, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(privileged.PrivilegedRefused) as отказ:
            with privileged.замок_издателя():
                pytest.fail("доставка начала работу при занятом замке")
        assert "производитель каталогов сейчас пишет снимки" in str(отказ.value)
    finally:
        fcntl.flock(чужой, fcntl.LOCK_UN)
        чужой.close()


def test_сухой_прогон_не_падает_из_за_чужой_занятости(свой_замок):
    """План ничего не меняет, и отказывать ему из-за чужого прогона нельзя.

    Иначе `plan` стал бы нестабильным: он отвечал бы по-разному в зависимости
    от того, идёт ли в эту минуту суточная публикация.
    """
    свой_замок.parent.mkdir(parents=True, exist_ok=True)
    чужой = open(свой_замок, "a+")
    fcntl.flock(чужой, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with privileged.замок_издателя(только_проверить=True) as состояние:
            assert состояние["held"] is False
            assert "занят" in состояние["note"]
    finally:
        fcntl.flock(чужой, fcntl.LOCK_UN)
        чужой.close()


def test_поколение_источника_новее_доставка_разрешена(tmp_path):
    источник, цель = tmp_path / "front", tmp_path / "cell"
    снимок(источник, "zona-02", revision="новое", built_at="2026-10-10T11:46:13Z")
    снимок(цель, "zona-02", revision="старое", built_at="2026-10-08T03:15:24Z")
    итог = privileged.снимок_не_старее(источник, цель, "zona-02")
    assert итог["verdict"] == "не старее", итог


def test_поколение_у_витрины_новее_доставка_называет_это(tmp_path):
    """Тот самый откат поколения, который проходил молча."""
    источник, цель = tmp_path / "front", tmp_path / "cell"
    снимок(источник, "zona-02", revision="старое", built_at="2026-10-08T03:15:24Z")
    снимок(цель, "zona-02", revision="новое", built_at="2026-10-10T11:46:13Z")
    итог = privileged.снимок_не_старее(источник, цель, "zona-02")
    assert итог["verdict"] == "источник старее", итог
    assert "2026-10-10T11:46:13Z" in итог["note"]


def test_непрочитанное_поколение_не_считается_несвежим(tmp_path):
    """Недоказанная несвежесть — не несвежесть.

    Останавливать доставку из-за того, что поколение прочитать нечем, значило
    бы выдавать отсутствие измерения за измеренное отставание — ошибка, уже
    стоившая этому контуру трёх суток.
    """
    источник, цель = tmp_path / "front", tmp_path / "cell"
    снимок(источник, "zona-02", revision="новое", built_at="2026-10-10T11:46:13Z")
    цель.mkdir(parents=True)
    итог = privileged.снимок_не_старее(источник, цель, "zona-02")
    assert итог["verdict"] == "не измерено", итог


def test_stage_snapshot_отказывает_на_устаревшем_источнике(tmp_path, monkeypatch):
    """Отказ наступает ДО прогрева кандидата и до любой записи."""
    источник = tmp_path / "front"
    площадка = tmp_path / "srv" / "zona-02"
    данные = площадка / "data"
    снимок(источник, "zona-02", revision="старое", built_at="2026-10-08T03:15:24Z")
    снимок(данные, "zona-02", revision="новое", built_at="2026-10-10T11:46:13Z")
    (площадка / "data-candidate").mkdir(parents=True, exist_ok=True)

    class Площадка:
        data = данные
        data_candidate = площадка / "data-candidate"
        account = "zonafilm-cc"
        current = площадка / "current"
        app = площадка / "app"

    monkeypatch.setattr(privileged.Площадка, "из_реестра",
                        classmethod(lambda cls, site_id, path=None: Площадка()))
    monkeypatch.setattr(privileged, "контракт_данных",
                        lambda site_id, площадка=None, репозиторий=None: {
                            "delivered": privileged.СНИМОК,
                            "user_writable": ("site-data",),
                            "source": "проверка"})
    with pytest.raises(privileged.PrivilegedRefused) as отказ:
        privileged.stage_snapshot("zona-02", источник, dry_run=True)
    assert "СТАРЕЕ" in str(отказ.value)
    # Кандидат не собран: отказ не стоил витрине ничего.
    assert not any((площадка / "data-candidate").iterdir())
