#!/usr/bin/env python3
"""Печатает каталог снимков витрины, если он на месте, иначе ничего.

Нужен раннеру набора проверок: по наличию снимков он решает, считать ли
«ничего не измерено» провалом (MOD-221). Отдельным файлом, а не строкой внутри
`run.sh`: встроенный в подстановку heredoc ломал разбор — прогон отвечал кодом
127 и не печатал ни одной новой строки.

Порядок поиска тот же, что в проверках (MOD-220): переменная окружения,
названная вызывающим → `deployment.data_dir` настройки витрины с раскрытием
`<root>` → каталог по домену. Имя каталога репозитория адресом данных не
считается.
"""
from __future__ import annotations

import json
import os
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parent.parent


def _из_настройки() -> str:
    try:
        настройка = json.loads(
            (КОРЕНЬ / "config" / "site.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — нет настройки, нет адреса
        return ""
    развёртка = настройка.get("deployment") or {}
    адрес = str(развёртка.get("data_dir") or "").replace(
        "<root>", str(развёртка.get("root") or ""))
    if адрес.startswith("/"):
        return адрес
    домен = str(настройка.get("domain") or "").replace(".", "-")
    return f"/srv/{домен}/data" if домен else ""


def каталог() -> str:
    назван = (os.environ.get("SITE_DATA_DIR") or os.environ.get("LORDS_DATA")
              or os.environ.get("ZONA02_DATA") or "")
    путь = назван or _из_настройки()
    if not путь:
        return ""
    п = pathlib.Path(путь)
    if п.is_dir() and any(п.glob("*-catalog.json")):
        return str(п)
    return ""


if __name__ == "__main__":
    print(каталог())
