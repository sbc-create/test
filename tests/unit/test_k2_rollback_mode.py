"""REQ-K2-ROLLBACK: возврат на прежний выпуск делается тем же сценарием.

Сценарий выпуска ПЕЧАТАЛ команду возврата текстом («откат вручную: ln -sfn …
&& systemctl restart …») и сам её не умел. Значит путь откатa не проверялся ни
разу — а Definition of Done проекта прямо запрещает считать работу сделанной,
если «нет бэкапа или не проверен rollback».

Режим `--rollback` делает ровно то, что печаталось, и ПРОВЕРЯЕТ результат:
переключает `current` на выпуск из `.previous-release`, перезапускает юнит
разрешённой командой и опознаёт витрину по `runtime_path` — тем же способом,
что выпуск. Без опознания откат был бы «ссылка переключена», а не «витрина
вернулась».

Проверено на живой витрине 2026-10-18: `dff8e5f5b912 → 58699a13e0dd`, опознание
подтвердило выпуск, главная отдала 114 188 знаков и 84 карточки; обратный
переход `58699a13e0dd → dff8e5f5b912` подтверждён тем же способом, и сухой
прогон после него сказал «выложена та же голова».
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

СЦЕНАРИЙ = (Path(__file__).resolve().parents[2] / "automation" / "host"
            / "k2-release-code.sh")
ТЕКСТ = СЦЕНАРИЙ.read_text(encoding="utf-8")
ОБЁРТКА = (Path(__file__).resolve().parents[2] / "automation" / "local"
           / "k2-release-code.sh").read_text(encoding="utf-8")


def _ветка() -> str:
    начало = ТЕКСТ.index('if [ "$mode" = "--rollback" ]; then')
    return ТЕКСТ[начало:ТЕКСТ.index('if [ "$mode" = "--verify" ]; then', начало)]


def test_режим_объявлен_в_обоих_сценариях():
    assert '--verify|--rollback' in ТЕКСТ
    assert '--verify|--rollback' in ОБЁРТКА


def test_откат_берёт_выпуск_из_файла_а_не_угадывает():
    ветка = _ветка()
    assert 'prev="$(cat "$previous_file")"' in ветка
    assert "[ ! -f \"$previous_file\" ]" in ветка, (
        "отсутствие файла прежнего выпуска обязано называться, а не "
        "приводить к пустой ссылке")


def test_исчезнувший_каталог_прежнего_выпуска_останавливает():
    ветка = _ветка()
    assert '[ ! -d "$prev" ]' in ветка
    assert "exit 2" in ветка


def test_повторный_откат_ничего_не_делает():
    """Идемпотентность: `current` уже на прежнем — говорим и выходим."""
    ветка = _ветка()
    assert '[ "$prev" = "$old_release" ]' in ветка
    assert "откат не нужен" in ветка


def test_откат_опознаёт_витрину_а_не_только_переключает():
    ветка = _ветка()
    assert "runtime_path" in ветка
    assert "откат не подтверждён" in ветка


def test_неудача_healthz_возвращает_ссылку_как_была():
    """Отрицательный контроль: неудачный откат не оставляет витрину нигде."""
    ветка = _ветка()
    и_отказ = ветка.index('[ "$rb_ready" = 0 ]')
    хвост = ветка[и_отказ:]
    assert 'ln -sfn "$old_release" "$current_link"' in хвост
    assert 'restart_unit "$unit"' in хвост


def test_прежний_выпуск_переписывается_после_откатa():
    """Иначе второй `--rollback` не вернул бы вперёд."""
    ветка = _ветка()
    assert 'printf \'%s\\n\' "$old_release" > "$previous_file"' in ветка


def test_обёртка_останавливается_на_первой_неудаче():
    кусок = ОБЁРТКА[ОБЁРТКА.index('if [ "$mode" = "--rollback" ]; then'):]
    кусок = кусок[:кусок.index("# Обзор не останавливается")]
    assert "откат не подтверждён — останавливаюсь" in кусок
    assert "exit 1" in кусок


@pytest.fixture(scope="module")
def различитель() -> str:
    """Проверка опознания из heredoc ветки откатa."""
    кусок = _ветка()
    начало = кусок.index("<<'PY'\n") + len("<<'PY'\n")
    конец = кусок.index("\nPY\n", начало)
    тело = кусок[начало:конец]
    assert "runtime_path" in тело
    return тело


def _запуск(код: str, ответ, tmp_path: Path) -> str:
    файл = tmp_path / "healthz.json"
    файл.write_text(ответ if isinstance(ответ, str)
                    else json.dumps(ответ, ensure_ascii=False), encoding="utf-8")
    г = subprocess.run([sys.executable, "-", str(файл),
                        "/srv/lordserial-net-ru/releases/58699a13e0dd"],
                       input=код, capture_output=True, text=True)
    assert г.returncode == 0, г.stderr
    return г.stdout.strip()


def test_опознание_прежнего_выпуска_проходит(различитель, tmp_path):
    вывод = _запуск(различитель, {
        "runtime_path": "/srv/lordserial-net-ru/releases/58699a13e0dd/src/"
                        "lords-frontend.py"}, tmp_path)
    assert вывод == ""


def test_опознание_ловит_невернувшуюся_витрину(различитель, tmp_path):
    """Ссылка переключена, а процесс остался на прежнем коде."""
    вывод = _запуск(различитель, {
        "runtime_path": "/srv/lordserial-net-ru/releases/dff8e5f5b912/src/"
                        "lords-frontend.py"}, tmp_path)
    assert "dff8e5f5b912" in вывод and "58699a13e0dd" in вывод
