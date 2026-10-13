"""Срок сертификата: «не измерено» не равно ни «просрочен», ни «в порядке».

Факт успешного запроса сертификат не проверяет: `curl` молчит, пока цепочка
верна, и про остаток дней не говорит ничего. Поэтому инструмент разбирает
`notAfter` и `subjectAltName` — и различает три исхода, а не два.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "tls-expiry-probe.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("tls_expiry_probe", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def test_неразрешимое_имя_это_не_измерено_а_не_просрочен():
    """Главное различение: отсутствие ответа и плохой сертификат — разное."""
    итог = МОД.сведения("domen-kotorogo-net-13102026.example", таймаут=5)
    assert isinstance(итог, str), итог
    assert "не разрешается" in итог or "соединение" in итог, итог


def test_живой_домен_даёт_дату_и_имена():
    """Если сети нет, проверка честно пропускается, а не выдаёт ложный успех."""
    итог = МОД.сведения("zonafilm.space", таймаут=20)
    if isinstance(итог, str):
        import pytest
        pytest.skip(f"TLS-соединение недоступно в этом окружении: {итог}")
    до, имена = итог
    import datetime as dt
    assert до.tzinfo is not None, "дата без часового пояса сравнима неверно"
    assert до > dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    assert "zonafilm.space" in имена, имена


def test_порог_запаса_настраиваемый_и_назван():
    текст = ПУТЬ.read_text(encoding="utf-8")
    assert "--дней" in текст
    assert "по умолчанию 21" in текст


def test_отсутствие_своего_имени_это_замечание():
    """Сертификат, не покрывающий свой домен, — «не про этот сайт»."""
    текст = ПУТЬ.read_text(encoding="utf-8")
    assert "собственного имени в сертификате НЕТ" in текст
    assert "не про этот сайт" in текст


def test_вывод_различает_не_измерено_словами():
    текст = ПУТЬ.read_text(encoding="utf-8")
    assert "«не измерено» — это не «просрочен» и не «в порядке»." in текст


def test_без_аргументов_инструмент_отказывает():
    г = subprocess.run([sys.executable, str(ПУТЬ)], capture_output=True,
                       text=True, timeout=120, cwd=str(КОРЕНЬ))
    assert г.returncode == 2, г.stdout
    assert "не названо ни одной витрины" in г.stdout


def test_зарезервированные_имена_не_обходятся():
    assert all(not д.endswith((".test", ".localhost")) for д in МОД.домены())
