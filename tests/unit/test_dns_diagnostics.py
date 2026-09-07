"""Разбор ответов DNS: собран вручную, значит обязан быть проверен.

`dig` в профиле разрешений нет, dnspython не установлен, и запросы собираются
здесь по проволочному формату. Такой разбор ошибается тихо: неверно прочитанное
сжатие имён даёт правдоподобный мусор, а не исключение, и отчёт о состоянии
доменов выходит уверенным и неправильным.

Отдельно закреплено различие, ради которого инструмент и писался: `NODATA` —
имя в зоне есть, записи такого типа нет; `NXDOMAIN` — имени нет вовсе. Для
домена, ожидающего DNS, это разные диагнозы: первый означает пустую зону,
второй — что зоны или делегирования нет.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import dns_diagnostics as dns  # noqa: E402


class TestКодированиеИмени:
    def test_простое_имя(self):
        assert dns._encode_name("example.com") == b"\x07example\x03com\x00"

    def test_завершающая_точка_не_создаёт_пустой_метки(self):
        assert dns._encode_name("example.com.") == dns._encode_name("example.com")

    def test_поддомен(self):
        assert dns._encode_name("www.animedia.icu") == (
            b"\x03www\x08animedia\x03icu\x00")


class TestРазборИмени:
    def test_имя_без_сжатия(self):
        data = b"\x07example\x03com\x00"
        assert dns._decode_name(data, 0) == ("example.com", 13)

    def test_указатель_сжатия_разворачивается(self):
        """Без разворота указателей разбор возвращает правдоподобный мусор."""
        data = b"\x07example\x03com\x00" + b"\x03www" + b"\xc0\x00"
        имя, конец = dns._decode_name(data, 13)
        assert имя == "www.example.com"
        assert конец == 19, "длина прочитанного обязана считаться до указателя"

    def test_указатель_в_начале(self):
        data = b"\x07example\x03com\x00" + b"\xc0\x00"
        assert dns._decode_name(data, 13) == ("example.com", 15)


class TestРазборЗаписей:
    def test_адрес_ipv4(self):
        assert dns._rdata(b"", 0, 1, bytes([45, 131, 182, 225])) == "45.131.182.225"

    def test_адрес_ipv6(self):
        rdata = bytes.fromhex("20010db8" + "0" * 24)
        assert dns._rdata(b"", 0, 28, rdata).startswith("2001:db8")

    def test_повреждённая_длина_не_принимается_за_адрес(self):
        """Три байта вместо четырёх — не адрес, и выдавать их за адрес нельзя."""
        assert dns._rdata(b"", 0, 1, b"\x2d\x83\xb6") == "2d83b6"


class TestКодыОтвета:
    @pytest.mark.parametrize("code,name", [(0, "NOERROR"), (3, "NXDOMAIN"),
                                           (2, "SERVFAIL"), (5, "REFUSED")])
    def test_коды_названы(self, code, name):
        assert dns._RCODES[code] == name


class TestНастройки:
    def test_резолверы_независимы(self):
        """Один резолвер с устаревшим кэшем показал бы не то состояние."""
        assert len(set(dns.RESOLVERS.values())) >= 4

    def test_управляющий_сервер_совпадает_с_инвентарём(self):
        инвентарь = (ROOT / "knowledge" / "INFRASTRUCTURE_INVENTORY.yaml").read_text(
            encoding="utf-8")
        assert dns.CONTROL_HOST in инвентарь, (
            "адрес управляющего сервера не выдуман, а взят из инвентаря")

    def test_инструмент_ничего_не_меняет(self):
        """Читающий инструмент не должен уметь писать: проверка по исходнику."""
        source = (ROOT / "scripts" / "dns_diagnostics.py").read_text(encoding="utf-8")
        for опасное in ("requests.post", "method=\"POST\"", "method=\"PUT\"",
                        "method=\"DELETE\"", "urlopen(request, data"):
            assert опасное not in source, f"инструмент умеет изменять: {опасное}"
