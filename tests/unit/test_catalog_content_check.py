"""Регрессия: HTTP 200 с пустым каталогом обязан считаться отказом.

2026-09-04 после перезагрузки под новый тариф Redis циклически падал с
повреждённым AOF, и все три витрины отдавали 200 при нулевом каталоге. Ни одна
проверка этого не увидела: смотрели на код ответа. Отказ держался, пока его не
заметили глазами.

Поэтому здесь закреплено именно содержимое. Тесты не ходят в сеть: `curl`
подменяется на PATH, и это обязательное условие, а не удобство — иначе проверка
измеряла бы живые витрины вместо логики сценария.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "automation" / "host" / "yummy-catalog-content-check.sh"


def поддельный_curl(tmp_path: Path, тела: dict[str, str], коды: dict[str, str]) -> Path:
    """curl, отвечающий заданными телом и кодом в зависимости от хоста."""
    binn = tmp_path / "bin"
    binn.mkdir(exist_ok=True)
    for host, body in тела.items():
        (tmp_path / f"body-{host}").write_text(body, encoding="utf-8")
    for host, code in коды.items():
        (tmp_path / f"code-{host}").write_text(code, encoding="utf-8")

    curl = binn / "curl"
    curl.write_text(
        "#!/usr/bin/env bash\n"
        "url=\"${@: -1}\"\n"
        "host=$(printf '%s' \"$url\" | sed -E 's|https?://([^/]+).*|\\1|')\n"
        "if printf '%s' \"$*\" | grep -q 'http_code'; then\n"
        f"  cat {tmp_path}/code-$host 2>/dev/null || echo 000\n"
        "else\n"
        f"  cat {tmp_path}/body-$host 2>/dev/null\n"
        "fi\n",
        encoding="utf-8",
    )
    curl.chmod(0o755)
    return binn


def запустить(binn: Path, hosts: str, **env: str) -> subprocess.CompletedProcess[str]:
    окружение = dict(os.environ)
    окружение["PATH"] = f"{binn}:{окружение.get('PATH', '')}"
    окружение["CATALOG_CHECK_HOSTS"] = hosts
    окружение.update(env)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=60,
        env=окружение,
    )


КАТАЛОГ = "\n".join(f'<a href="/anime/title-{i}">t</a>' for i in range(40))
ПУСТО = "<html><body><h1>Каталог</h1></body></html>"


def test_script_exists() -> None:
    assert SCRIPT.exists(), f"нет сценария: {SCRIPT}"


def test_две_сотни_с_пустым_каталогом_это_отказ(tmp_path: Path) -> None:
    """Главное свойство: код 200 успехом не считается."""
    binn = поддельный_curl(tmp_path, {"a.test": ПУСТО}, {"a.test": "200"})
    итог = запустить(binn, "a.test")
    assert итог.returncode != 0, "пустой каталог при 200 прошёл как успех"
    assert "пустой каталог" in итог.stdout
    assert "200" in итог.stdout


def test_наполненный_каталог_проходит(tmp_path: Path) -> None:
    binn = поддельный_curl(tmp_path, {"a.test": КАТАЛОГ}, {"a.test": "200"})
    итог = запустить(binn, "a.test")
    assert итог.returncode == 0, итог.stdout + итог.stderr
    assert "ок a.test" in итог.stdout


def test_отказ_на_любом_из_трёх_доменов_валит_проверку(tmp_path: Path) -> None:
    """Проверяются все три витрины, а не первая попавшаяся."""
    binn = поддельный_curl(
        tmp_path,
        {"a.test": КАТАЛОГ, "b.test": КАТАЛОГ, "c.test": ПУСТО},
        {"a.test": "200", "b.test": "200", "c.test": "200"},
    )
    итог = запустить(binn, "a.test b.test c.test")
    assert итог.returncode != 0
    assert "ТРЕВОГА c.test" in итог.stdout
    assert "ок a.test" in итог.stdout and "ок b.test" in итог.stdout


def test_не_двухсотый_код_тоже_отказ(tmp_path: Path) -> None:
    binn = поддельный_curl(tmp_path, {"a.test": КАТАЛОГ}, {"a.test": "502"})
    итог = запустить(binn, "a.test")
    assert итог.returncode != 0
    assert "502" in итог.stdout


def test_порог_настраивается(tmp_path: Path) -> None:
    binn = поддельный_curl(tmp_path, {"a.test": КАТАЛОГ}, {"a.test": "200"})
    assert запустить(binn, "a.test", CATALOG_CHECK_MIN_TITLES="10").returncode == 0
    assert запустить(binn, "a.test", CATALOG_CHECK_MIN_TITLES="500").returncode != 0


def test_отчёт_записывается(tmp_path: Path) -> None:
    binn = поддельный_curl(tmp_path, {"a.test": ПУСТО}, {"a.test": "200"})
    отчёт = tmp_path / "report.json"
    запустить(binn, "a.test", CATALOG_CHECK_REPORT=str(отчёт))
    assert отчёт.exists()
    текст = отчёт.read_text(encoding="utf-8")
    assert '"status":"alert"' in текст
    assert '"problems":1' in текст
