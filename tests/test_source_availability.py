"""Переходы реестра доступности: защита от дребезга, LKG, целостность файла."""

import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from factory.lords import source_availability as дост  # noqa: E402

ПРОФИЛЬ = "lords"
ИД = "0191511d-11fe-7daf-aebd-dfe84c6dbec7"
ИД2 = "019c047b-4f91-7b9b-aa1a-68c9fe926926"


def набл_доступно(подтверждено: bool = False) -> дост.Наблюдение:
    return дост.Наблюдение(http=200, items=3, stream=True, entity_ok=True,
                           media_ok=подтверждено)


def набл_204() -> дост.Наблюдение:
    return дост.Наблюдение(http=204, items=0, stream=False)


# --- классификация ответа --------------------------------------------------

@pytest.mark.parametrize("http,причина", [
    (401, "AUTH"), (403, "AUTH"), (429, "RATE_LIMITED"),
    (500, "PROVIDER_5XX"), (502, "PROVIDER_5XX"), (503, "PROVIDER_5XX"),
    (504, "PROVIDER_5XX"),
])
def test_коды_ошибок_дают_unknown(http, причина):
    статус, r = дост.наблюдаемый_статус(дост.Наблюдение(http=http))
    assert статус == дост.UNKNOWN
    assert r == причина


@pytest.mark.parametrize("причина", ["TIMEOUT", "DNS", "EMPTY_BODY", "MALFORMED_JSON"])
def test_транспортные_сбои_дают_unknown(причина):
    статус, r = дост.наблюдаемый_статус(дост.Наблюдение(http=None, reason=причина))
    assert статус == дост.UNKNOWN
    assert r == причина


def test_204_наблюдается_как_недоступно():
    статус, r = дост.наблюдаемый_статус(набл_204())
    assert статус == дост.SOURCE_UNAVAILABLE
    assert r == "NO_CONTENT_AT_PROVIDER"


def test_200_без_дорожки_не_карантин_и_не_доступно():
    """Тайтл у поставщика есть, дорожки нет. Это не 204 и карантином быть не может."""
    статус, r = дост.наблюдаемый_статус(дост.Наблюдение(http=200, items=0))
    assert статус == дост.UNKNOWN
    assert r == "NO_STREAM_IN_PLAYLIST"


def test_чужая_сущность_не_подтверждает():
    статус, r = дост.наблюдаемый_статус(
        дост.Наблюдение(http=200, items=5, stream=True, entity_ok=False))
    assert статус == дост.UNKNOWN
    assert r == "WRONG_ENTITY"


# --- защита от дребезга ----------------------------------------------------

def test_один_и_два_отказа_не_снимают_рабочую_карточку():
    р = дост.Реестр()
    р.обновить(ПРОФИЛЬ, ИД, набл_доступно())
    assert р.записи[дост.ключ(ПРОФИЛЬ, ИД)].effective_status == дост.AVAILABLE

    з = р.обновить(ПРОФИЛЬ, ИД, набл_204())
    assert з.effective_status == дост.AVAILABLE, "один 204 не повод снимать карточку"
    assert з.consecutive_204_count == 1

    з = р.обновить(ПРОФИЛЬ, ИД, набл_204())
    assert з.effective_status == дост.AVAILABLE, "два 204 — всё ещё не основание"
    assert з.consecutive_204_count == 2


def test_три_независимых_отказа_дают_карантин():
    р = дост.Реестр()
    р.обновить(ПРОФИЛЬ, ИД, набл_доступно())
    for _ in range(3):
        з = р.обновить(ПРОФИЛЬ, ИД, набл_204())
    assert з.consecutive_204_count == 3
    assert з.effective_status == дост.SOURCE_UNAVAILABLE
    assert р.карантин(ПРОФИЛЬ) == {ИД}


def test_unknown_сохраняет_последнее_достоверное_available():
    р = дост.Реестр()
    р.обновить(ПРОФИЛЬ, ИД, набл_доступно())
    з = р.обновить(ПРОФИЛЬ, ИД, дост.Наблюдение(http=503))
    assert з.effective_status == дост.AVAILABLE
    assert з.observed_status == дост.UNKNOWN


def test_unknown_сохраняет_карантин():
    р = дост.Реестр()
    for _ in range(3):
        р.обновить(ПРОФИЛЬ, ИД, набл_204())
    з = р.обновить(ПРОФИЛЬ, ИД, дост.Наблюдение(http=None, reason="TIMEOUT"))
    assert з.effective_status == дост.SOURCE_UNAVAILABLE


def test_unknown_не_обнуляет_счётчик_отказов():
    """Иначе обрыв связи посреди серии отказов откладывал бы карантин навсегда."""
    р = дост.Реестр()
    р.обновить(ПРОФИЛЬ, ИД, набл_204())
    р.обновить(ПРОФИЛЬ, ИД, набл_204())
    р.обновить(ПРОФИЛЬ, ИД, дост.Наблюдение(http=429))
    з = р.обновить(ПРОФИЛЬ, ИД, набл_204())
    assert з.consecutive_204_count == 3
    assert з.effective_status == дост.SOURCE_UNAVAILABLE


def test_новая_запись_с_unknown_не_публикуется_как_играющая():
    р = дост.Реестр()
    р.обновить(ПРОФИЛЬ, ИД, дост.Наблюдение(http=500))
    assert р.публикуемо(ПРОФИЛЬ, ИД) is False


def test_запись_без_истории_не_публикуется_как_играющая():
    assert дост.Реестр().публикуемо(ПРОФИЛЬ, ИД) is False


# --- возврат из карантина --------------------------------------------------

def test_возврат_требует_полной_цепочки():
    р = дост.Реестр()
    for _ in range(3):
        р.обновить(ПРОФИЛЬ, ИД, набл_204())
    # Ответ 200 с дорожкой, но без подтверждённого дескриптора — недостаточно.
    з = р.обновить(ПРОФИЛЬ, ИД, набл_доступно(подтверждено=False))
    assert з.effective_status == дост.SOURCE_UNAVAILABLE
    assert з.observed_status == дост.AVAILABLE

    з = р.обновить(ПРОФИЛЬ, ИД, набл_доступно(подтверждено=True))
    assert з.effective_status == дост.AVAILABLE
    assert з.last_confirmed_at is not None


def test_чужая_сущность_не_возвращает_из_карантина():
    р = дост.Реестр()
    for _ in range(3):
        р.обновить(ПРОФИЛЬ, ИД, набл_204())
    з = р.обновить(ПРОФИЛЬ, ИД, дост.Наблюдение(
        http=200, items=12, stream=True, entity_ok=False, media_ok=True))
    assert з.effective_status == дост.SOURCE_UNAVAILABLE


def test_совпадение_по_названию_не_является_подтверждением():
    """У модуля нет и не может быть входа для названия, года или slug.

    Проверяется не поведение, а отсутствие возможности: идентичность задана
    парой «профиль + идентификатор поставщика», и подсунуть вместо неё название
    просто некуда.
    """
    поля = set(дост.Наблюдение.__dataclass_fields__)
    assert поля.isdisjoint({"title", "name", "year", "slug", "kp", "imdb", "mal"})
    with pytest.raises(ValueError):
        дост.Реестр().обновить(ПРОФИЛЬ, "Рандеву с жизнью", набл_доступно(True))


def test_профили_не_делят_статус():
    """Один и тот же тайтл проверяется под двумя профилями независимо."""
    р = дост.Реестр()
    for _ in range(3):
        р.обновить("lords", ИД, набл_204())
    р.обновить("yami", ИД, набл_доступно())
    assert р.карантин("lords") == {ИД}
    assert р.карантин("yami") == set()


# --- файл состояния --------------------------------------------------------

def test_запись_и_чтение_кругом(tmp_path):
    путь = tmp_path / "source-availability.json"
    р = дост.Реестр()
    р.обновить(ПРОФИЛЬ, ИД, набл_доступно(True))
    дост.сохранить(путь, р)
    снова = дост.загрузить(путь)
    assert снова.записи[дост.ключ(ПРОФИЛЬ, ИД)].effective_status == дост.AVAILABLE
    assert json.loads(путь.read_text())["schema_version"] == дост.СХЕМА_ВЕРСИЯ


def test_поколение_меняется_при_каждой_записи(tmp_path):
    путь = tmp_path / "s.json"
    р = дост.Реестр()
    дост.сохранить(путь, р)
    первое = json.loads(путь.read_text())["generation_id"]
    дост.сохранить(путь, р)
    второе = json.loads(путь.read_text())["generation_id"]
    assert первое != второе


@pytest.mark.parametrize("мусор", [
    "", "{", "[]", '{"schema_version": 99, "generation_id": "x", "entries": {}}',
    '{"generation_id": "x", "entries": {}}',
    '{"schema_version": 1, "generation_id": "x"}',
])
def test_повреждённое_состояние_не_принимается(tmp_path, мусор):
    путь = tmp_path / "s.json"
    путь.write_text(мусор, encoding="utf-8")
    with pytest.raises(дост.ПовреждённоеСостояние):
        дост.загрузить(путь)


def test_повреждённый_файл_не_заменяет_целое_поколение(tmp_path):
    """Главное свойство: после неудачи на диске остаётся прежнее целое состояние."""
    путь = tmp_path / "s.json"
    р = дост.Реестр()
    for _ in range(3):
        р.обновить(ПРОФИЛЬ, ИД, набл_204())
    дост.сохранить(путь, р)
    целое = путь.read_text(encoding="utf-8")

    порченый = dict(р.как_словарь())
    порченый["entries"] = {"lords:не-идентификатор": {"provider_profile": "lords"}}
    with pytest.raises(дост.ПовреждённоеСостояние):
        дост.разобрать(json.dumps(порченый))
    assert путь.read_text(encoding="utf-8") == целое


def test_ключ_не_совпадающий_с_содержимым_отвергается():
    сырое = {
        "schema_version": дост.СХЕМА_ВЕРСИЯ, "generation_id": "g",
        "entries": {f"yami:{ИД}": {
            "provider_profile": "lords", "provider_uuid": ИД,
            "observed_status": дост.AVAILABLE, "effective_status": дост.AVAILABLE,
            "consecutive_204_count": 0}},
    }
    with pytest.raises(дост.ПовреждённоеСостояние):
        дост.разобрать(json.dumps(сырое))


def test_повторный_прогон_идемпотентен(tmp_path):
    путь = tmp_path / "s.json"
    наблюдения = [(ИД, набл_доступно(True)), (ИД2, набл_204())]
    первый = дост.применить_наблюдения(путь, ПРОФИЛЬ, наблюдения)
    снимок = {к: з.effective_status for к, з in первый.записи.items()}
    второй = дост.применить_наблюдения(путь, ПРОФИЛЬ, наблюдения)
    assert {к: з.effective_status for к, з in второй.записи.items()} == снимок


def test_восстановление_после_перезапуска(tmp_path):
    """Второй запуск продолжает накопленное, а не начинает с нуля."""
    путь = tmp_path / "s.json"
    дост.применить_наблюдения(путь, ПРОФИЛЬ, [(ИД, набл_204())])
    дост.применить_наблюдения(путь, ПРОФИЛЬ, [(ИД, набл_204())])
    реестр = дост.применить_наблюдения(путь, ПРОФИЛЬ, [(ИД, набл_204())])
    assert реестр.записи[дост.ключ(ПРОФИЛЬ, ИД)].effective_status == дост.SOURCE_UNAVAILABLE


def test_параллельные_задания_не_портят_артефакт(tmp_path):
    """Пятиминутная и суточная проверки пишут один файл и не должны его порвать."""
    путь = tmp_path / "s.json"
    дост.сохранить(путь, дост.Реестр())
    ошибки: list[BaseException] = []

    def работа(профиль: str, ид: str) -> None:
        try:
            for _ in range(15):
                дост.применить_наблюдения(путь, профиль, [(ид, набл_доступно(True))])
        except BaseException as e:  # noqa: BLE001 — падение нити должно быть видно
            ошибки.append(e)

    нити = [threading.Thread(target=работа, args=("lords", ИД)),
            threading.Thread(target=работа, args=("yami", ИД2))]
    for н in нити:
        н.start()
    for н in нити:
        н.join()

    assert not ошибки
    итог = дост.загрузить(путь)
    assert итог.записи[дост.ключ("lords", ИД)].effective_status == дост.AVAILABLE
    assert итог.записи[дост.ключ("yami", ИД2)].effective_status == дост.AVAILABLE
