"""Сборщик контекста образа Yummy: что попадает в образ и что попасть не может.

Главный риск здесь не технический, а предметный: вместе с правкой карты в образ
`.site` могли уехать две недели чужой работы, а с ними — файл обрезки заголовка,
то есть условие эксперимента B031 (у контроля заголовок обрезан, у подопытных
нет). Поэтому перечень запрещённых к переносу файлов проверяется тестом, а не
памятью.

Второй риск — порядок наложения: когда один и тот же файл приходит из двух
источников (перенос карты и патч свежести), в контексте должен остаться
ПОСЛЕДНИЙ, иначе в образ уедет непатченная версия.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_с = importlib.util.spec_from_file_location(
    "assemble_yummy_image_context",
    КОРЕНЬ / "automation/local/assemble-yummy-image-context.py")
ИНС = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ИНС)


def _источник(корень: pathlib.Path, файлы: dict[str, str]) -> pathlib.Path:
    корень.mkdir(parents=True, exist_ok=True)
    for путь, текст in файлы.items():
        цель = корень / путь
        цель.parent.mkdir(parents=True, exist_ok=True)
        цель.write_text(текст, encoding="utf-8")
    return корень


def _тест(tmp_path: pathlib.Path) -> pathlib.Path:
    файл = tmp_path / "проба.test.ts"
    файл.write_text('import { x } from "../src/lib/seo/sitemap.ts";\n',
                    encoding="utf-8")
    return файл


def test_контекст_собирается(tmp_path):
    источник = _источник(tmp_path / "a", {"lib/seo/sitemap.ts": "export const a = 1;\n"})
    выход = tmp_path / "ctx"
    код = ИНС.главное(["--out", str(выход), "--base", "образ:1", "--title", "проба",
                       "--src", str(источник), "--test", str(_тест(tmp_path))])
    assert код == 0
    assert (выход / "src/lib/seo/sitemap.ts").is_file()
    assert (выход / "Dockerfile").is_file()
    dockerfile = (выход / "Dockerfile").read_text(encoding="utf-8")
    assert "ARG BASE=образ:1" in dockerfile
    assert "vitest run" in dockerfile
    assert "next build" in dockerfile


def test_тест_переписывается_на_производную_копию(tmp_path):
    """Тесты импортируют копию дерева, которую собирает тестовый шаг."""
    источник = _источник(tmp_path / "a", {"lib/seo/sitemap.ts": "export const a = 1;\n"})
    выход = tmp_path / "ctx"
    ИНС.главное(["--out", str(выход), "--base", "образ:1", "--title", "проба",
                 "--src", str(источник), "--test", str(_тест(tmp_path))])
    текст = (выход / "tests-patch/проба.test.ts").read_text(encoding="utf-8")
    assert 'from "./src/lib/seo/sitemap.ts"' in текст
    assert "../src/" not in текст


@pytest.mark.parametrize("запрещённый", sorted(ИНС.ЗАПРЕЩЕНО))
def test_запрещённый_файл_роняет_сборку(capsys, tmp_path, запрещённый):
    """Файл обрезки заголовка и чужая работа в образ попасть не могут."""
    источник = _источник(tmp_path / "a", {запрещённый: "// чужое\n"})
    код = ИНС.главное(["--out", str(tmp_path / "ctx"), "--base", "образ:1",
                       "--title", "проба", "--src", str(источник)])
    assert код == 2
    вывод = capsys.readouterr().out
    assert "НЕ СОБРАНО" in вывод
    assert ИНС.ЗАПРЕЩЕНО[запрещённый][:20] in вывод


def test_перечень_запрещённых_включает_условие_эксперимента():
    """Если файл обрезки выпадет из перечня, B031 можно будет снести молча."""
    ключи = " ".join(ИНС.ЗАПРЕЩЕНО)
    assert "seo-core/trunc" in ключи
    причина = next(v for k, v in ИНС.ЗАПРЕЩЕНО.items() if "seo-core" in k)
    assert "B031" in причина


def test_последний_источник_перекрывает_первый(tmp_path):
    """Патченный файл обязан вытеснить непатченный, а не наоборот."""
    первый = _источник(tmp_path / "a", {"lib/seo/sitemap-catalog.ts": "// без правки\n"})
    второй = _источник(tmp_path / "b", {"lib/seo/sitemap-catalog.ts": "// С ПРАВКОЙ\n"})
    выход = tmp_path / "ctx"
    ИНС.главное(["--out", str(выход), "--base", "образ:1", "--title", "проба",
                 "--src", str(первый), "--src", str(второй)])
    assert "С ПРАВКОЙ" in (выход / "src/lib/seo/sitemap-catalog.ts").read_text(
        encoding="utf-8")


def test_прежний_контекст_очищается(tmp_path):
    """Файл от прошлой сборки не должен уехать в образ новой."""
    выход = tmp_path / "ctx"
    (выход / "src" / "lib").mkdir(parents=True)
    (выход / "src/lib/старое.ts").write_text("// хвост\n", encoding="utf-8")
    источник = _источник(tmp_path / "a", {"lib/seo/sitemap.ts": "export const a = 1;\n"})
    ИНС.главное(["--out", str(выход), "--base", "образ:1", "--title", "проба",
                 "--src", str(источник)])
    assert not (выход / "src/lib/старое.ts").exists()


def test_нет_каталога_источника_это_код_два(capsys, tmp_path):
    код = ИНС.главное(["--out", str(tmp_path / "ctx"), "--base", "образ:1",
                       "--title", "проба", "--src", str(tmp_path / "нет")])
    assert код == 2
    assert "НЕ СОБРАНО" in capsys.readouterr().out


def test_нет_файла_теста_это_код_два(capsys, tmp_path):
    источник = _источник(tmp_path / "a", {"lib/seo/sitemap.ts": "export const a = 1;\n"})
    код = ИНС.главное(["--out", str(tmp_path / "ctx"), "--base", "образ:1",
                       "--title", "проба", "--src", str(источник),
                       "--test", str(tmp_path / "нет.test.ts")])
    assert код == 2
    assert "НЕ СОБРАНО" in capsys.readouterr().out


def test_тестовый_шаг_проверяет_эквивалентность_копии():
    """Общий тестовый шаг обязан сверять производную копию с оригиналом."""
    шаг = ИНС.ШАГ_ТЕСТОВ.read_text(encoding="utf-8")
    assert "sha256sum" in шаг
    assert 'test "${ORIG}" = "${BACK}"' in шаг
    assert 'test "${WAS}" -gt "0"' in шаг
    # Пользователь обязан вернуться: иначе образ поедет с root.
    assert шаг.rstrip().endswith("USER node")
