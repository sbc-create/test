"""Файл происхождения внутри выпуска обязан называть ЭТОТ выпуск.

Он существует ровно затем, чтобы происхождение работающего кода можно было
проверить, глядя на сайт, а не сверяясь с /var/lib/site-cells, куда доступа может
и не быть. Два поля делали это невозможным, и оба нашла соседняя сессия, читавшая
манифест как объявление выпуска:

* `release` записывался ДО атомарного переименования и содержал имя служебного
  каталога `.<commit12>.new`, которого через мгновение не существует;
* `live_build_id` брался из `build_id` манифеста шаблона. У zona-02 манифест
  лежит в корне дерева, а не в `config/`, и `build_id` там — ревизия
  ЗАКРЕПЛЁННОГО шаблона, одинаковая у всех выпусков витрины. Поле выходило
  пустым, то есть файл, назначение которого — назвать выпуск, выпуска не
  называл.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.cell.privileged import _записать_происхождение

КОММИТ = "a14a7758337563cf065415c628c1f2720ce4148c"
ИМЯ = "a14a77583375"


def _прочитать(дерево: Path) -> dict:
    return json.loads((дерево / "release-manifest.json").read_text(encoding="utf-8"))


def test_имя_выпуска_окончательное_а_не_временное(tmp_path: Path) -> None:
    временный = tmp_path / f".{ИМЯ}.new"
    (временный / "config").mkdir(parents=True)
    _записать_происхождение(временный, site_id="zona-02", commit=КОММИТ,
                            digest="sha256:x", account="nobody", имя_выпуска=ИМЯ)
    запись = _прочитать(временный)
    assert запись["release"] == ИМЯ, "в манифест попало имя служебного каталога"
    assert ".new" not in запись["release"]


def test_метка_выпуска_не_остаётся_пустой(tmp_path: Path) -> None:
    """Без манифеста шаблона метка строится тем же правилом, что у витрины."""
    временный = tmp_path / f".{ИМЯ}.new"
    временный.mkdir()
    _записать_происхождение(временный, site_id="zona-02", commit=КОММИТ,
                            digest="sha256:x", account="nobody", имя_выпуска=ИМЯ)
    assert _прочитать(временный)["live_build_id"] == f"{ИМЯ}-zona-02"


def test_манифест_шаблона_читается_и_из_корня_дерева(tmp_path: Path) -> None:
    """У разных семейств он лежит по-разному; пустое поле — не «его нет»."""
    временный = tmp_path / f".{ИМЯ}.new"
    временный.mkdir()
    (временный / "template-manifest.json").write_text(
        json.dumps({"live_build_id": f"{ИМЯ}-zona-02"}), encoding="utf-8")
    _записать_происхождение(временный, site_id="zona-02", commit=КОММИТ,
                            digest="sha256:x", account="nobody", имя_выпуска=ИМЯ)
    assert _прочитать(временный)["live_build_id"] == f"{ИМЯ}-zona-02"


def test_чужая_метка_не_принимается(tmp_path: Path) -> None:
    """Объявление, не называющее ЭТОТ выпуск, не годится в метку выпуска.

    Ключ `build_id` у разных семейств означает разное: у одних метку выпуска,
    у других ревизию закреплённого шаблона. Принимать его без проверки значит
    повторить ошибку сверки по заголовку — значение выглядит правильным и
    ничего не различает.
    """
    временный = tmp_path / f".{ИМЯ}.new"
    временный.mkdir()
    (временный / "template-manifest.json").write_text(
        json.dumps({"live_build_id": "b65e9e64c76a-zona-03"}), encoding="utf-8")
    _записать_происхождение(временный, site_id="zona-02", commit=КОММИТ,
                            digest="sha256:x", account="nobody", имя_выпуска=ИМЯ)
    assert _прочитать(временный)["live_build_id"] == f"{ИМЯ}-zona-02"


def test_ревизия_шаблона_не_выдаётся_за_метку_выпуска(tmp_path: Path) -> None:
    """`build_id` закреплённого шаблона одинаков у всех выпусков витрины.

    Брать его как метку выпуска — та же ошибка, что читать заголовок
    X-Site-Factory-Build-Id: значение выглядит правильным и ничего не различает.
    """
    временный = tmp_path / f".{ИМЯ}.new"
    (временный / "config").mkdir(parents=True)
    (временный / "config" / "template-manifest.json").write_text(
        json.dumps({"build_id": "zona-02-0fb857b26f85"}), encoding="utf-8")
    _записать_происхождение(временный, site_id="zona-02", commit=КОММИТ,
                            digest="sha256:x", account="nobody", имя_выпуска=ИМЯ)
    метка = _прочитать(временный)["live_build_id"]
    assert метка == f"{ИМЯ}-zona-02", f"ревизия шаблона выдана за выпуск: {метка}"


def test_остальные_поля_на_месте(tmp_path: Path) -> None:
    временный = tmp_path / f".{ИМЯ}.new"
    (временный / "config").mkdir(parents=True)
    (временный / "config" / "site.json").write_text(
        json.dumps({"entrypoint": "serve.py"}), encoding="utf-8")
    _записать_происхождение(временный, site_id="zona-02", commit=КОММИТ,
                            digest="sha256:d", account="nobody", имя_выпуска=ИМЯ)
    запись = _прочитать(временный)
    assert запись["commit"] == КОММИТ
    assert запись["digest"] == "sha256:d"
    assert запись["entrypoint"] == "serve.py"
    assert запись["installed_by"] == "cell-executor"
