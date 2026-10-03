#!/usr/bin/env python3
"""Прогон пакета connect-site-factory-bridge.sh на МАКЕТЕ с настоящим docker compose.

Зачем. Пакет исполняется на чужом хосте (srv-qwen), и проверять его чтением
бессмысленно: ошибки такого рода — переименование сервиса, зависимость
`condition: service_healthy`, двойное разрешение имени в DNS, откат — видны
только исполнением. Здесь строится макет той же ФОРМЫ, что подтверждена
администратором, и пакет прогоняется по нему настоящим `docker compose`.

Что макет НЕ проверяет: настоящий туннель SSH и настоящие ответы моста из
контейнера Open WebUI. Канал в макете заведомо недоступен (цель — адрес из
TEST-NET-3), поэтому приёмка обязана ПРОВАЛИТЬСЯ, а пакет — вернуть состояние.
Это и есть проверяемое здесь свойство: отказ не оставляет систему сломанной.

Запуск (нужен доступ к docker; создаёт и удаляет ТОЛЬКО свой проект):

    python3 automation/local/mock-srv-qwen-package.py
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПАКЕТ = КОРЕНЬ / "automation" / "srv-qwen" / "connect-site-factory-bridge.sh"
ОБРАЗ = os.environ.get("MOCK_IMAGE", "redis:7-alpine")
ПРОЕКТ = "sfmock"
СЕТЬ = "sfmock-net"

COMPOSE = """\
services:

  site-factory-mcp:
    image: {образ}
    container_name: sfmock-site-factory-mcp
    restart: unless-stopped
    command: ["redis-server", "--port", "6379"]
    volumes:
      - sfmock-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "6379", "ping"]
      interval: 3s
      timeout: 3s
      retries: 5
    networks:
      qwen_default:
        aliases:
          - qwen-site-factory-mcp
          - site-factory-mcp

  seo-analytics-mcp:
    image: {образ}
    container_name: sfmock-seo-analytics-mcp
    command: ["sleep", "3600"]
    environment:
      SITE_FACTORY_URL: http://site-factory-mcp:9000/mcp
    depends_on:
      site-factory-mcp:
        condition: service_healthy
        required: true
    networks:
      qwen_default: {{}}

  open-webui:
    image: {образ}
    container_name: sfmock-open-webui
    command: ["sleep", "3600"]
    networks:
      qwen_default: {{}}

volumes:
  sfmock-data:

networks:
  qwen_default:
    name: {сеть}
"""

итоги: list[tuple[bool, str]] = []


def проверка(условие: bool, описание: str) -> None:
    итоги.append((bool(условие), описание))
    print(f"   {'OK  ' if условие else 'СБОЙ'} {описание}")


def выполнить(аргументы, **kw):
    return subprocess.run(аргументы, capture_output=True, text=True, timeout=600, **kw)


def compose(каталог: pathlib.Path, *аргументы):
    return выполнить(["docker", "compose", "-p", ПРОЕКТ, "--project-directory", str(каталог),
                      "-f", str(каталог / "compose.yaml"), *аргументы])


def имена_с_алиасом(алиас: str) -> list[str]:
    """Контейнеры, которых DNS сети разрешит по этому имени."""
    найденные = []
    пс = выполнить(["docker", "ps", "--format", "{{.Names}}"]).stdout.split()
    for имя in пс:
        данные = выполнить(["docker", "inspect", имя, "--format",
                            "{{json .NetworkSettings.Networks}}"]).stdout.strip()
        try:
            сети = json.loads(данные)
        except json.JSONDecodeError:
            continue
        for сеть in сети.values():
            алиасы = (сеть or {}).get("Aliases") or []
            if алиас in алиасы:
                найденные.append(имя)
                break
    return sorted(найденные)


def главное() -> int:
    if not shutil.which("docker"):
        print("нет docker — прогон невозможен")
        return 2
    работа = pathlib.Path(tempfile.mkdtemp(prefix="sfmock-"))
    канал = работа / "channel"
    канал.mkdir()
    (работа / "compose.yaml").write_text(COMPOSE.format(образ=ОБРАЗ, сеть=СЕТЬ), encoding="utf-8")
    # Одноразовый ключ: настоящий ключ канала живёт на srv-qwen и здесь не нужен.
    выполнить(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "mock",
               "-f", str(канал / "bridge_key")])
    (канал / "known_hosts").write_text(
        "45.131.182.225 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFsE8ga+faA5pSxQGu37jtiUtMLJKaeIEo8dcKNB+pvZ\n",
        encoding="utf-8")

    try:
        print("=== 1. макет поднимается, зависимость service_healthy работает")
        up = compose(работа, "up", "-d")
        проверка(up.returncode == 0, f"макет поднят ({up.stderr.strip().splitlines()[-1:] or ['']})")
        пс = compose(работа, "ps", "--format", "json").stdout
        проверка("sfmock-seo-analytics-mcp" in пс,
                 "зависимый сервис запущен — значит условие service_healthy выполнилось")
        проверка(имена_с_алиасом("site-factory-mcp") == ["sfmock-site-factory-mcp"],
                 "до изменения имя site-factory-mcp разрешается в прежний контейнер")

        print("=== 2. пакет: проверка без изменений (--check)")
        проверить = выполнить(["bash", str(ПАКЕТ), "--check",
                               "--compose-file", str(работа / "compose.yaml"),
                               "--channel-dir", str(канал),
                               "--bridge-image", ОБРАЗ,
                               "--webui-container", "sfmock-open-webui",
                               "--backup-root", str(работа / "backups"),
                               "--factory-target", "sfbridge@203.0.113.1"])
        print((проверить.stdout + проверить.stderr).strip()[-1200:])
        проверка(проверить.returncode == 0, "--check прошёл")
        проверка("зависимости на site-factory-mcp: seo-analytics-mcp:service_healthy:True"
                 in проверить.stdout, "--check назвал зависимость с условием")
        проверка((работа / "compose.yaml").read_text(encoding="utf-8")
                 == COMPOSE.format(образ=ОБРАЗ, сеть=СЕТЬ),
                 "--check не изменил файл")

        print("=== 3. пакет: полный проход; приёмка обязана провалиться и откатить")
        применить = выполнить(["bash", str(ПАКЕТ),
                               "--compose-file", str(работа / "compose.yaml"),
                               "--channel-dir", str(канал),
                               "--bridge-image", ОБРАЗ,
                               "--webui-container", "sfmock-open-webui",
                               "--backup-root", str(работа / "backups"),
                               "--factory-target", "sfbridge@203.0.113.1"])
        вывод = применить.stdout + применить.stderr
        print(вывод.strip()[-2500:])
        проверка(применить.returncode != 0, "пакет завершился отказом (канал в макете невозможен)")
        проверка("возврат состояния" in вывод, "выполнен возврат состояния")

        копии = sorted((работа / "backups").glob("site-factory-bridge-*"))
        проверка(bool(копии), "резервная копия создана")
        if копии:
            к = копии[-1]
            проверка((к / "compose.yaml").exists(), "в копии есть исходный compose.yaml")
            проверка((к / "compose-resolved-before.json").exists(),
                     "в копии есть разрешённая конфигурация ДО")
            проверка((к / "compose-candidate.yaml").exists(),
                     "в копии есть предложенная конфигурация")
            кандидат = (к / "compose-candidate.yaml").read_text(encoding="utf-8")
            проверка("site-factory-mcp-legacy:" in кандидат,
                     "в предложенной конфигурации прежний сервис переименован")
            проверка("http://site-factory-mcp-legacy:9000/mcp" in кандидат,
                     "ссылка зависимого сервиса переведена на прежнюю службу")

        print("=== 4. состояние ПОСЛЕ отката")
        файл = (работа / "compose.yaml").read_text(encoding="utf-8")
        проверка(файл == COMPOSE.format(образ=ОБРАЗ, сеть=СЕТЬ),
                 "compose.yaml вернулся к исходному байт в байт")
        проверка(имена_с_алиасом("site-factory-mcp") == ["sfmock-site-factory-mcp"],
                 "имя site-factory-mcp снова разрешается РОВНО в один прежний контейнер")
        # Остановленный или перезапускающийся контейнер моста тоже носит имя
        # сервиса: по работающим его не видно, поэтому считаются ВСЕ.
        все_сервиса = выполнить(["docker", "ps", "-a",
                                 "--filter", "label=com.docker.compose.service=site-factory-mcp",
                                 "--format", "{{.Names}}"]).stdout.split()
        проверка(все_сервиса == ["sfmock-site-factory-mcp"],
                 f"контейнеров сервиса site-factory-mcp ровно один, включая остановленные "
                 f"(найдено: {все_сервиса or 'ничего'})")
        живые = выполнить(["docker", "ps", "--format", "{{.Names}}"]).stdout.split()
        проверка("sfmock-seo-analytics-mcp" in живые, "зависимый сервис не потерян")
        томa = выполнить(["docker", "volume", "ls", "--format", "{{.Name}}"]).stdout
        проверка(f"{ПРОЕКТ}_sfmock-data" in томa, "том данных прежнего сервиса сохранён")
    finally:
        # Уборка не полагается на имя проекта: пакет мог создать контейнеры в
        # другом проекте, а остатки макета ломают следующий прогон. Трогаются
        # ТОЛЬКО объекты с приставкой sfmock-.
        print("=== уборка макета")
        compose(работа, "down", "-v")
        свои = [и for и in выполнить(["docker", "ps", "-a", "--format", "{{.Names}}"]).stdout.split()
                if и.startswith("sfmock-")]
        if свои:
            выполнить(["docker", "rm", "-f", *свои])
        выполнить(["docker", "network", "rm", СЕТЬ])
        томa = [т for т in выполнить(["docker", "volume", "ls", "--format", "{{.Name}}"]).stdout.split()
                if "sfmock" in т]
        if томa:
            выполнить(["docker", "volume", "rm", *томa])
        shutil.rmtree(работа, ignore_errors=True)

    плохо = [о for у, о in итоги if not у]
    print(f"\n=== итог макета: проверок {len(итоги)}, сбоев {len(плохо)}")
    for о in плохо:
        print(f"   СБОЙ: {о}")
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(главное())
