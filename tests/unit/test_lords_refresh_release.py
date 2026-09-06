"""REQ-CANARY-PERSISTENCE: выложенный шаблон переживает обновление каталога.

Инцидент. На `lords-02` канареечный релиз был переключён и работал: происхождение
`cdnvideohub-live`, операция в аудите, новый шаблон на витрине. Через сорок
восемь минут очередной запуск таймера обновления каталога заменил публичный
`current` релизом, собранным из развёрнутого checkout: происхождение
`fixture/test`, отпечаток артефакта отсутствует, версия шаблона равна отпечатку
пустого массива. Изменения канарейки исчезли с публичной витрины, а само
переключение считалось успешным.

Отсюда три утверждения, каждое проверяется отдельно:

1. обновление каталога отрисовывает витрину **артефактом текущего релиза**, а не
   тем, что лежит в рабочем дереве;
2. после обновления шаблонная часть манифеста совпадает до последнего поля, а
   содержательная — обязана измениться;
3. релиз, нарушающий инвариант, до `current` не доходит.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from factory.lords import refresh_release as рр
from factory.lords import release_manifest as рм
from factory.lords import template_artifact as та

ОТПЕЧАТОК_ПУСТОГО = рм.ПУСТОЙ_МАССИВ


def _архив(каталог: Path, имя: str, содержимое: dict[str, str]) -> tuple[Path, str]:
    """Настоящий tar.gz с содержимым — артефакт проверяется распаковкой."""
    исходники = каталог / f"src-{имя}"
    (исходники / "factory" / "lords").mkdir(parents=True, exist_ok=True)
    for относительный, текст in содержимое.items():
        путь = исходники / относительный
        путь.parent.mkdir(parents=True, exist_ok=True)
        путь.write_text(текст, encoding="utf-8")
    архив = каталог / f"{имя}.tar.gz"
    subprocess.run(["tar", "-czf", str(архив), "-C", str(исходники), "."], check=True)
    return архив, рм.отпечаток_файла(архив)


def _манифест(**поля) -> dict:
    основа = {
        "tenant_id": "lords-02",
        "domain": "lordserial33.biz",
        "theme": "lords_dark",
        "template_package_ref": "artifacts/lords/bundle/lords-02.tar",
        "template_artifact_ref": "templates/v3.tar.gz",
        "template_digest": "a" * 64,
        "renderer_revision": "b" * 40,
        "content_snapshot_id": "snap-1",
        "content_source": "cdnvideohub-live",
        "content_count": 4316,
        "created_at": "2026-09-06T09:00:00Z",
        "created_by": "тест",
        "previous_release": None,
        "rollback_target": None,
        "release_reason": "canary",
        "production_authorized": True,
    }
    основа.update(поля)
    return основа


@pytest.fixture()
def стенд(tmp_path):
    """Витрина с релизом A и закреплённым артефактом шаблона A."""
    рантайм = tmp_path / "runtime" / "lords-02"
    (рантайм / "releases").mkdir(parents=True)
    артефакты = tmp_path / "artifacts"
    (артефакты / "templates").mkdir(parents=True)

    архив_a, отпечаток_a = _архив(tmp_path, "A", {
        "factory/lords/renderer.py": "ШАБЛОН = 'A'\n"})
    (архив_a).replace(артефакты / "templates" / "A.tar.gz")

    релиз = рантайм / "releases" / "aaaa1111"
    (релиз / "site").mkdir(parents=True)
    (релиз / "site" / "index.html").write_text("<h1>A</h1>", encoding="utf-8")
    манифест = _манифест(template_artifact_ref="templates/A.tar.gz",
                         template_digest=отпечаток_a)
    (релиз / рр.МАНИФЕСТ).write_text(json.dumps(манифест, ensure_ascii=False),
                                     encoding="utf-8")
    (рантайм / "current").symlink_to(релиз)
    return {"runtime": рантайм, "artifacts": артефакты, "releaseA": релиз,
            "digestA": отпечаток_a, "tmp": tmp_path}


# --- ЦИКЛ 1: воспроизведение инцидента --------------------------------------

def test_обновление_берёт_шаблон_из_релиза_а_не_из_рабочего_дерева(стенд):
    """Канарейка B выложена. Обновление обязано отрисовывать B, а не A."""
    архив_b, отпечаток_b = _архив(стенд["tmp"], "B", {
        "factory/lords/renderer.py": "ШАБЛОН = 'B'\n"})
    архив_b.replace(стенд["artifacts"] / "templates" / "B.tar.gz")

    релиз_b = стенд["runtime"] / "releases" / "bbbb2222"
    (релиз_b / "site").mkdir(parents=True)
    манифест_b = _манифест(template_artifact_ref="templates/B.tar.gz",
                           template_digest=отпечаток_b,
                           previous_release="aaaa1111", rollback_target="aaaa1111",
                           content_snapshot_id="snap-2")
    (релиз_b / рр.МАНИФЕСТ).write_text(json.dumps(манифест_b, ensure_ascii=False),
                                       encoding="utf-8")
    with рр.замок(стенд["runtime"]):
        рр.переключить(стенд["runtime"], релиз_b, expected_current="aaaa1111",
                       reason="canary", actor="тест")

    план = рр.план(стенд["runtime"], artifact_root=стенд["artifacts"])

    assert план["templateDigest"] == отпечаток_b, "обновление взяло шаблон прежнего релиза"
    отрисовщик = Path(план["templateRoot"]) / "factory" / "lords" / "renderer.py"
    assert отрисовщик.read_text(encoding="utf-8").strip() == "ШАБЛОН = 'B'", (
        "отрисовка пошла бы шаблоном A: ровно так канарейка и исчезала"
    )


# --- ЦИКЛ 3: шаблон сохраняется, каталог обновляется ------------------------

def test_после_обновления_шаблон_тот_же_а_каталог_другой(стенд):
    план = рр.план(стенд["runtime"], artifact_root=стенд["artifacts"])
    цель = стенд["runtime"] / "releases" / "cccc3333"
    (цель / "site").mkdir(parents=True)
    time.sleep(1.05)  # время создания обязано отличаться
    новый = рр.записать_манифест(цель, план, content_snapshot_id="snap-99",
                                 content_count=4400, created_by="тест",
                                 artifact_root=стенд["artifacts"])

    assert рм.шаблон_сохранён(план["manifest"], новый) == []
    assert рм.каталог_обновлён(план["manifest"], новый) == []
    assert новый["content_count"] == 4400
    assert новый["previous_release"] == "aaaa1111"
    assert новый["rollback_target"] == "aaaa1111"


def test_обновление_не_вправе_подменить_шаблон(стенд):
    план = рр.план(стенд["runtime"], artifact_root=стенд["artifacts"])
    план["manifest"] = dict(план["manifest"])
    цель = стенд["runtime"] / "releases" / "dddd4444"
    (цель / "site").mkdir(parents=True)
    испорченный = dict(план["manifest"], template_digest="c" * 64)
    план_c_подменой = dict(план, manifest=испорченный)
    # Артефакт под новый отпечаток не существует — подмена обязана быть замечена
    # до записи, а не после переключения.
    with pytest.raises(рр.RefreshRefused) as отказ:
        рр.записать_манифест(цель, план_c_подменой, content_snapshot_id="snap-3",
                             content_count=10, created_by="тест",
                             artifact_root=стенд["artifacts"])
    assert "артефакт" in str(отказ.value) or "инвариант" in str(отказ.value)


# --- ЦИКЛ 6: отрицательные проверки -----------------------------------------

@pytest.mark.parametrize("поле,значение,почему", [
    ("template_digest", "", "пустой отпечаток"),
    ("template_digest", ОТПЕЧАТОК_ПУСТОГО, "отпечаток пустого массива"),
    ("content_source", "fixture/test", "происхождение fixture/test"),
    ("production_authorized", False, "витрина не разрешена к выкладке"),
    ("content_count", 0, "нулевой каталог"),
])
def test_релиз_с_нарушением_не_принимается(поле, значение, почему):
    беды = рм.нарушения(_манифест(**{поле: значение}))
    assert беды, f"нарушение пропущено: {почему}"


def test_нарушения_называются_все_сразу():
    беды = рм.нарушения(_манифест(template_digest="", content_source="fixture/test",
                                  production_authorized=False))
    assert len(беды) >= 3, беды


def test_план_отказывает_на_испорченном_текущем_релизе(стенд):
    манифест = json.loads((стенд["releaseA"] / рр.МАНИФЕСТ).read_text(encoding="utf-8"))
    манифест["content_source"] = "fixture/test"
    (стенд["releaseA"] / рр.МАНИФЕСТ).write_text(json.dumps(манифест), encoding="utf-8")
    with pytest.raises(рр.RefreshRefused) as отказ:
        рр.план(стенд["runtime"], artifact_root=стенд["artifacts"])
    assert "fixture" in str(отказ.value)


def test_подменённый_артефакт_замечен_распаковкой(стенд):
    архив = стенд["artifacts"] / "templates" / "A.tar.gz"
    архив.write_bytes(архив.read_bytes() + b"\0tampered")
    with pytest.raises(рр.RefreshRefused) as отказ:
        рр.план(стенд["runtime"], artifact_root=стенд["artifacts"])
    assert "артефакт" in str(отказ.value)


# --- ЦИКЛ 4: конкуренция и атомарность --------------------------------------

def test_переключение_отказано_при_чужом_изменении_состояния(стенд):
    чужой = стенд["runtime"] / "releases" / "eeee5555"
    (чужой / "site").mkdir(parents=True)
    (чужой / рр.МАНИФЕСТ).write_text(json.dumps(_манифест()), encoding="utf-8")
    (стенд["runtime"] / "current").unlink()
    (стенд["runtime"] / "current").symlink_to(чужой)

    цель = стенд["runtime"] / "releases" / "ffff6666"
    (цель / "site").mkdir(parents=True)
    (цель / рр.МАНИФЕСТ).write_text(json.dumps(_манифест()), encoding="utf-8")
    with pytest.raises(рр.RefreshRefused) as отказ:
        рр.переключить(стенд["runtime"], цель, expected_current="aaaa1111",
                       reason="refresh", actor="тест")
    assert "состояние изменилось" in str(отказ.value)
    assert (стенд["runtime"] / "current").resolve().name == "eeee5555", "current затёрт"


def test_повтор_той_же_операции_ничего_не_делает(стенд):
    итог = рр.переключить(стенд["runtime"], стенд["releaseA"],
                          expected_current="aaaa1111", reason="повтор", actor="тест")
    assert итог["switched"] is False and итог["idempotent"] is True


def test_замок_держится_одним_владельцем(стенд):
    with рр.замок(стенд["runtime"]):
        with pytest.raises(рр.RefreshRefused) as отказ:
            with рр.замок(стенд["runtime"], timeout=0.5):
                pass
    assert "занята" in str(отказ.value)


def test_переключение_без_манифеста_отказано(стенд):
    голый = стенд["runtime"] / "releases" / "9999zzzz"
    голый.mkdir(parents=True)
    with pytest.raises(рр.RefreshRefused) as отказ:
        рр.переключить(стенд["runtime"], голый, expected_current="aaaa1111",
                       reason="refresh", actor="тест")
    assert "манифест" in str(отказ.value)
    assert (стенд["runtime"] / "current").resolve().name == "aaaa1111"


# --- ЦИКЛ 5: диагностика ----------------------------------------------------

def test_переключение_записывается_до_и_после(стенд):
    цель = стенд["runtime"] / "releases" / "7777aaaa"
    (цель / "site").mkdir(parents=True)
    (цель / рр.МАНИФЕСТ).write_text(json.dumps(_манифест(previous_release="aaaa1111")),
                                    encoding="utf-8")
    рр.переключить(стенд["runtime"], цель, expected_current="aaaa1111",
                   reason="canary", actor="тест")
    записи = [json.loads(с) for с in
              (стенд["runtime"] / рр.ЖУРНАЛ).read_text(encoding="utf-8").splitlines()]
    последняя = записи[-1]
    assert последняя["from"] == "aaaa1111" and последняя["to"] == "7777aaaa"
    assert последняя["tenant"] == "lords-02"
    assert последняя["pid"] == os.getpid() and последняя["uid"] == os.getuid()
    assert "reason" in последняя and "at" in последняя
    # Секретов в журнале нет: он читается людьми и попадает в отчёты.
    текст = (стенд["runtime"] / рр.ЖУРНАЛ).read_text(encoding="utf-8").lower()
    for запрет in ("token", "password", "publisher", "secret"):
        assert запрет not in текст


def test_артефакт_распаковывается_один_раз(стенд):
    план1 = рр.план(стенд["runtime"], artifact_root=стенд["artifacts"])
    метка = Path(план1["templateRoot"]) / "маркер"
    метка.write_text("след", encoding="utf-8")
    план2 = рр.план(стенд["runtime"], artifact_root=стенд["artifacts"])
    assert план1["templateRoot"] == план2["templateRoot"]
    assert метка.is_file(), "артефакт распакован заново — цикл платил бы за это каждый раз"


def test_отпечаток_дерева_замечает_правку(стенд):
    план = рр.план(стенд["runtime"], artifact_root=стенд["artifacts"])
    было = та.отпечаток_дерева(план["templateRoot"], подкаталоги=("factory",))
    (Path(план["templateRoot"]) / "factory" / "lords" / "renderer.py").write_text(
        "ШАБЛОН = 'подменён'\n", encoding="utf-8")
    стало = та.отпечаток_дерева(план["templateRoot"], подкаталоги=("factory",))
    assert было != стало
