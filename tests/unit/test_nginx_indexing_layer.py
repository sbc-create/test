"""Слой индексации в nginx: правка файлов, отказ проверки, возврат, повтор.

Проверяется ПРИВИЛЕГИРОВАННАЯ часть — та, что правит конфигурации и
перезагружает nginx. Без root её поведение всё равно проверяемо: файлы лежат в
своём каталоге, `nginx` подменён заглушкой, а требование root снято ровно на
время проверки. Что именно снято — видно здесь, а не спрятано в коде.

Главное утверждение одно: частично переведённая конфигурация недопустима.
Часть блоков читала бы переменную, которой нет, и nginx не поднялся бы вовсе —
поэтому при отказе проверки ВСЕ файлы возвращаются, и перезагрузки не
происходит.
"""
from __future__ import annotations

import json
import os
import pathlib
import stat

import pytest

from factory.cell import nginx_indexing as ни
from factory.cell import privileged

САЙТ = "test-01"
ДОМЕН = "t.example"


def _конфигурация(корень: pathlib.Path, имя: str, *, порт: str) -> pathlib.Path:
    """Живая конфигурация: заголовок зашит, рядом настройки, которых нет в заготовке."""
    п = корень / "lords" / имя
    п.parent.mkdir(parents=True, exist_ok=True)
    п.write_text(
        "limit_conn_zone $binary_remote_addr zone=по_адресу:10m;\n"
        "log_format со_временем '$status $request_time';\n"
        "\n"
        "server {\n"
        f"    listen {порт};\n"
        f"    server_name {ДОМЕН} www.{ДОМЕН};\n"
        "    server_tokens off;\n"
        f"    {ни.ФИКСИРОВАННАЯ}\n"
        "    location ^~ /.well-known/acme-challenge/ { root /var/www/certbot; }\n"
        "    location / { proxy_pass http://cell_test_01; }\n"
        "}\n", encoding="utf-8")
    return п


@pytest.fixture
def площадка(tmp_path, monkeypatch):
    """Каталог nginx, заглушка `nginx`, снятое требование root."""
    корень = tmp_path / "nginx"
    (корень / "cells").mkdir(parents=True)
    (корень / "backups").mkdir(parents=True)
    файлы = [_конфигурация(корень, f"{САЙТ}.conf", порт="80"),
             _конфигурация(корень, f"{САЙТ}-tls.conf", порт="443 ssl")]
    monkeypatch.setattr(ни, "КОРЕНЬ_NGINX", корень)
    monkeypatch.setattr(ни, "КАТАЛОГ_ВКЛЮЧАЕМЫХ", корень / "cells")
    # Требование root снимается ТОЛЬКО здесь и только для проверки: на сервере
    # операцию выполняет исполнитель от root.
    monkeypatch.setattr(privileged, "_нужен_root", lambda: None)
    monkeypatch.setattr(privileged, "Площадка",
                        type("Заглушка", (), {"из_реестра": staticmethod(
                            lambda site_id, **kw: None)}))
    monkeypatch.setattr(privileged.runtime, "размещение",
                        lambda site_id, **kw: type("Р", (), {"domain": ДОМЕН})())

    # Заглушка nginx: пишет вызовы в файл, код возврата задаётся сценарием.
    вызовы = tmp_path / "nginx-calls.txt"
    заглушка = tmp_path / "nginx-stub"
    заглушка.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> {вызовы}\n'
        'if [ "$1" = "-t" ] && [ -f ' + str(tmp_path / "fail-t") + ' ]; then\n'
        '  echo "nginx: [emerg] тестовый отказ" >&2; exit 1\n'
        "fi\n"
        "exit 0\n", encoding="utf-8")
    заглушка.chmod(заглушка.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("SITE_NGINX", str(заглушка))
    return {"корень": корень, "файлы": файлы, "вызовы": вызовы,
            "отказ_t": tmp_path / "fail-t", "tmp": tmp_path}


def _вызовы(п) -> list[str]:
    return (п["вызовы"].read_text("utf-8").splitlines()
            if п["вызовы"].exists() else [])


def test_переводятся_ВСЕ_конфигурации_домена(площадка):
    """У домена две конфигурации: `:80` и `:443` отдельными файлами.

    Прежний root-скрипт брал ПЕРВУЮ подошедшую и требовал в ней ровно одну
    фиксированную строку — на таком домене он бы отказал, а переведя один
    файл, оставил бы домен закрытым заголовком из другого.
    """
    итог = privileged.слой_индексации(САЙТ, mode="OPEN", dry_run=False)
    assert итог["changed"] is True
    assert len(итог["configs"]) == 2, итог["configs"]
    перем = f"add_header X-Robots-Tag ${ни.имя_переменной(САЙТ)} always;"
    объявлений = 0
    for ф in площадка["файлы"]:
        текст = ф.read_text("utf-8")
        assert перем in текст, ф
        assert ни.ФИКСИРОВАННАЯ not in текст, ф
        if ни.map_объявлен(текст, САЙТ):
            объявлений += 1
            # Объявление map стоит в контексте http — до первого server.
            assert текст.index("map $uri") < текст.index("server {"), ф
        # Настройки, которых нет в заготовке, остались на месте.
        assert "limit_conn_zone" in текст and "log_format" in текст, ф
    # ОДНО объявление на весь контекст http. Оба файла домена включает один и
    # тот же `conf.d/lords.conf`, и второе объявление той же переменной — это
    # `nginx: [emerg] duplicate variable`: проверка конфигурации упала бы, а
    # операция откатилась бы на ровном месте.
    assert объявлений == 1, f"объявлений map: {объявлений}, должно быть одно"
    assert [ш["map_declared_here"] for ш in итог["plan"]].count(True) == 1
    включаемый = ни.путь_включаемого(САЙТ)
    тело = включаемый.read_text("utf-8")
    assert 'default "";' in тело, тело
    for путь in ни.СЛУЖЕБНЫЕ:
        assert путь.replace(".", "\\.") in тело, путь
    assert oct(включаемый.stat().st_mode & 0o777) == "0o644"
    # Резервные копии сделаны до правки.
    копии = sorted((площадка["корень"] / "backups").iterdir())
    assert len(копии) == 2, копии
    for к in копии:
        assert ни.ФИКСИРОВАННАЯ in к.read_text("utf-8")
    # Проверка и перезагрузка — в этом порядке.
    assert _вызовы(площадка) == ["-t", "-s reload"], _вызовы(площадка)


def test_закрытый_режим_пишет_запрет_по_умолчанию(площадка):
    privileged.слой_индексации(САЙТ, mode="CLOSED", dry_run=False)
    тело = ни.путь_включаемого(САЙТ).read_text("utf-8")
    assert 'default "noindex, nofollow";' in тело, тело


def test_отказ_проверки_возвращает_ВСЕ_файлы_и_не_перезагружает(площадка):
    """Частично переведённая конфигурация хуже непереведённой."""
    было = [ф.read_text("utf-8") for ф in площадка["файлы"]]
    площадка["отказ_t"].write_text("да", encoding="utf-8")
    with pytest.raises(privileged.PrivilegedRefused) as ош:
        privileged.слой_индексации(САЙТ, mode="OPEN", dry_run=False)
    assert "nginx -t отказал" in str(ош.value)
    assert "НЕ переключён" in str(ош.value)
    for ф, прежний in zip(площадка["файлы"], было):
        assert ф.read_text("utf-8") == прежний, f"{ф} не возвращён"
    # Включаемого файла не осталось: до операции его не было.
    assert not ни.путь_включаемого(САЙТ).exists()
    # Перезагрузки не было — только проверки.
    assert "-s reload" not in _вызовы(площадка), _вызовы(площадка)


def test_повтор_в_том_же_режиме_ничего_не_меняет(площадка):
    privileged.слой_индексации(САЙТ, mode="OPEN", dry_run=False)
    снимки = {ф: ф.read_text("utf-8") for ф in площадка["файлы"]}
    включаемый = ни.путь_включаемого(САЙТ)
    тело = включаемый.read_text("utf-8")
    время = включаемый.stat().st_mtime_ns
    площадка["вызовы"].unlink(missing_ok=True)

    итог = privileged.слой_индексации(САЙТ, mode="OPEN", dry_run=False)
    assert итог["changed"] is False, итог
    assert итог["include_changes"] is False
    for ф, прежний in снимки.items():
        assert ф.read_text("utf-8") == прежний
    assert включаемый.read_text("utf-8") == тело
    assert включаемый.stat().st_mtime_ns == время, "время файла не двигается"


def test_без_строки_заголовка_править_наугад_нельзя(площадка, tmp_path):
    """В конфигурации нет ни фиксированной строки, ни переменной — отказ."""
    for ф in площадка["файлы"]:
        ф.write_text(ф.read_text("utf-8").replace(ни.ФИКСИРОВАННАЯ, ""),
                     encoding="utf-8")
    with pytest.raises(privileged.PrivilegedRefused) as ош:
        privileged.слой_индексации(САЙТ, mode="OPEN", dry_run=False)
    assert "Править наугад нельзя" in str(ош.value)
    assert _вызовы(площадка) == [], "до отказа nginx не зовётся"


def test_неизвестный_режим_отвергается(площадка):
    for режим in ("", "maybe", "OPENISH", None):
        with pytest.raises(privileged.PrivilegedRefused):
            privileged.слой_индексации(САЙТ, mode=режим, dry_run=True)


def test_сухой_прогон_ничего_не_пишет(площадка):
    было = [ф.read_text("utf-8") for ф in площадка["файлы"]]
    итог = privileged.слой_индексации(САЙТ, mode="OPEN", dry_run=True)
    assert итог["dry_run"] is True and итог["changed"] is True
    assert [ш["will_convert"] for ш in итог["plan"]] == [1, 1], итог["plan"]
    for ф, прежний in zip(площадка["файлы"], было):
        assert ф.read_text("utf-8") == прежний
    assert not ни.путь_включаемого(САЙТ).exists()
    assert _вызовы(площадка) == []

def test_второе_объявление_переменной_не_появляется(площадка):
    """Повторная установка не добавляет второго `map` — ни в один файл.

    Проверяется после ДВУХ прогонов: первый переводит файлы, второй обязан
    увидеть, что переменная уже объявлена, и ничего не добавить.
    """
    privileged.слой_индексации(САЙТ, mode="OPEN", dry_run=False)
    privileged.слой_индексации(САЙТ, mode="CLOSED", dry_run=False)
    всего = sum(ни.map_объявлен(ф.read_text("utf-8"), САЙТ)
                for ф in площадка["файлы"])
    assert всего == 1, f"объявлений map после двух прогонов: {всего}"
    # И режим при этом второй прогон поменял.
    assert 'default "noindex, nofollow";' in ни.путь_включаемого(САЙТ).read_text("utf-8")
