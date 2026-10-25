"""Активный список домéнов и охват регулярного цикла.

Повод измеренный, 2026-10-22: юниты цикла работают в другой рабочей копии, и
реестр ячеек ТОЙ копии содержал 25 ячеек без восьми витрин K2. Восемь живых
сайтов не получали ни одной регулярной проверки, а `regular status` при этом
показывал «таймеры включены, срабатывали сегодня». Поэтому здесь закреплены
два разных требования: список активных домéнов полон и согласован с реестром,
и мера охвата отличает «цикл о домене не знает» от «объявил, но не проверил».
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

jsonschema = pytest.importorskip("jsonschema")

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СПИСОК = КОРЕНЬ / "config" / "active-domains.json"
СХЕМА = КОРЕНЬ / "schemas" / "active-domains.schema.json"
ЯЧЕЙКИ = КОРЕНЬ / "config" / "site-cells.json"

_сп = importlib.util.spec_from_file_location(
    "cycle_coverage", КОРЕНЬ / "automation" / "local" / "cycle-coverage.py")
мера = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(мера)

#: Домены из задания владельца 2026-10-22, §2 — переписаны поимённо. Это
#: контрольный список: если файл разойдётся с заданием, проверка упадёт.
ЗАДАНИЕ = {
    "yummy": ["yummyani.site", "yummyani7.site", "yummyani7.info",
              "yummyani.org", "yummyani.biz"],
    "animedia": ["animedia.icu", "animedia.space"],
    "animego": ["animeg0.site", "an1meg0.site", "an1mego.site"],
    "lords": ["lordserials22.info", "1lordserials1.online",
              "lordfilm47.space", "lordserial33.biz"],
    "zona": ["zonafilm12.site", "zonafilm.space", "zonafilm.cc"],
    "k2": ["lordfilm.group", "lordfilm.spb.ru", "lordfilm.msk.ru",
           "lordserial.su", "lordserial.group", "lordserial.spb.ru",
           "lordserial.msk.ru", "lordserial.net.ru"],
}
#: Домены, ВЫВЕДЕННЫЕ владельцем 2026-10-25 из активной работы. Задание 22.10
#: называло их активными, распоряжение 25.10 — вывело: animedia.space,
#: lordfilm47.space, lordserials22.site и lordserials22.space. Поэтому
#: контрольный список активных равен заданию 22.10 МИНУС эти четыре, а не
#: заданию 22.10 целиком: иначе проверка требовала бы обратного решению
#: владельца. lordserials22.info в вывод НЕ входит и остаётся активным.
ВЫВЕДЕНЫ_25_10 = ["animedia.space", "lordfilm47.space",
                  "lordserials22.site", "lordserials22.space"]
ЖДУТ_ЗАМЕНЫ = ["lordserials22.site", "lordserials22.space",
               "lordserial101.site", "lordfilm077.site",
               "animedia.space", "lordfilm47.space"]


@pytest.fixture(scope="module")
def список() -> dict:
    return json.loads(СПИСОК.read_text(encoding="utf-8"))


# --- сам список -----------------------------------------------------------

def test_список_проходит_свою_схему(список):
    схема = json.loads(СХЕМА.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(схема)
    jsonschema.Draft7Validator(схема).validate(список)


def test_состав_совпадает_с_заданием_владельца(список):
    """Список — не мнение агента: он сверяется с заданием поимённо."""
    в_файле = {з["domain"] for з in список["domains"]}
    в_задании = {д for дом in ЗАДАНИЕ.values() for д in дом} - set(ВЫВЕДЕНЫ_25_10)
    assert в_файле == в_задании, {
        "лишние": sorted(в_файле - в_задании),
        "пропущенные": sorted(в_задании - в_файле)}


def test_семейство_каждого_домена_то_же_что_в_задании(список):
    ожидание = {д: семья for семья, дом in ЗАДАНИЕ.items() for д in дом}
    расхождения = {з["domain"]: (з["family"], ожидание[з["domain"]])
                   for з in список["domains"]
                   if з["family"] != ожидание[з["domain"]]}
    assert not расхождения, расхождения


def test_выведенные_домены_есть_в_паспортах_с_датой(список):
    """Вывод — решение владельца, и он обязан быть записан в реестре ячеек.

    Проверка добавлена 25.10: без неё «домена нет в активных» неотличимо от
    «домен потеряли». Дата и основание читаются из паспорта.
    """
    from factory.cell import registry

    выведены = registry.выведенные_домены()
    for домен in ВЫВЕДЕНЫ_25_10:
        assert домен in выведены, f"{домен} нет в активных, но и не выведен в паспорте"
        блок = registry.resolve(домен).withdrawal
        assert блок.get("at", "").startswith("2026-10-25"), домен
        assert блок.get("authority"), домен
    assert "lordserials22.info" not in выведены


def test_ожидающие_замены_не_попали_в_активные(список):
    """Домены, ждущие замены: продвижение им не назначается."""
    активные = {з["domain"] for з in список["domains"]}
    пересечение = активные & set(ЖДУТ_ЗАМЕНЫ)
    assert not пересечение, пересечение
    объявлены = {з["domain"] for з in список["awaiting_replacement"]}
    assert объявлены == set(ЖДУТ_ЗАМЕНЫ)


def test_каждый_активный_домен_есть_в_реестре_ячеек(список):
    """Домен без ячейки нельзя ни выпустить, ни проверить."""
    реестр = json.loads(ЯЧЕЙКИ.read_text(encoding="utf-8"))
    по_домену = {з["domain"]: з["site_id"] for з in реестр["cells"]}
    нет = [з["domain"] for з in список["domains"] if з["domain"] not in по_домену]
    assert not нет, нет
    расхождения = {з["domain"]: (з["site_id"], по_домену[з["domain"]])
                   for з in список["domains"]
                   if по_домену[з["domain"]] != з["site_id"]}
    assert not расхождения, расхождения


def test_у_каждого_домена_своя_очередь_и_свой_паспорт(список):
    очереди = [з["queue"] for з in список["domains"]]
    паспорта = [з["passport"] for з in список["domains"]]
    assert len(set(очереди)) == len(очереди), "очередь делится между доменами"
    assert len(set(паспорта)) == len(паспорта), "паспорт делится между доменами"
    for з in список["domains"]:
        assert з["domain"] in з["queue"], з
        assert з["domain"] in з["passport"], з


def test_у_каждого_семейства_есть_файл_знаний(список):
    семьи = set(список["families"])
    у_домéнов = {з["family"] for з in список["domains"]}
    assert у_домéнов <= семьи, у_домéнов - семьи
    for имя, с in список["families"].items():
        assert с["knowledge"].endswith(f"{имя}.md"), (имя, с["knowledge"])


def test_у_общих_составляющих_назван_владелец(список):
    """Общий дефект, правленный в случайной копии, — измеренная причина вреда."""
    for имя, с in список["shared_components"].items():
        if имя == "note":
            continue
        assert с.get("owner"), имя


# --- мера охвата: чистые функции -----------------------------------------

def test_домен_которого_цикл_не_объявил_это_вне_цикла():
    assert мера.исход_домена("a.test", set(), set()) == мера.ВНЕ_ЦИКЛА


def test_объявленный_но_непроверенный_это_другой_исход():
    """Исчерпанный бюджет запросов и отсутствие в реестре — разные дефекты."""
    assert мера.исход_домена("a.test", {"a.test"}, set()) == мера.НЕ_ПРОВЕРЕН


def test_объявлен_и_проверен_это_полно():
    assert мера.исход_домена("a.test", {"a.test"}, {"a.test"}) == мера.ПОЛНО


def test_вне_цикла_весомее_непроверенного():
    """Называется более дорогой дефект: о домене не знают вовсе."""
    assert мера.свести({"a": мера.ВНЕ_ЦИКЛА,
                        "b": мера.НЕ_ПРОВЕРЕН}) == мера.ВНЕ_ЦИКЛА


def test_пустые_исходы_это_не_измерено():
    assert мера.свести({}) == мера.НЕ_ИЗМЕРЕНО


def test_всё_полно_только_когда_все_полны():
    assert мера.свести({"a": мера.ПОЛНО, "b": мера.ПОЛНО}) == мера.ПОЛНО


# --- мера охвата: чтение переиспользованной проверки ----------------------

def прогон(tmp_path, *, availability=None, check=None, discover=("a.test",)):
    п = tmp_path / "runs" / "daily-2026-10-22"
    п.mkdir(parents=True)
    (п / "discover.json").write_text(
        json.dumps([{"domain": д} for д in discover]), encoding="utf-8")
    if availability is not None:
        (п / "availability.json").write_text(
            json.dumps([{"domain": д} for д in availability]),
            encoding="utf-8")
    if check is not None:
        (п / "check.json").write_text(json.dumps(check), encoding="utf-8")
    return п


def test_переиспользованная_проверка_читается_из_check(tmp_path):
    """Суточный прогон доступность не повторяет — он её переиспользует.

    Первая редакция меры читала только `availability.json`, не находила его в
    суточном прогоне и объявляла НЕ ПРОВЕРЕННЫМИ все 17 домéнов: ложная
    находка на исправном цикле.
    """
    п = прогон(tmp_path, check={"reused": True,
                                "availability": [{"domain": "a.test"}]})
    домены, источник = мера.проверенные_домены(п)
    assert домены == {"a.test"}
    assert "переиспользованная" in источник


def test_прямой_файл_проверки_имеет_приоритет(tmp_path):
    п = прогон(tmp_path, availability=["a.test", "b.test"],
               check={"reused": True, "availability": [{"domain": "a.test"}]})
    домены, источник = мера.проверенные_домены(п)
    assert домены == {"a.test", "b.test"}
    assert источник == "availability"


def test_прогон_без_проверки_честно_пуст(tmp_path):
    п = прогон(tmp_path)
    домены, источник = мера.проверенные_домены(п)
    assert домены == set()
    assert источник == "не найдено"


def test_битый_файл_проверки_не_роняет_меру(tmp_path):
    п = прогон(tmp_path)
    (п / "check.json").write_text("{не json", encoding="utf-8")
    домены, источник = мера.проверенные_домены(п)
    assert домены == set()


def test_мера_находит_восемь_K2_вне_цикла_на_стенде(tmp_path):
    """Сквозная проверка меры на подменённом состоянии цикла.

    Воспроизводится именно измеренное положение: цикл объявил 21 домен без
    витрин K2 и проверил их же.
    """
    # Выведенные 25.10 домены попадают сюда ОДИН раз — через ЖДУТ_ЗАМЕНЫ:
    # в задании 22.10 они ещё активны, и без вычитания список удваивался бы.
    активные_не_k2 = [д for семья, дом in ЗАДАНИЕ.items() if семья != "k2"
                      for д in дом if д not in ВЫВЕДЕНЫ_25_10]
    объявлены = активные_не_k2 + ЖДУТ_ЗАМЕНЫ
    прогон(tmp_path, check={"reused": True,
                            "availability": [{"domain": д} for д in объявлены]},
           discover=объявлены)
    итоги = мера.проверить(корень_цикла=tmp_path)
    assert итоги["исход"] == мера.ВНЕ_ЦИКЛА
    assert итоги["вне_цикла"] == sorted(ЗАДАНИЕ["k2"])
    assert итоги["по_семьям"] == {"k2": sorted(ЗАДАНИЕ["k2"])}
    assert итоги["лишние_в_цикле"] == sorted(ЖДУТ_ЗАМЕНЫ)
    assert итоги["проверено_циклом"] == len(объявлены)


def test_полный_охват_даёт_полно(tmp_path):
    """Граница с другой стороны: мера не кричит на исправном цикле."""
    все = [з["domain"] for з in json.loads(
        СПИСОК.read_text(encoding="utf-8"))["domains"]]
    прогон(tmp_path, availability=все, discover=все)
    итоги = мера.проверить(корень_цикла=tmp_path)
    assert итоги["исход"] == мера.ПОЛНО
    assert итоги["вне_цикла"] == []
    assert итоги["лишние_в_цикле"] == []
