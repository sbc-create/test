"""Доставка контента в ячейку: только своё, только целиком, только своему.

Разрыв, который она закрывает: активация копирует снимок каталога один раз, а
производители продолжают писать в общий каталог. Витрина замирает на версии
момента активации, и выглядит это не как поломка, а как сайт, который перестал
пополняться — замечают через сутки.

Проверяется поведение на настоящей файловой системе: временный каталог вместо
`/srv`, настоящие файлы, настоящая замена.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import delivery, registry  # noqa: E402


def _ячейка(site_id: str, domain: str, repo_path: str | None,
            *, remote: str | None = "") -> registry.Cell:
    адрес = (remote if remote else
             f"https://github.com/sbc-create/site-{domain.replace('.', '-')}")
    return registry.Cell(
        site_id=site_id, domain=domain, aliases=(),
        repo={"kind": "remote", "path": repo_path, "remote": адрес},
        template={"template_id": "zona-nova"}, pins={}, deploy_target={},
        publisher={}, data={})


@pytest.fixture()
def контур(tmp_path: Path, monkeypatch):
    """Общий каталог производителя и хранилища двух соседних витрин."""
    общий = tmp_path / "frontend"
    общий.mkdir()
    (общий / "zona-01-catalog.json").write_text('{"v": 2}', encoding="utf-8")
    (общий / "zona-01-details.json").write_text('{"d": 2}', encoding="utf-8")
    (общий / "zona-02-catalog.json").write_text('{"СОСЕД": true}', encoding="utf-8")

    свой = tmp_path / "srv" / "zonafilm-space" / "data"
    свой.mkdir(parents=True)
    (свой / "zona-01-catalog.json").write_text('{"v": 1}', encoding="utf-8")
    сосед = tmp_path / "srv" / "zonafilm-cc" / "data"
    сосед.mkdir(parents=True)
    (сосед / "zona-02-catalog.json").write_text('{"СОСЕД": true}', encoding="utf-8")

    monkeypatch.setattr(delivery, "каталог_данных", lambda cell: свой)
    return общий, свой, сосед


def test_обновляет_только_изменившееся(контур, monkeypatch):
    общий, свой, сосед = контур
    monkeypatch.setattr(registry, "resolve", lambda s: _ячейка("zona-01", "zonafilm.space", None))

    итог = delivery.доставить("zona-01", общий=общий)

    assert "zona-01-catalog.json" in итог.delivered
    assert json.loads((свой / "zona-01-catalog.json").read_text()) == {"v": 2}
    # Файл, которого у витрины ещё не было, тоже доставляется.
    assert (свой / "zona-01-details.json").is_file()

    # Повтор ничего не переписывает: доставка идемпотентна, и «доставлено»
    # означает именно изменение, а не факт запуска.
    повтор = delivery.доставить("zona-01", общий=общий)
    assert повтор.delivered == []
    assert sorted(повтор.unchanged) == ["zona-01-catalog.json", "zona-01-details.json"]


def test_файл_соседа_недостижим(контур, monkeypatch):
    """Перечень строится по site_id, поэтому чужой файл в него не попадает."""
    общий, свой, сосед = контур
    monkeypatch.setattr(registry, "resolve", lambda s: _ячейка("zona-01", "zonafilm.space", None))
    до = (сосед / "zona-02-catalog.json").read_bytes()

    delivery.доставить("zona-01", общий=общий)

    assert (сосед / "zona-02-catalog.json").read_bytes() == до
    assert not (свой / "zona-02-catalog.json").exists()


def test_неактивированная_ячейка_пропускается(контур, monkeypatch):
    """Отсутствие хранилища — нормальное состояние до переключения, не ошибка."""
    общий, _, _ = контур
    monkeypatch.setattr(registry, "resolve", lambda s: _ячейка("zona-01", "zonafilm.space", None))
    monkeypatch.setattr(delivery, "каталог_данных", lambda cell: None)

    итог = delivery.доставить("zona-01", общий=общий)

    assert итог.delivered == []
    assert "не активирована" in итог.skipped_reason


def test_сухой_прогон_ничего_не_пишет(контур, monkeypatch):
    общий, свой, _ = контур
    monkeypatch.setattr(registry, "resolve", lambda s: _ячейка("zona-01", "zonafilm.space", None))
    до = {p.name: p.read_bytes() for p in свой.iterdir()}

    итог = delivery.доставить("zona-01", общий=общий, dry_run=True)

    assert итог.delivered, "сухой прогон обязан показать, что именно изменилось бы"
    assert {p.name: p.read_bytes() for p in свой.iterdir()} == до


def test_сайт_без_своего_репозитория_не_обслуживается(контур, monkeypatch):
    """Доставка — часть контура ячейки; невыделенному сайту она не адресована."""
    общий, _, _ = контур
    невыделенный = registry.Cell(
        site_id="zona-01", domain="zonafilm.space", aliases=(), repo={},
        template={"template_id": "zona-nova"}, pins={}, deploy_target={},
        publisher={}, data={})
    monkeypatch.setattr(registry, "resolve", lambda s: невыделенный)

    with pytest.raises(registry.OwnRepositoryMissing):
        delivery.доставить("zona-01", общий=общий)


def test_перечень_берётся_из_конфигурации_ячейки(tmp_path: Path):
    """Витрина получает то, что читает, а не то, что когда-то читала.

    Манифест шаблона переехал в репозиторий; доставлять его в хранилище значило
    бы менять данные живого сайта без всякой причины.
    """
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "config" / "site.json").write_text(json.dumps({
        "site_id": "zona-01", "domain": "zonafilm.space",
        "environment": {
            "LORDS_CATALOG": "<data>/zona-01-catalog.json",
            "LORDS_TEMPLATE_MANIFEST": "<app>/config/template-manifest.json",
            "LORDS_LEGACY_ROOT": "<data>/site",
            "LORDS_SITE_NAME": "Zona",
        },
    }, ensure_ascii=False), encoding="utf-8")

    имена = delivery.что_читает(_ячейка("zona-01", "zonafilm.space", str(repo)))

    assert имена == ["zona-01-catalog.json"]
    # `<app>` — не хранилище; `<data>/site` — каталог, а не файл.
    assert all("template-manifest" not in н for н in имена)


def test_запись_идёт_рядом_с_назначением(контур, monkeypatch):
    """os.replace атомарен лишь в пределах файловой системы назначения.

    Временный файл в /tmp дал бы `Invalid cross-device link` у службы с
    PrivateTmp — то есть доставка падала бы только в production.
    """
    общий, свой, _ = контур
    monkeypatch.setattr(registry, "resolve", lambda s: _ячейка("zona-01", "zonafilm.space", None))
    каталоги = []
    настоящий = delivery.tempfile.NamedTemporaryFile

    def подмена(*args, **kwargs):
        каталоги.append(kwargs.get("dir"))
        return настоящий(*args, **kwargs)

    monkeypatch.setattr(delivery.tempfile, "NamedTemporaryFile", подмена)
    delivery.доставить("zona-01", общий=общий)

    assert каталоги and all(Path(d) == свой for d in каталоги)
    assert not [p for p in свой.iterdir() if p.name.startswith("tmp")], "временный файл остался"


def test_права_на_доставленный_файл_читаемы(контур, monkeypatch):
    общий, свой, _ = контур
    monkeypatch.setattr(registry, "resolve", lambda s: _ячейка("zona-01", "zonafilm.space", None))
    delivery.доставить("zona-01", общий=общий)
    режим = os.stat(свой / "zona-01-details.json").st_mode & 0o777
    assert режим == 0o644
