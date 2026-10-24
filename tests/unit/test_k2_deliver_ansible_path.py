"""Доставка каталога K2 не должна зависеть от PATH оболочки.

Повод измеренный, 24.10. Суточный запуск из таймера пользователя
(`k2-catalog-deliver.user.timer`, 05:20 UTC) падал на шаге копирования:

    automation/local/k2-deliver-catalog.sh: line 115: ansible: command not found

При этом ansible установлен — `/home/claude/.local/bin/ansible`. systemd даёт
юниту минимальный PATH (`/usr/local/bin:/usr/bin:/bin`), и этого каталога в нём
нет; в интерактивной оболочке тот же скрипт работает, потому что PATH туда
добавляет профиль. Отказ выглядел как отказ УЗЛА («доставка не удалась»), и
четыре суточных отказа подряд 19–22.10 имели ту же причину — но их вывод
уничтожался `>/dev/null`, поэтому причина не называлась четверо суток.

Проверяется статически и через запуск блока разрешения под тем самым
минимальным PATH: сеть и узел не нужны.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СКРИПТ = КОРЕНЬ / "automation" / "local" / "k2-deliver-catalog.sh"

# `ansible` в начале команды: после начала строки, `if !`, `$(`, `&&`, `|`.
ГОЛЫЙ_ВЫЗОВ = re.compile(r"(?:^|[;&|(]|\bif\s+!?\s*|\$\(\s*)ansible\s+-")


def _текст() -> str:
    return СКРИПТ.read_text(encoding="utf-8")


def _блок_разрешения(текст: str) -> str:
    начало = текст.index("ansible_bin=")
    конец = текст.index("export PATH", начало) + len("export PATH")
    return текст[начало:конец]


def test_скрипт_существует_и_исполняем():
    assert СКРИПТ.exists(), СКРИПТ
    assert СКРИПТ.stat().st_mode & 0o111, "скрипт зовут из юнита, он должен быть исполняем"


def test_нет_голого_вызова_ansible():
    """Ровно та строка, что падала: `if ! ansible -i ...`."""
    плохие = [(н, с) for н, с in enumerate(_текст().splitlines(), 1)
              if ГОЛЫЙ_ВЫЗОВ.search(с) and "ansible_bin" not in с]
    assert плохие == [], (
        "вызов ansible без разрешённого пути вернёт «command not found» под "
        f"минимальным PATH systemd: {плохие}")


def test_все_вызовы_идут_через_разрешённый_путь():
    текст = _текст()
    # Обе команды ansible в скрипте: copy и raw-сверка сумм.
    assert текст.count('"$ansible_bin" -i "$inventory"') == 2, текст.count('"$ansible_bin"')


def test_отсутствие_ansible_называется_отдельной_ошибкой():
    """«ansible не найден» ≠ «доставка не удалась»: иначе чинят не то.

    Под прежней редакцией отсутствие исполняемого файла печаталось как отказ
    узла, и разбор 23.10 пошёл искать приёмщик на узле, которого там не было.
    """
    блок = _блок_разрешения(_текст())
    assert "не найден" in блок
    assert "exit 2" in блок, "ошибка окружения должна иметь свой код выхода"


def test_разрешение_работает_под_минимальным_PATH_systemd(tmp_path):
    """Положительный контроль: тот самый PATH, при котором был отказ."""
    подложка = tmp_path / "bin"
    подложка.mkdir()
    (подложка / "ansible").write_text("#!/bin/sh\necho ansible-подложка\n", encoding="utf-8")
    (подложка / "ansible").chmod(0o755)
    дом = tmp_path / "home"
    (дом / ".local" / "bin").mkdir(parents=True)
    (дом / ".local" / "bin" / "ansible").symlink_to(подложка / "ansible")

    пр = tmp_path / "resolve.sh"
    пр.write_text(_блок_разрешения(_текст()) + '\necho "НАЙДЕН:$ansible_bin"\n',
                  encoding="utf-8")
    гот = subprocess.run(
        ["/bin/bash", str(пр)], capture_output=True, text=True,
        env={"HOME": str(дом), "PATH": "/usr/local/bin:/usr/bin:/bin"})
    assert гот.returncode == 0, гот.stderr
    assert f"НАЙДЕН:{дом}/.local/bin/ansible" in гот.stdout, гот.stdout


def test_разрешение_отказывает_когда_ansible_нет_нигде(tmp_path):
    """Отрицательный контроль: проверка обязана уметь не найти."""
    пр = tmp_path / "resolve.sh"
    пр.write_text(_блок_разрешения(_текст()), encoding="utf-8")
    гот = subprocess.run(
        ["/bin/bash", str(пр)], capture_output=True, text=True,
        env={"HOME": str(tmp_path / "нет"), "PATH": str(tmp_path / "нет")})
    assert гот.returncode == 2, (гот.returncode, гот.stdout, гот.stderr)
    assert "ansible не найден" in гот.stderr


def test_вывод_ansible_не_уничтожается():
    """Причина отказа должна оставаться в журнале.

    Четыре отказа 19–22.10 не оставили ни одной строки о причине: шаг, на
    котором стоит вся цепочка, был единственным, чей вывод шёл в /dev/null.
    """
    текст = _текст()
    строки_копии = [с for с in текст.splitlines() if "incoming/$site" in с]
    assert строки_копии, "шаг копирования не найден"
    assert not any("/dev/null" in с for с in строки_копии), строки_копии
    assert "copy_log" in текст and "last-copy-failure.log" in текст


def test_PATH_спрашивается_раньше_известных_каталогов(tmp_path):
    """Порядок поиска: сначала PATH, потом запасные каталоги.

    Повод измеренный, 24.10, и это регрессия МОЕГО же исправления. Первая
    редакция брала `~/.local/bin/ansible` раньше PATH — и сломала четыре
    проверки доставки в `test_k2_delivery_one_failure.py`, которые
    подкладывают собственный ansible в PATH: вместо подложки запускался
    настоящий ansible и уходил на живой узел (`UNREACHABLE! … Permission
    denied (publickey)`).

    Если ansible есть в PATH — значит имелся в виду именно он. Известные
    каталоги остаются запасным путём ровно для юнита с урезанным PATH.
    """
    подмена = tmp_path / "в-пути"
    подмена.mkdir()
    (подмена / "ansible").write_text("#!/bin/sh\necho из-PATH\n", encoding="utf-8")
    (подмена / "ansible").chmod(0o755)

    дом = tmp_path / "home"
    (дом / ".local" / "bin").mkdir(parents=True)
    (дом / ".local" / "bin" / "ansible").write_text(
        "#!/bin/sh\necho из-домашнего\n", encoding="utf-8")
    (дом / ".local" / "bin" / "ansible").chmod(0o755)

    пр = tmp_path / "resolve.sh"
    пр.write_text(_блок_разрешения(_текст()) + '\necho "НАЙДЕН:$ansible_bin"\n',
                  encoding="utf-8")
    гот = subprocess.run(
        ["/bin/bash", str(пр)], capture_output=True, text=True,
        env={"HOME": str(дом), "PATH": f"{подмена}:/usr/local/bin:/usr/bin:/bin"})
    assert гот.returncode == 0, гот.stderr
    assert f"НАЙДЕН:{подмена}/ansible" in гот.stdout, (
        "ansible из PATH обязан иметь приоритет над запасными каталогами;"
        f" получено: {гот.stdout}")


def test_ANSIBLE_BIN_сильнее_всего():
    """Явно названный исполняемый файл не переопределяется поиском."""
    блок = _блок_разрешения(_текст())
    assert блок.splitlines()[0].startswith('ansible_bin="${ANSIBLE_BIN:-}"')
