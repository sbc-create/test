"""Релизная проверка Publisher ID читает тот же файл, что и всё остальное.

Смысл проверки — поймать расхождение между тремя местами, которые до сих пор
могли разойтись молча: профилем тенанта в git, боковым файлом на хосте и
ожиданием семейства. Пока сверять было нечем, расхождение обнаруживалось
единственным способом — чужим каталогом на живой витрине.

Проверяется, что команда:

* берёт ожидание из config/publisher-ids.yaml, а не из собственной копии;
* отвергает профиль семейства с чужим или снятым значением;
* отвергает два тенанта на одном домене;
* молчит про семейства вне политики — Lords и Yummy не её забота;
* завершается ненулевым кодом при расхождении, иначе проверку можно не заметить.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory import cli
from factory.site_engine import publisher_policy as политика

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _чистый_кэш():
    политика.сбросить_кэш()
    yield
    политика.сбросить_кэш()


@pytest.fixture
def стенд(tmp_path):
    """Копия репозитория с одним лишь тем, что читает проверка."""
    (tmp_path / "config" / "site-profiles").mkdir(parents=True)
    (tmp_path / "config" / "publisher-ids.yaml").write_text(
        (ROOT / "config" / "publisher-ids.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return tmp_path


def положить(корень: Path, site_id: str, **правки) -> None:
    профиль = {
        "schema_version": "1.0",
        "site_id": site_id,
        "domains": [f"{site_id}.example"],
    }
    профиль.update(правки)
    (корень / "config" / "site-profiles" / f"{site_id}.json").write_text(
        json.dumps(профиль, ensure_ascii=False), encoding="utf-8")


ИГРОК_ANIMEDIA = {
    "provider": "cdnvideohub", "credential_profile": "yami",
    "publisher_id_ref": "secret://cdnvideohub/yami/publisher-id",
    "source_mode": "provider-id",
}


def test_согласованный_набор_проходит(стенд, capsys):
    положить(стенд, "animedia-03", family="animedia",
             player={**ИГРОК_ANIMEDIA, "publisher_id": "10252"})
    assert cli.проверить_publisher_ids(стенд) == 0
    assert "OK" in capsys.readouterr().out


def test_чужое_значение_роняет_проверку(стенд, capsys):
    положить(стенд, "animedia-03", family="animedia",
             player={**ИГРОК_ANIMEDIA, "publisher_id": "10238"})
    assert cli.проверить_publisher_ids(стенд) == 1
    assert "10238" in capsys.readouterr().out


@pytest.mark.parametrize("снятый", ["10331", "10332", "10333"])
def test_снятое_значение_роняет_проверку(стенд, capsys, снятый):
    положить(стенд, "animedia-03", family="animedia",
             player={**ИГРОК_ANIMEDIA, "publisher_id": снятый})
    assert cli.проверить_publisher_ids(стенд) == 1
    assert снятый in capsys.readouterr().out


def test_два_тенанта_на_одном_домене_роняют_проверку(стенд, capsys):
    положить(стенд, "animedia-03", family="animedia", player=ИГРОК_ANIMEDIA,
             domains=["общий.example"])
    положить(стенд, "animedia-04", family="animedia", player=ИГРОК_ANIMEDIA,
             domains=["общий.example"])
    assert cli.проверить_publisher_ids(стенд) == 1
    assert "общий.example" in capsys.readouterr().out


def test_семейства_вне_политики_не_упоминаются(стенд, capsys):
    положить(стенд, "lords-09", player={
        "provider": "cdnvideohub", "credential_profile": "lords",
        "publisher_id_ref": "secret://cdnvideohub/lords/lords-01/publisher-id",
        "publisher_id": "10238", "source_mode": "provider-id"})
    положить(стенд, "yummyani-09", family="yummy", player={
        "provider": "cdnvideohub", "credential_profile": "yami",
        "publisher_id_ref": "secret://cdnvideohub/yami/publisher-id",
        "publisher_id": "99999", "source_mode": "provider-id"})
    assert cli.проверить_publisher_ids(стенд) == 0
    вывод = capsys.readouterr().out
    assert "lords-09" not in вывод and "yummyani-09" not in вывод


def test_действующий_репозиторий_согласован(capsys):
    """Живые профили фабрики не расходятся с политикой."""
    assert cli.проверить_publisher_ids(ROOT) == 0


def test_семейство_ссылается_на_существующий_портфель_secret_hub(стенд, capsys):
    """Пара семейства обязана существовать в Secret Hub.

    Семейство, указывающее на несуществующий портфель, ломается не здесь, а на
    хосте в момент подключения плеера — сообщением про отсутствующий файл, по
    которому причину не видно.
    """
    (стенд / "config" / "publisher-ids.yaml").write_text(
        "schema_version: 1\n"
        "families:\n"
        "  animedia:\n"
        "    publisher_id: \"10252\"\n"
        "    credential_profile: несуществующий\n"
        "retired: []\n",
        encoding="utf-8",
    )
    (стенд / "config" / "secret-hub.json").write_text(
        json.dumps({"portfolios": [{"id": "yami", "enabled": True}]}), encoding="utf-8")
    положить(стенд, "animedia-03", family="animedia", player=ИГРОК_ANIMEDIA)
    assert cli.проверить_publisher_ids(стенд) == 1
    assert "несуществующий" in capsys.readouterr().out


def test_действующие_семейства_ссылаются_на_живые_портфели(capsys):
    """yami и lords обязаны существовать в config/secret-hub.json репозитория."""
    портфели = {
        p["id"] for p in json.loads(
            (ROOT / "config" / "secret-hub.json").read_text(encoding="utf-8"))["portfolios"]
    }
    for имя in политика.семейства(root=ROOT):
        описание = политика.загрузить(root=ROOT).семейства[имя]
        assert описание.credential_profile in портфели, имя


def test_отчёт_называет_источник(стенд, capsys):
    положить(стенд, "animedia-03", family="animedia", player=ИГРОК_ANIMEDIA)
    cli.проверить_publisher_ids(стенд)
    assert политика.POLICY_REF in capsys.readouterr().out
