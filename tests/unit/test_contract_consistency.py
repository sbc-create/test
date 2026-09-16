"""REQ-CONTRACT-CONSISTENCY: контракт содержимого не предлагает того, что запрещает контракт плеера.

Два перечня агрегаторов живут в разных местах: приоритет в контракте источника
и допустимые значения в сборщике элемента плеера. Пока они не сверяются,
расширение одного молча создаёт записи, которые второй отвергает — карточка
получает дескриптор и всё равно показывает «видео недоступно».

Так и произошло: imdb добавили в приоритет источника, каталог выдал 645
дескрипторов, а сборщик плеера отверг их по правилу PC-2. Дефект выглядел как
исправление.
"""
from pathlib import Path

import yaml

from factory.lords.player import ALLOWED_AGGREGATORS

REPO = Path(__file__).resolve().parents[2]
CONTENT = REPO / "knowledge" / "cdnvideohub" / "content-api.yaml"
PLAYER = REPO / "knowledge" / "cdnvideohub" / "PLAYER_CONTRACT.yaml"


def приоритет() -> list[str]:
    raw = yaml.safe_load(CONTENT.read_text(encoding="utf-8"))
    return list(raw["mapping"]["title"]["playback_aggregator_priority"])


def test_источник_не_предлагает_запрещённое_плеером():
    лишние = [a for a in приоритет() if a not in ALLOWED_AGGREGATORS]
    assert not лишние, (
        f"контракт источника предлагает агрегаторы {лишние}, которых нет в "
        f"ALLOWED_AGGREGATORS={list(ALLOWED_AGGREGATORS)}. Такие дескрипторы "
        "будут созданы и отвергнуты сборщиком плеера: карточка получит "
        "дескриптор и всё равно покажет «видео недоступно»."
    )


def test_imdb_запрещён_правилом_pc2():
    """PC-2 заморожен: снимать запрет вправе только владелец контракта."""
    правила = yaml.safe_load(PLAYER.read_text(encoding="utf-8")).get("rules") or []
    pc2 = next((r for r in правила if r.get("id") == "PC-2"), None)
    assert pc2 is not None, "правило PC-2 исчезло из контракта плеера"
    assert "IMDb" in pc2["rule"]
    assert "imdb" not in ALLOWED_AGGREGATORS
    assert "imdb" not in приоритет()


def test_каждый_допустимый_агрегатор_объявлен_в_источнике():
    """Обратная сторона: плеер не обязан уметь то, чего источник не даёт,
    но всё объявленное в приоритете обязано быть исполнимо."""
    for a in приоритет():
        assert a in ALLOWED_AGGREGATORS
