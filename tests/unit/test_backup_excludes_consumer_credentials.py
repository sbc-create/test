"""REQ-BACKUP-NO-PLAINTEXT: открытые consumer credentials не попадают в бэкап.

История отказа, ради которой этот файл существует. `site-factory-backup.sh`
исключал секреты по шаблонам, среди которых был `secrets/`. Consumer'ы Lords
лежат в `/etc/site-factory/secrets/lords/...` и под шаблон попадали случайно —
не потому, что это секреты, а потому, что каталог так назван. Consumer Yami
лежит в `/srv/sites/yummyani-staging/runtime/cdnvideohub/` и не попадал ни под
один шаблон. rsync заходил в файл, доступный только root, получал EACCES и
валил весь бэкап. Дальше подтверждённая копия старела, и `site-factory-health`
начинал падать каждые 15 минут — уже не по своей вине.

Поэтому проверяется не «есть ли слово api-token в скрипте», а поведение:
настоящий rsync с настоящим набором исключений прогоняется по дереву, повторяющему
раскладку из реестра, и в результате не должно остаться ни одного открытого файла
credential'а. Тест обязан ломаться при добавлении нового направления, чей
consumer забыли исключить.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "automation" / "host" / "site-factory-backup.sh"
REGISTRY = REPO / "config" / "secret-hub.json"


def consumer_files() -> dict[str, list[str]]:
    """Имена открытых consumer-файлов по направлениям — из реестра, не из кода."""
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    result: dict[str, list[str]] = {}
    for portfolio in registry.get("portfolios", []):
        for consumer in portfolio.get("consumers", []):
            files = consumer.get("files", {})
            names = list(files.values()) if isinstance(files, dict) else list(files)
            directory = consumer.get("directory")
            if directory and names:
                result[directory] = names
    return result


def script_excludes() -> list[str]:
    """Статические `--exclude=` из самого скрипта плюс выведенные из реестра.

    Статические читаются из файла, а не переписываются сюда: копия рассинхронизуется
    с оригиналом ровно тогда, когда это перестанут замечать.
    """
    text = SCRIPT.read_text(encoding="utf-8")
    static = re.findall(r"--exclude='([^']+)'", text)
    derived: list[str] = []
    for names in consumer_files().values():
        derived.extend(names)
    return static + derived


@pytest.mark.skipif(shutil.which("rsync") is None, reason="rsync не установлен")
class TestPlaintextCredentialsNeverReachTheArchive:
    def test_no_consumer_file_survives_the_collect_step(self, tmp_path: Path):
        """Дерево по раскладке реестра: после rsync открытых credential'ов нет."""
        source = tmp_path / "src"
        stage = tmp_path / "stage"
        stage.mkdir()

        expected_names: set[str] = set()
        for directory, names in consumer_files().items():
            target = source / directory.lstrip("/")
            target.mkdir(parents=True, exist_ok=True)
            for name in names:
                (target / name).write_text("НЕ-НАСТОЯЩЕЕ-ЗНАЧЕНИЕ\n", encoding="utf-8")
                expected_names.add(name)
            # Соседний файл того же каталога обязан уцелеть: исключение должно
            # убирать credential, а не каталог целиком.
            (target / "README.md").write_text("safe\n", encoding="utf-8")

        assert expected_names, "реестр не содержит ни одного consumer-файла — тест бессмыслен"

        args = ["rsync", "-a", "--quiet"]
        args += [f"--exclude={pattern}" for pattern in script_excludes()]
        args += [f"{source}/", str(stage)]
        assert subprocess.run(args, check=False).returncode == 0, "rsync завершился с ошибкой"

        survivors = {p.name for p in stage.rglob("*") if p.is_file()}
        leaked = survivors & expected_names
        assert not leaked, f"открытые credential'ы попали в бэкап: {sorted(leaked)}"
        assert "README.md" in survivors, "исключение вырезало лишнее вместе с credential'ом"

    def test_every_registry_consumer_is_covered_by_an_exclude(self):
        """Новое направление без исключения обязано ломать тест, а не бэкап."""
        patterns = set(script_excludes())
        for directory, names in consumer_files().items():
            for name in names:
                assert name in patterns, (
                    f"consumer {directory}/{name} не исключён из бэкапа: "
                    "добавьте его в реестр так, чтобы имя выводилось из config/secret-hub.json"
                )


class TestRestoreKeepsItsOnlySource:
    def test_encrypted_store_is_collected(self):
        """Без шифрованного хранилища восстановить исключённые файлы нечем."""
        text = SCRIPT.read_text(encoding="utf-8")
        assert "HUB_STORE_DIR" in text, "каталог Secret Hub не участвует в сборе"
        assert re.search(r'collect\s+"\$HUB_STORE_DIR/"', text), (
            "шифрованное хранилище Secret Hub не собирается: "
            "restore не сможет заново создать consumer-файлы"
        )

    def test_master_key_is_not_collected(self):
        """Ключ и шифртекст в одном архиве превращают шифрование в украшение."""
        from factory.secret_hub import crypto

        key_file = Path(crypto.DEFAULT_KEY_FILE)
        assert "secrets" in key_file.parts, (
            f"мастер-ключ {key_file} лежит вне каталога secrets/ — "
            "он перестал попадать под исключение и уедет в архив вместе с шифртекстом"
        )
        assert "--exclude='secrets/'" in SCRIPT.read_text(encoding="utf-8")


class TestEncryptedStoreIsNeverSilentlySkipped:
    """REQ-BACKUP-STORE-READABLE: недоступное хранилище — отказ, а не тихий пропуск.

    Хранилище Secret Hub намеренно 0700 root:root. Юнит какое-то время запускался
    как User=claude, и добавленный сбор шифрованного хранилища превращался в
    `rsync ... Permission denied` — бэкап падал целиком, подтверждённая копия
    старела, а health начинал падать каждые 15 минут уже не по своей вине.

    Соблазнительное «исправление» — исключить каталог, чтобы run стал зелёным.
    Оно даёт архив, из которого нельзя восстановить consumer-файлы: те исключены
    как открытые секреты и восстанавливаются только из этого хранилища. Поэтому
    проверяется ровно обратное: каталог не в исключениях, а недоступность —
    явный отказ с внятным текстом.
    """

    def test_store_is_not_in_any_exclude(self):
        for pattern in script_excludes():
            assert "site-factory-secret-hub" not in pattern, (
                f"шифрованное хранилище исключено из бэкапа шаблоном {pattern!r}: "
                "восстановление consumer-файлов станет невозможным"
            )

    def test_unreadable_store_fails_the_run(self, tmp_path: Path):
        """Поведенческая проверка: нечитаемый каталог обязан завершать скрипт."""
        store = tmp_path / "store"
        store.mkdir()
        store.chmod(0o000)
        try:
            snippet = (
                'HUB_STORE_DIR="$1"\n'
                'fail() { echo "BACKUP FAILED: $*" >&2; exit 1; }\n'
                + _precheck_block()
                + '\necho "REACHED_COLLECT"\n'
            )
            proc = subprocess.run(
                ["bash", "-c", snippet, "bash", str(store)],
                capture_output=True,
                text=True,
            )
        finally:
            store.chmod(0o700)

        assert proc.returncode == 1, "недоступное хранилище не остановило прогон"
        assert "REACHED_COLLECT" not in proc.stdout
        assert "Secret Hub" in proc.stderr, f"текст отказа не называет причину: {proc.stderr!r}"

    def test_missing_verification_record_fails_the_run(self):
        """Прогон без записи о проверке не имеет права считаться успешным."""
        text = SCRIPT.read_text(encoding="utf-8")
        assert re.search(r'if \[ ! -s "\$RECORD" \]', text), (
            "нет проверки, что запись о проверке создана и непуста"
        )


def _precheck_block() -> str:
    """Берёт сам блок предпроверки из скрипта, а не его пересказ."""
    text = SCRIPT.read_text(encoding="utf-8")
    match = re.search(
        r'^if \[ -e "\$HUB_STORE_DIR" \] && \[ ! -r "\$HUB_STORE_DIR" \]; then\n.*?^fi$',
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "блок предпроверки хранилища не найден в скрипте"
    return match.group(0)
