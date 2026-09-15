"""Сценарий открытия индексации проверяется целиком, без единой правки production.

Две выкладки подряд откатились не из-за самой правки, а из-за того, что
проверки в сценарии маскировали собственные неудачи: ожидание готовности
считало успехом ответ 502, а неполученная страница превращалась в «на странице
нет canonical». Оба раза защита сработала и production вернулся в исходное
состояние, но узнавали мы об этом уже после запуска на живом сайте.

Здесь сценарий прогоняется целиком — включая откат и повторный запуск — на
подменённых `curl` и `systemctl`. Настоящий HTML главной страницы (254 187
байт, снят 2026-09-15) служит образцом для положительной проверки canonical:
шаблон, совпадающий с выдуманной строкой, ничего не доказывает.

Проверяется главным образом то, что отличает «плохо» от «не измерено». Ответ,
которого не получили, не должен ни подтверждать блокировку чужого домена, ни
объявлять дефект на своём.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "host" / "yummy-site-open-indexing.sh"
ОБРАЗЕЦ = КОРЕНЬ / "tests" / "fixtures" / "yummyani-site-home.live-20260915.html"

ОТКРЫТЫЙ = "yummyani.site"
ЗАКРЫТЫЕ = (
    "yummyani.org", "yummyani.biz", "lordfilm47.space", "lordserial33.biz",
    "1lordserials1.online", "zonafilm.space", "animedia.icu", "animedia.space",
)

ПРЕЖНЕЕ = "# прежняя версия посредника\n"
#: Слепок, который сценарий ожидает увидеть на хосте.
ПРЕЖНИЙ_SHA = "97e4f1933de57aff65053253c0546ebbed478c180250b36d28b725d6d74200d7"

ПОДДЕЛЬНЫЙ_CURL = r'''#!/usr/bin/env python3
"""Подменный curl. Поведение задаётся переменной SCENARIO."""
import os, sys, pathlib

сценарий = os.environ["SCENARIO"]
образец = pathlib.Path(os.environ["FIXTURE_HTML"]).read_text(encoding="utf-8")
аргументы = sys.argv[1:]

url = [a for a in аргументы if a.startswith("http")][-1]
только_заголовки = "-fsSI" in аргументы


def значение(флаг):
    return аргументы[аргументы.index(флаг) + 1] if флаг in аргументы else None


домен = url.split("//", 1)[1].split("/", 1)[0]
путь = "/" + url.split("//", 1)[1].split("/", 1)[1] if "/" in url.split("//", 1)[1] else "/"
свой = домен == "yummyani.site"

# Отказы, заданные сценарием.
if свой and сценарий == "timeout":
    sys.exit(28)
if свой and сценарий == "curl_error":
    sys.exit(7)
if свой and сценарий == "http502":
    print("curl: (22) The requested URL returned error: 502", file=sys.stderr)
    sys.exit(22)
if сценарий == "closed_unreachable" and домен == "animedia.icu":
    sys.exit(28)

if свой:
    заголовки = "HTTP/2 200\r\ncontent-type: text/html; charset=utf-8\r\n"
    if путь == "/robots.txt":
        тело = "User-agent: *\nAllow: /\nDisallow: /dev/\n"
    elif сценарий == "empty_body":
        тело = ""
    elif сценарий == "bad_canonical":
        тело = образец.replace('href="https://yummyani.site"',
                               'href="https://example.invalid"')
    else:
        тело = образец
else:
    открыт_чужой = сценарий == "closed_opened" and домен == "yummyani.org"
    заголовки = "HTTP/2 200\r\ncontent-type: text/html\r\n"
    if not открыт_чужой:
        заголовки += "x-robots-tag: noindex, nofollow\r\n"
    тело = ("User-agent: *\nAllow: /\n" if открыт_чужой else "User-agent: *\nDisallow: /\n") \
        if путь == "/robots.txt" else "<html></html>"

файл_заголовков = значение("-D")
if файл_заголовков and файл_заголовков != "-":
    pathlib.Path(файл_заголовков).write_text(заголовки, encoding="utf-8")
файл_тела = значение("-o")
if файл_тела:
    if файл_тела != "/dev/null":
        pathlib.Path(файл_тела).write_text(тело, encoding="utf-8")
else:
    sys.stdout.write(заголовки if только_заголовки else тело)
'''

ПОДДЕЛЬНЫЙ_SYSTEMCTL = "#!/bin/sh\nexit 0\n"


@pytest.fixture
def песочница(tmp_path):
    """Каталог, в котором сценарий можно прогнать целиком и безопасно."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for имя, текст in (("curl", ПОДДЕЛЬНЫЙ_CURL), ("systemctl", ПОДДЕЛЬНЫЙ_SYSTEMCTL)):
        путь = bin_dir / имя
        путь.write_text(текст, encoding="utf-8")
        путь.chmod(путь.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    цель = tmp_path / "yummy-frontend.py"
    цель.write_text(ПРЕЖНЕЕ, encoding="utf-8")
    источник = tmp_path / "новый" / "yummy-frontend.py"
    источник.parent.mkdir()
    источник.write_text("# новая версия посредника\n", encoding="utf-8")
    профиль = tmp_path / "yummyani-site.json"
    профиль.write_text('{"seo_profile": {"indexing_enabled": false}}\n', encoding="utf-8")
    return {
        "tmp": tmp_path, "bin": bin_dir, "цель": цель,
        "источник": источник, "профиль": профиль,
    }


def запустить(песочница, сценарий: str, *, ожидаемый_sha: str | None = None):
    окружение = dict(os.environ)
    окружение.update(
        PATH=f"{песочница['bin']}:{os.environ['PATH']}",
        SCENARIO=сценарий,
        FIXTURE_HTML=str(ОБРАЗЕЦ),
        CURL=str(песочница["bin"] / "curl"),
        SYSTEMCTL=str(песочница["bin"] / "systemctl"),
        INSTALL_OWNERSHIP="",
        TARGET=str(песочница["цель"]),
        SOURCE=str(песочница["источник"]),
        PROFILE=str(песочница["профиль"]),
        EXPECTED_BEFORE=ожидаемый_sha or ПРЕЖНИЙ_SHA,
        REQUEST_TIMEOUT="5",
        READINESS_ATTEMPTS="2",
    )
    return subprocess.run(
        ["bash", str(СЦЕНАРИЙ)], capture_output=True, text=True, env=окружение, timeout=120
    )


def подставить_слепок(песочница):
    """Подогнать ожидаемый слепок под содержимое песочницы."""
    return subprocess.run(
        ["sha256sum", str(песочница["цель"])], capture_output=True, text=True
    ).stdout.split()[0]


# --- статический разбор -------------------------------------------------------

def test_скрипт_проходит_bash_n() -> None:
    assert subprocess.run(["bash", "-n", str(СЦЕНАРИЙ)]).returncode == 0


def test_скрипт_проходит_shellcheck() -> None:
    if shutil.which("shellcheck") is None:
        pytest.skip("shellcheck не установлен в этой среде")
    готово = subprocess.run(["shellcheck", str(СЦЕНАРИЙ)], capture_output=True, text=True)
    assert готово.returncode == 0, готово.stdout


def test_страница_и_заголовки_берутся_одним_запросом() -> None:
    """Иначе проверки могут судить о разных ответах.

    Признак — один вызов curl с `-D` и `-o` сразу, а не отдельный `-I` рядом с
    отдельным запросом тела.
    """
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert '-D "$headers_file" -o "$body_file"' in текст
    assert текст.count('"$CURL" -fsSI') == 1, (
        "заголовки отдельным запросом остались только у закрытых доменов, "
        "где тело не нужно"
    )


def test_нигде_не_осталось_проглатывания_ошибок() -> None:
    """`|| true` вокруг curl — это и есть механизм обоих ложных откатов."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    for строка in текст.splitlines():
        if "curl" in строка.lower() and "|| true" in строка:
            pytest.fail(f"ошибка запроса проглатывается: {строка.strip()}")


# --- образец настоящей страницы ----------------------------------------------

def test_образец_это_настоящая_страница() -> None:
    assert ОБРАЗЕЦ.stat().st_size == 254187, "образец должен быть снятой живой страницей"


def test_шаблон_canonical_совпадает_с_настоящей_страницей() -> None:
    """Шаблон, совпадающий только с выдуманной строкой, ничего не доказывает."""
    готово = subprocess.run(
        ["grep", "-qi", f'rel="canonical"[^>]*href="https://{ОТКРЫТЫЙ}', str(ОБРАЗЕЦ)]
    )
    assert готово.returncode == 0


# --- прогон сценария целиком --------------------------------------------------

def test_успешная_выкладка(песочница) -> None:
    готово = запустить(песочница, "ok", ожидаемый_sha=подставить_слепок(песочница))
    assert готово.returncode == 0, готово.stderr
    assert "YUMMYANI_SITE_PUBLIC_INDEXING=OPEN_PASS" in готово.stdout
    assert "OTHER_DOMAINS_INDEXING=LOCKED_PASS" in готово.stdout
    assert песочница["цель"].read_text(encoding="utf-8") == "# новая версия посредника\n"
    assert '"indexing_enabled": true' in песочница["профиль"].read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "сценарий, причина",
    [
        ("timeout", "запрос не уложился в срок"),
        ("curl_error", "curl не смог выполнить запрос"),
        ("http502", "шлюз ответил 502"),
        ("empty_body", "тело ответа пустое"),
        ("bad_canonical", "canonical указывает на чужой домен"),
    ],
)
def test_отказ_приводит_к_откату(песочница, сценарий: str, причина: str) -> None:
    готово = запустить(песочница, сценарий, ожидаемый_sha=подставить_слепок(песочница))
    assert готово.returncode != 0, f"{причина}: выкладку следовало откатить"
    assert песочница["цель"].read_text(encoding="utf-8") == ПРЕЖНЕЕ, (
        f"{причина}: посредник не возвращён в прежнее состояние"
    )
    assert '"indexing_enabled": false' in песочница["профиль"].read_text(encoding="utf-8"), (
        f"{причина}: объявленная политика не возвращена"
    )


def test_откат_подтверждается_ответом_витрины(песочница) -> None:
    """Возврат в строй не объявляется, а проверяется.

    Прежде откат заканчивался `wait_for_service || true`: служба
    перезапускалась, и сценарий молча считал дело сделанным, даже если витрина
    после отката не поднялась.
    """
    готово = запустить(песочница, "bad_canonical", ожидаемый_sha=подставить_слепок(песочница))
    assert готово.returncode != 0
    assert "откат выполнен и подтверждён" in готово.stderr
    assert песочница["цель"].read_text(encoding="utf-8") == ПРЕЖНЕЕ


def test_невозможность_подтвердить_откат_названа_прямо(песочница) -> None:
    """Если витрина не поднялась и после отката, об этом говорится отдельно."""
    готово = запустить(песочница, "timeout", ожидаемый_sha=подставить_слепок(песочница))
    assert готово.returncode != 0
    assert "ВНИМАНИЕ" in готово.stderr
    assert "не отдала 200" in готово.stderr


def test_недоступность_закрытого_домена_не_считается_подтверждением(песочница) -> None:
    """Ответ, которого не получили, не подтверждает, что домен закрыт.

    Прежде такой ответ проглатывался `|| true`, и отсутствие заголовка в пустой
    строке читалось как «запрет пропал» — либо, при обратном условии, молчание
    засчитывалось за блокировку. Оба прочтения неверны: состояние не измерено.
    """
    готово = запустить(песочница, "closed_unreachable",
                       ожидаемый_sha=подставить_слепок(песочница))
    assert готово.returncode != 0
    assert "не измерено" in готово.stderr
    assert песочница["цель"].read_text(encoding="utf-8") == ПРЕЖНЕЕ


def test_открывшийся_чужой_домен_валит_выкладку(песочница) -> None:
    готово = запустить(песочница, "closed_opened", ожидаемый_sha=подставить_слепок(песочница))
    assert готово.returncode != 0
    assert "не должен был открыться" in готово.stderr
    assert песочница["цель"].read_text(encoding="utf-8") == ПРЕЖНЕЕ


def test_повторный_запуск_ничего_не_выкладывает(песочница) -> None:
    """Идемпотентность: второй запуск только перепроверяет."""
    первый = запустить(песочница, "ok", ожидаемый_sha=подставить_слепок(песочница))
    assert первый.returncode == 0
    копии_после_первого = list(песочница["tmp"].glob("*before-open-indexing*"))

    второй = запустить(песочница, "ok")
    assert второй.returncode == 0
    assert "версия уже выложена" in второй.stdout
    assert list(песочница["tmp"].glob("*before-open-indexing*")) == копии_после_первого, (
        "повторный запуск не должен делать новых копий"
    )


def test_чужая_версия_на_хосте_отменяет_выкладку(песочница) -> None:
    """Файл меняли после подготовки — выкладка отменяется, а не затирает чужое."""
    готово = запустить(песочница, "ok", ожидаемый_sha="0" * 64)
    assert готово.returncode == 3
    assert песочница["цель"].read_text(encoding="utf-8") == ПРЕЖНЕЕ
    assert not list(песочница["tmp"].glob("*before-open-indexing*"))
