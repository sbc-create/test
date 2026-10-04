"""Пакет подключения моста на srv-qwen: разбор, правка и приёмка.

Пакет исполняется НЕ здесь, а на чужом хосте, поэтому проверяется то, что
можно проверить без него: встроенные программы разбора конфигурации
(`PYFACTS`), точечной правки (`PYEDIT`), проверки результата (`PYCHECK`) и
приёмки (`PYACCEPT`). Они извлекаются ИЗ ДОСТАВЛЯЕМОГО ТЕКСТА скрипта —
проверять копию бессмысленно: поедет скрипт.

Главное свойство, которое здесь доказывается: имя `site-factory-mcp` после
правки принадлежит РОВНО одному сервису. В Compose имя сервиса само является
именем в DNS сети, поэтому переноса `aliases` недостаточно — пока прежний
сервис называется `site-factory-mcp`, он отвечает на это имя. Отсюда
переименование прежнего сервиса и перенаправление зависимостей, включая
`seo-analytics-mcp: {condition: service_healthy, required: true}`.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПАКЕТ = КОРЕНЬ / "automation" / "srv-qwen" / "connect-site-factory-bridge.sh"

СЕРВИС = "site-factory-mcp"
LEGACY = "site-factory-mcp-legacy"

#: Фактическая форма /opt/qwen/compose.yaml, насколько она подтверждена
#: администратором: имя сервиса, контейнер, сеть, два alias и зависимость
#: seo-analytics-mcp с условием service_healthy.
COMPOSE_ФАКТ = """\
services:

  site-factory-mcp:
    image: qwen/site-factory-mcp:1.0.0
    container_name: qwen-site-factory-mcp
    restart: unless-stopped
    volumes:
      - /opt/qwen/data:/data
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:9000/healthz"]
      interval: 30s
    networks:
      qwen_default:
        aliases:
          - qwen-site-factory-mcp
          - site-factory-mcp

  seo-analytics-mcp:
    image: qwen/seo-analytics-mcp:1.0.0
    container_name: qwen-seo-analytics-mcp
    environment:
      SITE_FACTORY_URL: http://site-factory-mcp:9000/mcp
    depends_on:
      site-factory-mcp:
        condition: service_healthy
        required: true
    networks:
      qwen_default: {}

  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: qwen-open-webui
    networks:
      qwen_default: {}

networks:
  qwen_default:
    external: true
    name: qwen_default
"""


def блок(имя: str) -> str:
    """Встроенная программа из доставляемого скрипта по ограничителю heredoc."""
    текст = ПАКЕТ.read_text(encoding="utf-8")
    m = re.search(rf"<<'{имя}'\n(.*?)\n{имя}\n", текст, re.S)
    assert m, f"в пакете нет блока {имя} — изменилась форма скрипта"
    return m.group(1)


def запустить(исходник: str, *аргументы: str, ввод: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(["python3", "-c", исходник, *аргументы],
                          capture_output=True, text=True, input=ввод, timeout=120)


@pytest.fixture()
def конфиг(tmp_path):
    """compose.yaml фикстуры + его разрешённый вид в JSON (как даёт compose)."""
    файл = tmp_path / "compose.yaml"
    файл.write_text(COMPOSE_ФАКТ, encoding="utf-8")
    разрешённый = {
        "services": {
            "site-factory-mcp": {
                "image": "qwen/site-factory-mcp:1.0.0",
                "container_name": "qwen-site-factory-mcp",
                "volumes": [{"source": "/opt/qwen/data", "target": "/data"}],
                "networks": {"qwen_default": {"aliases": ["qwen-site-factory-mcp",
                                                          "site-factory-mcp"]}},
            },
            "seo-analytics-mcp": {
                "image": "qwen/seo-analytics-mcp:1.0.0",
                "container_name": "qwen-seo-analytics-mcp",
                "environment": {"SITE_FACTORY_URL": "http://site-factory-mcp:9000/mcp"},
                "depends_on": {"site-factory-mcp": {"condition": "service_healthy",
                                                    "required": True}},
                "networks": {"qwen_default": {}},
            },
            "open-webui": {
                "image": "ghcr.io/open-webui/open-webui:main",
                "container_name": "qwen-open-webui",
                "networks": {"qwen_default": {}},
            },
        },
        "networks": {"qwen_default": {"external": True, "name": "qwen_default"}},
    }
    json_файл = tmp_path / "resolved.json"
    json_файл.write_text(json.dumps(разрешённый), encoding="utf-8")
    return файл, json_файл


def test_разбор_находит_сеть_зависимость_и_ссылку_на_имя(конфиг):
    _, json_файл = конфиг
    итог = запустить(блок("PYFACTS"), str(json_файл), СЕРВИС, LEGACY)
    assert итог.returncode == 0, итог.stderr
    факты = json.loads(итог.stdout)
    assert факты["network"] == "qwen_default"
    assert факты["container_name"] == "qwen-site-factory-mcp"
    assert факты["aliases"] == ["qwen-site-factory-mcp", "site-factory-mcp"]
    # Зависимость найдена ВМЕСТЕ с условием и обязательностью: именно их
    # придётся сохранить при перенаправлении.
    assert факты["dependents"] == ["seo-analytics-mcp:service_healthy:True"]
    assert факты["hostrefs"] == ["seo-analytics-mcp/env/SITE_FACTORY_URL"]


@pytest.mark.parametrize("порча, причина", [
    ({"services": {"other": {}}}, "нет сервиса"),
    ({"services": {"site-factory-mcp": {"networks": {"a": {}, "b": {}}}}}, "нескольких сетях"),
    ({"services": {"site-factory-mcp": {}, "site-factory-mcp-legacy": {}}}, "уже существует"),
    ({"services": {"site-factory-mcp": {"networks": {}}}}, "не объявлены сети"),
])
def test_неожиданная_конфигурация_останавливает_до_изменений(tmp_path, порча, причина):
    файл = tmp_path / "bad.json"
    файл.write_text(json.dumps(порча), encoding="utf-8")
    итог = запустить(блок("PYFACTS"), str(файл), СЕРВИС, LEGACY)
    assert итог.returncode != 0, итог.stdout
    assert причина in итог.stderr, итог.stderr


def test_правка_переименовывает_сервис_переводит_зависимость_и_добавляет_мост(конфиг, tmp_path):
    файл, _ = конфиг
    было = файл.read_text(encoding="utf-8")
    новый = tmp_path / "new.yaml"
    итог = запустить(блок("PYEDIT"), str(файл), str(новый), СЕРВИС, LEGACY,
                     "qwen_default", "/opt/qwen/site-factory-channel",
                     "alpine:3.20", "sfbridge@45.131.182.225")
    assert итог.returncode == 0, итог.stderr
    assert файл.read_text(encoding="utf-8") == было, "исходный файл изменён — правка должна идти в копию"
    текст = новый.read_text(encoding="utf-8")

    # 1. прежний сервис переименован, его опознавательные признаки целы
    assert f"\n  {LEGACY}:\n" in текст
    assert re.search(rf"^  {re.escape(СЕРВИС)}:$", текст, re.M), "нет нового сервиса моста"
    assert "container_name: qwen-site-factory-mcp" in текст
    assert "- /opt/qwen/data:/data" in текст, "томa прежнего сервиса потеряны"
    # 2. одноимённый alias убран, второй сохранён
    assert "- qwen-site-factory-mcp" in текст
    assert not re.search(r"^\s+- site-factory-mcp$", текст, re.M), "одноимённый alias остался"
    # 3. зависимость переведена С СОХРАНЕНИЕМ условия
    assert re.search(rf"depends_on:\s*\n\s+{re.escape(LEGACY)}:\s*\n\s+condition: service_healthy\s*\n\s+required: true",
                     текст), текст
    # 4. ссылка на имя хоста у другого сервиса переведена на legacy
    assert f"http://{LEGACY}:9000/mcp" in текст
    # 5. мост: канал только для чтения, многострочная команда списком
    assert "/opt/qwen/site-factory-channel:/channel:ro" in текст
    assert "sfbridge@45.131.182.225" in текст
    assert "-L 0.0.0.0:9000:127.0.0.1:9000" in текст


def test_проверка_результата_ловит_двойное_разрешение_имени(tmp_path):
    """Если бы мост получил alias рядом с прежним сервисом — проверка обязана упасть."""
    плохо = {"services": {
        СЕРВИС: {"networks": {"qwen_default": {}}},
        LEGACY: {"container_name": "qwen-site-factory-mcp",
                 "networks": {"qwen_default": {"aliases": [СЕРВИС]}}},
    }}
    файл = tmp_path / "after-bad.json"
    файл.write_text(json.dumps(плохо), encoding="utf-8")
    итог = запустить(блок("PYCHECK"), str(файл), СЕРВИС, LEGACY,
                     "qwen_default", "qwen-site-factory-mcp")
    assert итог.returncode != 0
    assert "разрешается в" in итог.stderr, итог.stderr


def test_проверка_результата_принимает_правильный_итог(tmp_path):
    хорошо = {"services": {
        СЕРВИС: {"networks": {"qwen_default": {"aliases": ["site-factory-mcp-bridge"]}}},
        LEGACY: {"container_name": "qwen-site-factory-mcp",
                 "networks": {"qwen_default": {"aliases": ["qwen-site-factory-mcp"]}}},
        "seo-analytics-mcp": {"depends_on": {LEGACY: {"condition": "service_healthy",
                                                      "required": True}}},
    }}
    файл = tmp_path / "after-good.json"
    файл.write_text(json.dumps(хорошо), encoding="utf-8")
    итог = запустить(блок("PYCHECK"), str(файл), СЕРВИС, LEGACY,
                     "qwen_default", "qwen-site-factory-mcp")
    assert итог.returncode == 0, итог.stderr
    assert "принадлежит только мосту" in итог.stdout


#: Версия правил берётся из ЕДИНСТВЕННОГО источника, а не повторяется строкой:
#: повтор разошёлся бы с кодом при первом же изменении версии, и приёмка
#: пакета проверяла бы устаревшее значение.
from factory.qwen.__main__ import ВЕРСИЯ_ИНСТРУКЦИИ  # noqa: E402


def _ответы(каталог: pathlib.Path, *, host="claude-control-01",
            version=ВЕРСИЯ_ИНСТРУКЦИИ,
            sites=23, digest="4511cf3add1b3e88fb4b5a124d19fc53", read_only=True,
            domain="lordserials22.info"):
    """Ответы трёх инструментов в той форме, которую даёт работающий мост."""
    готовность = {
        "environment": {"host": host, "instruction": {"version": version}},
        "ok": True, "read_only": read_only,
        "registry": {"valid": True, "sites": sites, "sites_digest": digest,
                     "sources": {"site_cells": {
                         "path": "/home/claude/wt-portable-site-cell-01/config/site-cells.json",
                         "ok": True, "count": sites, "error": None}}},
    }
    список = {"version": 1, "sites": [{"domain": f"site{i}.example"} for i in range(sites - 1)]
              + [{"domain": domain}]}
    сайт = {"site": {"domain": domain, "site_id": "lords-05"}}
    for имя, тело in (("system_readiness", готовность),
                      ("list_registered_sites", список),
                      ("get_registered_site", сайт)):
        (каталог / f"{имя}.json").write_text(json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "result": {"content": [{"type": "text", "text": json.dumps(тело)}]}}),
            encoding="utf-8")
    return каталог


ОЖИДАНИЯ = ("claude-control-01", ВЕРСИЯ_ИНСТРУКЦИИ, "23", "4511cf3add1b3e88",
            "config/site-cells.json", "lordserials22.info")


def test_пакет_ждёт_ту_же_версию_правил_что_объявляет_код():
    """Ожидание пакета и версия кода — одно значение, а не два похожих.

    Пакет сверяет версию правил, чтобы отличить мост фабрики от чужого
    сервера. Если версию поднять в коде и забыть в пакете, приёмка на srv-qwen
    начнёт отказывать на ПРАВИЛЬНОМ моcте — отказ по устаревшему ожиданию.
    """
    текст = ПАКЕТ.read_text(encoding="utf-8")
    m = re.search(r'EXPECT_VERSION="([^"]+)"', текст)
    assert m, "в пакете нет EXPECT_VERSION"
    assert m.group(1) == ВЕРСИЯ_ИНСТРУКЦИИ, (
        f"пакет ждёт {m.group(1)}, код объявляет {ВЕРСИЯ_ИНСТРУКЦИИ}")


def test_приёмка_проходит_на_ответах_фабрики(tmp_path):
    каталог = _ответы(tmp_path)
    итог = запустить(блок("PYACCEPT"), str(каталог), *ОЖИДАНИЯ)
    assert итог.returncode == 0, итог.stderr
    assert "приёмка" in итог.stdout


@pytest.mark.parametrize("подмена, причина", [
    ({"host": "srv-qwen"}, "отвечает не фабрика"),
    ({"sites": 0}, "сайтов="),
    ({"digest": "0000000000000000"}, "отпечаток реестра"),
    ({"version": "2026-09-01.1"}, "версия инструкции"),
    ({"read_only": False}, "read_only"),
    ({"domain": "other.example"}, "контрольного домена"),
])
def test_приёмка_отклоняет_чужой_или_изменённый_ответ(tmp_path, подмена, причина):
    """HTTP 200 не является приёмкой: ответ обязан совпасть по сути."""
    каталог = _ответы(tmp_path, **подмена)
    итог = запустить(блок("PYACCEPT"), str(каталог), *ОЖИДАНИЯ)
    assert итог.returncode != 0, итог.stdout
    assert причина in итог.stderr, итог.stderr


def test_приёмка_не_принимает_isError_за_успех(tmp_path):
    (tmp_path / "system_readiness.json").write_text(json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "result": {"isError": True, "content": [{"type": "text", "text": "реестр не прочитан"}]}}),
        encoding="utf-8")
    for имя in ("list_registered_sites", "get_registered_site"):
        (tmp_path / f"{имя}.json").write_text(json.dumps({"jsonrpc": "2.0", "id": 1,
                                                          "result": {"content": []}}),
                                              encoding="utf-8")
    итог = запустить(блок("PYACCEPT"), str(tmp_path), *ОЖИДАНИЯ)
    assert итог.returncode != 0
    assert "вернул ошибку" in итог.stderr, итог.stderr
