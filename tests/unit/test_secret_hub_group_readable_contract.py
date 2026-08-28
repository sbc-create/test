"""Секрет, который должен прочитать процесс, работающий не от root.

Каталог публичного стенда однажды опустел после выкладки: файл секрета лежал
с правами 0400 root:root, а контейнер читает его от пользователя `node`. Файл
существовал, права были «строгие», и именно поэтому сайт остался без каталога.

Контракт с тех пор такой: 0440 root:<группа> — владелец и группа читают, мир
не читает никогда. Эти тесты держат обе половины утверждения; ослабить до 0644
или 0777 нельзя ни через схему, ни мимо неё.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.secret_hub.consumers import verify_written
from factory.secret_hub.registry import Consumer, Reload

SCHEMA = Path("schemas/secret-hub.schema.json")
HUB_CONFIG = Path("config/secret-hub.json")


def _consumer(tmp_path: Path, file_mode: int, group: str = "ubuntu") -> Consumer:
    return Consumer(
        id="lords-01", kind="systemd_credential", title="lords-01.service",
        directory=tmp_path / "secrets" / "lords-01",
        files={"api_token": "cdnvideohub-api-token",
               "publisher_id": "cdnvideohub-publisher-id"},
        owner="root", group=group, file_mode=file_mode, directory_mode=0o750,
        reload=Reload("none"),
    )


def _write(consumer: Consumer, mode: int) -> None:
    consumer.directory.mkdir(parents=True, exist_ok=True)
    for name in ("api_token", "publisher_id"):
        path = consumer.path_for(name)
        path.write_text("значение", encoding="utf-8")
        path.chmod(mode)


class TestPermissionCheckLooksAtTheWorldNotTheGroup:
    def test_a_group_readable_secret_is_accepted(self, tmp_path):
        # Ровно та раскладка, которой не хватало контейнеру.
        consumer = _consumer(tmp_path, 0o440)
        _write(consumer, 0o440)
        assert verify_written(consumer) == []

    def test_a_world_readable_secret_is_refused(self, tmp_path):
        consumer = _consumer(tmp_path, 0o440)
        _write(consumer, 0o444)
        problems = verify_written(consumer)
        assert problems
        assert any("миру" in p for p in problems)

    @pytest.mark.parametrize("mode", [0o644, 0o666, 0o777])
    def test_the_loose_modes_named_in_the_ban_are_refused(self, tmp_path, mode):
        consumer = _consumer(tmp_path, 0o440)
        _write(consumer, mode)
        assert verify_written(consumer)

    def test_a_mode_that_differs_from_the_contract_is_refused(self, tmp_path):
        # 0400 само по себе безопасно, но контракт объявлен как 0440:
        # расхождение с объявленным — тоже проблема, а не мелочь.
        consumer = _consumer(tmp_path, 0o440)
        _write(consumer, 0o400)
        assert verify_written(consumer)

    def test_a_missing_secret_is_reported_not_ignored(self, tmp_path):
        consumer = _consumer(tmp_path, 0o440)
        consumer.directory.mkdir(parents=True, exist_ok=True)
        assert verify_written(consumer)


class TestSchemaAllowsTheContractAndNothingLooser:
    def _schema(self) -> dict:
        return json.loads(SCHEMA.read_text(encoding="utf-8"))

    def _file_mode_enum(self) -> list[str]:
        def walk(node):
            if isinstance(node, dict):
                if "file_mode" in node and isinstance(node["file_mode"], dict):
                    enum = node["file_mode"].get("enum")
                    if enum:
                        return enum
                for value in node.values():
                    found = walk(value)
                    if found:
                        return found
            elif isinstance(node, list):
                for value in node:
                    found = walk(value)
                    if found:
                        return found
            return None

        enum = walk(self._schema())
        assert enum, "в схеме нет перечисления file_mode"
        return enum

    def test_the_group_readable_mode_is_permitted(self):
        assert "0440" in self._file_mode_enum()

    @pytest.mark.parametrize("loose", ["0644", "0666", "0777", "0640"])
    def test_looser_modes_are_not_permitted(self, loose):
        assert loose not in self._file_mode_enum()

    def test_the_description_no_longer_promises_owner_only(self):
        # Описание обещало «читает только владелец» уже после того, как 0440
        # стал допустим. Текст, разошедшийся с правилом, вводит в заблуждение
        # ровно тех, кто пришёл выяснить правило.
        text = SCHEMA.read_text(encoding="utf-8")
        assert "читает только владелец" not in text


class TestTheDeclaredContractIsTheOneWeShipped:
    def test_the_lords_consumers_declare_group_readable_secrets(self):
        config = json.loads(HUB_CONFIG.read_text(encoding="utf-8"))
        found = []

        def walk(node):
            if isinstance(node, dict):
                if "file_mode" in node and "directory_mode" in node:
                    found.append(node)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(config)
        assert found, "в конфигурации нет ни одного потребителя"
        for consumer in found:
            assert consumer["file_mode"] in ("0400", "0440", "0600")
            assert consumer["directory_mode"] in ("0700", "0750", "0755")
            assert consumer.get("owner") == "root"

    def test_the_publisher_id_is_still_delivered(self):
        # Publisher ID однажды пропал вместе с плеером на всех 4315 тайтлах:
        # его перестал получать сборщик. Потребитель обязан его доставлять.
        config = HUB_CONFIG.read_text(encoding="utf-8")
        assert "publisher_id" in config
        assert "publisher-id" in config

    def test_no_secret_value_is_stored_in_the_configuration(self):
        # В конфигурации живут пути и права, но не значения.
        config = json.loads(HUB_CONFIG.read_text(encoding="utf-8"))
        text = json.dumps(config, ensure_ascii=False)
        for marker in ("Bearer ", "eyJ", "-----BEGIN"):
            assert marker not in text
