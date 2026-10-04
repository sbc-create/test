"""Согласие владельца, выданное ИЗ ЧАТА, и почему это не право модели.

Задача была такая: согласие на открытие домена хранится в каталоге root и
создаётся только командой владельца, поэтому выдать его из рабочего чата было
нечем — операция упиралась в человека с терминалом.

Прямой инструмент моста задачу НЕ решает: мост работает от `claude`, и
«инструмент регистрации согласия» без доказательства означал бы право модели
выдавать разрешения себе. Тогда корневой якорь, из-за которого флаг в реестре
разрешением не считается, становится украшением.

Поэтому вызов из чата несёт доказательство — одноразовый код владельца. Здесь
закреплены свойства, без которых механизм не имеет смысла:

* без кода согласие не регистрируется;
* код действует ОДИН раз;
* код привязан к ДОМЕНУ и ДЕЙСТВИЮ: заявкой на `grant` для одного домена
  нельзя получить `revoke` для другого;
* код не попадает ни в заявку на диске, ни в ответ инструмента, ни в отказ;
* согласие создаёт ТА ЖЕ команда владельца, второй реализации нет;
* итог проверяется чтением якоря, а не выводом команды.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from factory.cell import owner_codes
from factory.cell import queue as q

ДОМЕН = "t-consent.localhost"
САЙТ = "t-consent-01"
КОД = "oc-AAAAA-BBBBB-CCCCC"


@pytest.fixture()
def хранилище(tmp_path, monkeypatch):
    """Коды владельца на стенде; проверка владельца файла подменена.

    Требование «файл принадлежит root и недоступен никому больше» закреплено
    отдельно (`test_права_требуются`): без root его на стенде не создать, а
    ослаблять проверку ради удобства теста нельзя.
    """
    п = tmp_path / "owner-consent-codes.json"
    п.write_text(json.dumps({
        "schema_version": 1, "issued_at": "2026-10-04T00:00:00Z",
        "valid_until": "2099-01-01T00:00:00Z",
        "codes": [
            {"id": "c01", "code": КОД, "valid_until": "2099-01-01T00:00:00Z"},
            {"id": "c02", "code": "oc-DDDDD-EEEEE-FFFFF",
             "valid_until": "2000-01-01T00:00:00Z"},
        ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(owner_codes, "ХРАНИЛИЩЕ", п)
    monkeypatch.setattr(owner_codes, "_права", lambda: (True, ""))
    return п


def test_привязка_зависит_от_домена_и_действия():
    а = owner_codes.привязка(КОД, ДОМЕН, "grant")
    assert а != owner_codes.привязка(КОД, ДОМЕН, "revoke"), "действие не входит"
    assert а != owner_codes.привязка(КОД, "другой.localhost", "grant"), (
        "домен не входит в привязку: заявку можно было бы применить к чужому "
        "домену")
    assert len(а) == 64 and all(з in "0123456789abcdef" for з in а)


def test_код_гасится_после_первого_применения(хранилище):
    привязка = owner_codes.привязка(КОД, ДОМЕН, "grant")
    первый = owner_codes.проверить_и_погасить(привязка, ДОМЕН, "grant")
    assert первый["id"] == "c01"
    assert первый["used_for"] == f"{ДОМЕН}:grant"
    with pytest.raises(owner_codes.КодОтвергнут) as ош:
        owner_codes.проверить_и_погасить(привязка, ДОМЕН, "grant")
    assert "одноразов" in str(ош.value)


def test_чужая_привязка_не_доказывает_ничего(хранилище):
    чужая = owner_codes.привязка(КОД, "другой.localhost", "grant")
    with pytest.raises(owner_codes.КодОтвергнут) as ош:
        owner_codes.проверить_и_погасить(чужая, ДОМЕН, "grant")
    assert "не доказано" in str(ош.value)
    # Код при этом НЕ погашен: отказ не вправе расходовать чужой код.
    данные = json.loads(хранилище.read_text(encoding="utf-8"))
    assert all(not к.get("used_at") for к in данные["codes"])


def test_просроченный_код_отвергается(хранилище):
    привязка = owner_codes.привязка("oc-DDDDD-EEEEE-FFFFF", ДОМЕН, "grant")
    with pytest.raises(owner_codes.КодОтвергнут) as ош:
        owner_codes.проверить_и_погасить(привязка, ДОМЕН, "grant")
    assert "срок" in str(ош.value)


def test_отказ_не_повторяет_кода(хранилище):
    """Ни код, ни его привязка не появляются в тексте отказа."""
    привязка = owner_codes.привязка("oc-ZZZZZ-ZZZZZ-ZZZZZ", ДОМЕН, "grant")
    with pytest.raises(owner_codes.КодОтвергнут) as ош:
        owner_codes.проверить_и_погасить(привязка, ДОМЕН, "grant")
    текст = str(ош.value)
    assert "oc-" not in текст, текст
    assert привязка not in текст, текст


def test_права_требуются(tmp_path, monkeypatch):
    """Хранилище, доступное не только root, не принимается вовсе."""
    п = tmp_path / "codes.json"
    п.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(owner_codes, "ХРАНИЛИЩЕ", п)
    with pytest.raises(owner_codes.КодОтвергнут) as ош:
        owner_codes.проверить_и_погасить("a" * 64, ДОМЕН, "grant")
    # На стенде файл принадлежит обычной учётной записи — это и проверяется.
    assert "root" in str(ош.value)


def test_заявка_несёт_привязку_а_не_код():
    привязка = owner_codes.привязка(КОД, ДОМЕН, "grant")
    заявка = q.собрать(САЙТ, "", "", operation="owner-consent",
                       consent_action="grant", consent_proof=привязка,
                       note="проба")
    сырое = json.dumps(заявка.as_dict(), ensure_ascii=False)
    assert КОД not in сырое, "код владельца попал в заявку на диске"
    assert привязка in сырое
    assert заявка.request_id.startswith(f"{САЙТ}-consent-grant-")


def test_форма_заявки_проверяется():
    with pytest.raises(q.RequestRejected):
        q.разобрать({"request_id": "x-consent-1", "operation": "owner-consent",
                     "site_id": САЙТ, "commit": "", "digest": "",
                     "consent_action": "grant", "consent_proof": "коротко"})
    with pytest.raises(q.RequestRejected):
        q.разобрать({"request_id": "x-consent-2", "operation": "owner-consent",
                     "site_id": САЙТ, "commit": "", "digest": "",
                     "consent_action": "maybe", "consent_proof": "a" * 64})
    with pytest.raises(q.RequestRejected) as ош:
        q.разобрать({"request_id": "x-access-1", "operation": "access-check",
                     "site_id": САЙТ, "commit": "", "digest": "",
                     "consent_action": "grant", "consent_proof": "a" * 64})
    assert "не распоряжается" in str(ош.value)


def test_инструмент_требует_код():
    from factory.qwen import mcp

    assert "register_owner_consent" in mcp.ИНСТРУМЕНТЫ
    assert "register_owner_consent" in mcp.ПИШУЩИЕ, (
        "инструмент меняет состояние и обязан быть в перечне пишущих: иначе "
        "режим «только чтение» его не скроет")
    схема = mcp.ИНСТРУМЕНТЫ["register_owner_consent"]["схема"]
    assert "code" in схема["required"], (
        "без обязательного кода инструмент стал бы правом выдать разрешение "
        "себе")
    with pytest.raises(mcp.ОшибкаИнструмента) as ош:
        mcp.вызвать("register_owner_consent", {"site": ДОМЕН})
    assert "code" in str(ош.value)


def test_исполнитель_зовёт_команду_владельца():
    """Второй реализации согласия не появляется — только та же команда."""
    текст = pathlib.Path("factory/cell/executor.py").read_text(encoding="utf-8")
    участок = текст[текст.index("def зарегистрировать_согласие"):]
    участок = участок[:участок.index("def переключить_слой_индексации")]
    assert "authorize-indexing.sh" in участок, (
        "исполнитель создаёт согласие сам, минуя команду владельца")
    assert "проверить_и_погасить" in участок, "код не проверяется"
    assert "owner_consent.сведения" in участок, (
        "итог берётся из вывода команды, а не из чтения якоря")


# --- репетиция всей цепочки на изолированном сайте ------------------------
#
# Настоящая приёмка «из чата» требует двух действий администратора: выдать коды
# (файл root) и переустановить исполнителя с новой операцией. Здесь проходит
# ВСЯ логика цепочки без root: заявка -> проверка кода -> та же команда
# владельца -> чтение якоря -> отзыв. Подменены ровно две вещи: хранилище кодов
# (его не создать без root) и путь к команде владельца, вместо которой стоит
# заглушка, пишущая и убирающая якорь, — настоящая требует root. Логика
# исполнителя не подменяется ничем: ни запуск процессов, ни проверка итога.

ЗАГЛУШКА_КОМАНДЫ = """#!/usr/bin/env bash
set -Eeuo pipefail
domain=""
undo=0
while [ $# -gt 0 ]; do
  case "$1" in
    --domain) domain="$2"; shift 2 ;;
    --undo) undo=1; shift ;;
    *) shift ;;
  esac
done
target="${CONSENT_DIR}/${domain}.json"
if [ "$undo" = 1 ]; then
  rm -f "$target"
  echo "подтверждение удалено"
else
  printf '{"schema_version": 1, "domain": "%s", "site_id": "%s", "authorized": true, "by": "owner", "at": "2026-10-04T00:00:00Z", "id": "stand-0001"}\\n' \\
    "$domain" "$SITE_ID_FOR_STUB" > "$target"
  echo "создан $target"
fi
"""


@pytest.fixture()
def цепочка(tmp_path, monkeypatch, хранилище):
    from factory.cell import executor, owner_consent, registry

    согласия = tmp_path / "owner-consent"
    согласия.mkdir()
    monkeypatch.setattr(owner_consent, "КОРЕНЬ", согласия)
    # Владелец файла якоря закреплён отдельно (test_owner_consent): без root
    # его на стенде не создать, а ослаблять правило ради удобства нельзя.
    monkeypatch.setattr(owner_consent, "_права", lambda путь: (True, ""))

    команда = tmp_path / "authorize-indexing.sh"
    команда.write_text(ЗАГЛУШКА_КОМАНДЫ, encoding="utf-8")
    команда.chmod(0o755)
    monkeypatch.setattr(executor, "КОМАНДА_СОГЛАСИЯ", команда)
    monkeypatch.setenv("CONSENT_DIR", str(согласия))
    monkeypatch.setenv("SITE_ID_FOR_STUB", САЙТ)

    class Ячейка:
        site_id = САЙТ
        domain = ДОМЕН

    monkeypatch.setattr(registry, "resolve", lambda _: Ячейка())
    return {"ex": executor, "консент": owner_consent, "согласия": согласия}


def _заявка(действие: str, код: str = КОД):
    return q.собрать(САЙТ, "", "", operation="owner-consent",
                     consent_action=действие,
                     consent_proof=owner_codes.привязка(код, ДОМЕН, действие))


def _добавить_код(значение: str) -> None:
    путь = pathlib.Path(owner_codes.ХРАНИЛИЩЕ)
    данные = json.loads(путь.read_text(encoding="utf-8"))
    данные["codes"].append({"id": "c03", "code": значение,
                            "valid_until": "2099-01-01T00:00:00Z"})
    путь.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")


def test_цепочка_выдача_видимость_и_отзыв(цепочка):
    ex = цепочка["ex"]

    # 1. Выдача согласия заявкой — кода в результате нет.
    итог = ex.зарегистрировать_согласие(_заявка("grant"), dry_run=False)
    assert итог["status"] == "applied", итог
    assert итог["stage"] == "consent_applied"
    assert КОД not in json.dumps(итог, ensure_ascii=False), (
        "код владельца попал в результат операции")
    assert итог["steps"]["code"]["id"] == "c01"

    # 2. Видимость: диагностика фабрики читает якорь и признаёт согласие.
    сведения = цепочка["консент"].сведения(ДОМЕН)
    assert сведения["present"] is True, сведения
    ок, почему, запись = цепочка["консент"].проверить(САЙТ, ДОМЕН)
    assert ок is True, почему
    assert запись["id"] == "stand-0001"

    # 3. Повтор тем же кодом невозможен.
    with pytest.raises(ex.ExecutorError) as ош:
        ex.зарегистрировать_согласие(_заявка("grant"), dry_run=False)
    assert "одноразов" in str(ош.value)

    # 4. Отзыв другим кодом, и его ДЕЙСТВИЕ проверяется чтением якоря.
    _добавить_код("oc-GGGGG-HHHHH-IIIII")
    итог2 = ex.зарегистрировать_согласие(
        _заявка("revoke", "oc-GGGGG-HHHHH-IIIII"), dry_run=False)
    assert итог2["status"] == "applied", итог2
    assert цепочка["консент"].сведения(ДОМЕН)["present"] is False, (
        "отзыв не подействовал: якорь остался")
    ок2, почему2, _ = цепочка["консент"].проверить(САЙТ, ДОМЕН)
    assert ок2 is False and "не существует" in почему2


def test_сухой_прогон_не_гасит_код(цепочка):
    итог = цепочка["ex"].зарегистрировать_согласие(_заявка("grant"), dry_run=True)
    assert итог["status"] == "nothing-to-do"
    данные = json.loads(pathlib.Path(owner_codes.ХРАНИЛИЩЕ).read_text(encoding="utf-8"))
    assert all(not к.get("used_at") for к in данные["codes"]), (
        "сухой прогон израсходовал код владельца")


def test_отсутствие_команды_владельца_названо(цепочка, monkeypatch):
    """Без команды владельца согласие не выдаётся, и это сказано."""
    monkeypatch.setattr(цепочка["ex"], "КОМАНДА_СОГЛАСИЯ",
                        pathlib.Path("/нет/такой/команды.sh"))
    with pytest.raises(цепочка["ex"].ExecutorError) as ош:
        цепочка["ex"].зарегистрировать_согласие(_заявка("grant"), dry_run=False)
    assert "команды владельца" in str(ош.value)
