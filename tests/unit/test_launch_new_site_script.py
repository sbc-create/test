"""Запуск нового домена: шаг HTTPS пропускается по предусловию, а не глохнет.

Измерено 2026-10-05 на `lordserials22.site` и `lordserials22.space`: оба
отвечают `NXDOMAIN` от авторитетного сервера зоны TLD — имени нет в
родительской зоне вовсе. `certbot` подтверждает владение доменом запросом по
HTTP на его собственное имя, поэтому у домена без записи DNS шаг не может
пройти ПО ПОСТРОЕНИЮ.

Прежде шаг вызывался всегда. При `set -Eeuo pipefail` его неудача обрывала
запуск, не доходя до шага 4 (планировщик недельного снимка), и выдавала
ненастоящий отказ за отказ установки — ровно тот класс, что `ok: command not
found` (D158): итог верный, а учёт врёт.

Проверяется ПОВЕДЕНИЕ сценария, а не наличие строк: сухой прогон запускается и
его вывод читается.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "host" / "launch-new-site.sh"
#: Домены этих сайтов измерены как не разрешающиеся (NXDOMAIN от зоны TLD).
БЕЗ_DNS = ("lords-06", "lords-07")


def _сухой(site: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(СЦЕНАРИЙ), "--site", site, "--dry-run"],
                          capture_output=True, text=True, cwd=str(КОРЕНЬ),
                          timeout=300)


@pytest.mark.parametrize("site", БЕЗ_DNS)
def test_шаг_https_пропускается_с_названной_причиной(site):
    итог = _сухой(site)
    assert итог.returncode == 0, итог.stdout + итог.stderr
    вывод = итог.stdout
    assert "не разрешается в адрес" in вывод, вывод[-800:]
    assert "certbot подтвердить владение не сможет" in вывод
    # Пропуск назван пропуском, а не успехом.
    assert "шаг пропущен НЕ из-за ошибки" in вывод
    # И названа ровно та команда, которой шаг делается ПОСЛЕ записи DNS.
    assert f"install-site-tls.sh --site {site}" in вывод
    # Запуск дошёл до конца: шаг 4 не потерян.
    assert "шаг 4" in вывод
    assert "сухой прогон: ничего не менялось" in вывод


def test_имена_переменных_сценария_только_ascii():
    """Требование bash, и оно уже ломало сценарий (D158)."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    import re

    for строка in текст.splitlines():
        голая = строка.strip()
        if голая.startswith("#"):
            continue
        for совпадение in re.finditer(r"^\s*([A-Za-zА-Яа-яЁё_][\w]*)=", строка):
            имя = совпадение.group(1)
            assert имя.isascii(), f"не-ASCII имя переменной: {имя!r} в {строка!r}"
        for совпадение in re.finditer(r"\$\{?([A-Za-zА-Яа-яЁё_][\w]*)", строка):
            имя = совпадение.group(1)
            assert имя.isascii(), f"не-ASCII подстановка: {имя!r} в {строка!r}"


def test_отказ_certbot_при_существующем_dns_не_проглатывается():
    """Настоящая неудача обязана остановить запуск: прятать её нельзя."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    ветка = текст.split('log "домен, шаг 3: HTTPS"', 1)[1].split('log "домен, шаг 4', 1)[0]
    assert "install-site-tls.sh" in ветка
    # В ветке, где домен разрешается, вызов идёт БЕЗ подавления кода возврата.
    вызов = [с for с in ветка.splitlines()
             if "install-site-tls.sh" in с and "echo" not in с]
    assert вызов, ветка
    for с in вызов:
        assert "|| true" not in с and "||true" not in с, с
        assert "2>/dev/null" not in с, с
