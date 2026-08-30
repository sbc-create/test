"""Drop-in'ы обновления каталога Lords живут в репозитории и стерегутся.

До сих пор они лежали только на диске. Один такой файл пережил правку, о которой
не знал никто: интервал таймера подняли, а сам таймер запустить забыли — и
автообновление каталога молча перестало происходить, тогда как витрины
продолжали отвечать 200. Проверки ниже стерегут именно то, что тогда сломалось.
"""
import re
from pathlib import Path

import pytest

from factory.paths import PATHS

DROPINS = PATHS.root / "automation" / "host" / "systemd" / "dropins"
SERVICE_D = DROPINS / "lords-content-refresh.service.d"
TIMER_D = DROPINS / "lords-content-refresh.timer.d"


def значение(path: Path, ключ: str) -> str:
    """Действующее значение настройки, как его понял бы systemd.

    Побеждает последнее непустое присваивание. Пустое — это сброс списка
    (`OnUnitActiveSec=`), а не значение: без такого сброса настройка из
    основного unit-файла остаётся в силе, и таймер срабатывает дважды.
    Наивный разбор «первое совпадение» возвращал здесь пустую строку.
    """
    найдено: str | None = None
    for строка in path.read_text(encoding="utf-8").splitlines():
        строка = строка.strip()
        if строка.startswith(f"{ключ}="):
            хвост = строка.split("=", 1)[1].strip()
            if хвост:
                найдено = хвост
    if найдено is None:
        raise AssertionError(f"в {path.name} нет непустого {ключ}")
    return найдено


def секунды(значение_времени: str) -> int:
    единицы = {"s": 1, "min": 60, "h": 3600, "d": 86400}
    совпадение = re.fullmatch(r"(\d+)(s|min|h|d)?", значение_времени)
    assert совпадение, f"непонятная длительность: {значение_времени}"
    число, единица = совпадение.groups()
    return int(число) * единицы.get(единица or "s", 1)


class TestDropinЕстьВРепозитории:
    def test_каталог_drop_in_существует(self):
        assert DROPINS.is_dir(), "drop-in'ы обязаны храниться в репозитории, а не только на диске"

    @pytest.mark.parametrize("файл", ["timeout.conf", "retention.conf"])
    def test_файлы_службы_на_месте(self, файл):
        assert (SERVICE_D / файл).is_file()

    def test_файл_таймера_на_месте(self):
        assert (TIMER_D / "interval.conf").is_file()

    def test_установщик_ставит_drop_in(self):
        """Файл в репозитории, который никто не ставит, — не управление, а заметка."""
        установщик = (PATHS.root / "automation" / "host" / "install-units.sh").read_text(
            encoding="utf-8"
        )
        assert "dropins" in установщик
        assert "systemctl daemon-reload" in установщик


class TestИзмеренныеЗначения:
    def test_таймаут_вмещает_три_витрины(self):
        """Рендер одной витрины занял 2 ч 33 мин; витрин три.

        Прежние три часа убивали прогон на второй витрине: первая получала
        полный каталог, две другие оставались на прежних релизах.
        """
        предел = секунды(значение(SERVICE_D / "timeout.conf", "TimeoutStartSec"))
        одна_витрина = 2 * 3600 + 33 * 60
        assert предел >= 3 * одна_витрина, (
            f"предел {предел} с меньше трёх витрин по {одна_витрина} с"
        )

    def test_шаг_таймера_превышает_цикл(self):
        """Иначе запуски выстраиваются в очередь, а свежесть только ухудшается."""
        предел = секунды(значение(SERVICE_D / "timeout.conf", "TimeoutStartSec"))
        шаг = секунды(значение(TIMER_D / "interval.conf", "OnUnitActiveSec"))
        assert шаг > предел, f"шаг {шаг} с не больше длительности цикла {предел} с"

    def test_хранится_два_релиза(self):
        """Релиз с полным каталогом — около 1,6 ГБ; четыре копии на трёх сайтах не влезают."""
        assert значение(SERVICE_D / "retention.conf", "Environment") == "LORDS_KEEP_RELEASES=2"

    def test_пропущенный_запуск_навёрстывается(self):
        assert значение(TIMER_D / "interval.conf", "Persistent") == "true"


class TestОбъясненияНеПотеряны:
    """Значение без причины через месяц выглядит произволом и его правят наугад."""

    @pytest.mark.parametrize(
        "путь", [SERVICE_D / "timeout.conf", SERVICE_D / "retention.conf",
                 TIMER_D / "interval.conf"]
    )
    def test_каждый_файл_объясняет_своё_число(self, путь):
        текст = путь.read_text(encoding="utf-8")
        комментарии = [s for s in текст.splitlines() if s.strip().startswith("#")]
        assert len(комментарии) >= 3, f"{путь.name}: число без объяснения"

    def test_временность_восьмичасового_предела_записана(self):
        """Восемь часов — восстановление, а не решение свежести."""
        текст = (SERVICE_D / "timeout.conf").read_text(encoding="utf-8")
        assert "временное восстановление" in текст
        assert "02B" in текст, "должно быть сказано, чем это заменяется"


class TestСбросСписковыхНастроек:
    """`OnUnitActiveSec` — список, а не одиночная настройка.

    Без пустого присваивания перед своим значением значение из основного
    unit-файла остаётся в силе, и таймер срабатывает и через десять минут, и
    через девять часов. Проверено на живом хосте: `systemctl cat` показывал обе
    строки сразу.
    """

    def test_интервал_сбрасывается_перед_установкой(self):
        строки = [
            s.strip()
            for s in (TIMER_D / "interval.conf").read_text(encoding="utf-8").splitlines()
            if s.strip().startswith("OnUnitActiveSec=")
        ]
        assert строки[0] == "OnUnitActiveSec=", (
            "перед своим значением обязан идти сброс списка, иначе останется чужое"
        )
        assert len(строки) >= 2 and строки[-1] != "OnUnitActiveSec="


class TestХукСторожа:
    """Хук, который не может выполниться, — не наблюдение, а его видимость.

    Проверено на живом хосте: команда из ExecStopPost падала с
    ModuleNotFoundError, потому что модуля нет в выложенном репозитории.
    Дефис перед командой проглатывал отказ молча.
    """

    ХУК = SERVICE_D / "watchdog.conf"

    def test_хук_описан(self):
        assert self.ХУК.is_file()

    def test_отказ_сторожа_не_валит_прогон(self):
        """Сторож сообщает о состоянии, а не создаёт его."""
        команда = значение(self.ХУК, "ExecStopPost")
        assert команда.startswith("-"), (
            "без дефиса ненулевой код сторожа объявил бы прогон неудавшимся"
        )

    def test_модуль_из_хука_существует_в_репозитории(self):
        """Путь в юните и раскладка репозитория обязаны совпадать."""
        команда = значение(self.ХУК, "ExecStopPost")
        assert "factory.lords.refresh_watchdog" in команда
        assert (PATHS.root / "factory" / "lords" / "refresh_watchdog.py").is_file()

    def test_сказано_что_мёртвый_таймер_так_не_ловится(self):
        """Если таймер не тикает, служба не стартует, и хук не вызывается."""
        текст = self.ХУК.read_text(encoding="utf-8")
        assert "мёртвый таймер" in текст
        assert "независимая периодическая проверка" in текст
