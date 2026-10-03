"""Публичный адрес обратной связи объявлен в одном месте и нигде не продублирован.

Доказывает требование `REQ-CELL-CONTACT` (`docs/MASTER_PROMPT_REQUIREMENTS.md`):
ссылка на него обязана быть в тексте теста, иначе прослеженность держится на
имени файла — это и проверяет `tests/test_traceability.py`.

Зачем проверка
--------------

Адрес был объявлен четырьмя независимыми литералами: генератор новых ячеек,
шаблон подвала Lords, манифест проектов Topvisor и приложение Yummy. Пока
значение не менялось, дубли выглядели безобидно. Смена адреса 2026-10-01
показала цену: четыре места — четыре возможности забыть одно, и забытое
всплывает не здесь, а на живой странице, причём только у части витрин.

Проверка держит два разных утверждения, и важно не путать их:

1. прежний адрес не остался НИ ОДНИМ значением — ни в конфигурации витрины, ни
   в коде, ни в профиле. Единственное разрешённое упоминание — исторический
   комментарий в `factory/contact.py`, где сказано, что и на что заменено;
2. каждое объявленное поле контакта равно `factory.contact.ПОЧТА_СЕТИ`.

Чего проверка НЕ делает
-----------------------

Она не ищет «все email в проекте» и не требует, чтобы они совпадали. Адреса
учётных записей, авторизации, Git и уведомлений инфраструктуры — другое
назначение, и массовая замена по совпадению строки запрещена ровно потому, что
совпадение строки не означает совпадение назначения.

Она не подтверждает доставку писем: правильная ссылка и дошедшее письмо —
разные утверждения, второе проверяется только живым человеком.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory import contact

КОРЕНЬ = Path(__file__).resolve().parents[2]

#: Прежний адрес сети. Хранится здесь намеренно: без него проверка «старого не
#: осталось» не умеет назвать, чего именно не должно быть.
ПРЕЖНИЙ = "sbc.claude@yandex.ru"

#: Места, где прежний адрес разрешён, и ПОЧЕМУ. Список короткий намеренно:
#: каждое исключение — это файл, за которым проверка больше не следит.
#:
#: * factory/contact.py — объясняет, что и на что заменено;
#: * этот файл — ему нужно НАЗВАТЬ то, чего не должно быть;
#: * automation/host/contact-email-live-check.py — опрашивает выложенные
#:   витрины и обязан узнавать прежний адрес, иначе не сможет сказать, что он
#:   остался;
#: * шаблон проверки для новых проектов — та же причина, что у самой проверки;
#: * automation/host/apply-contact-email-animego-root.sh — сверяет публичную
#:   страницу после выкладки и обязан узнавать прежний адрес, иначе не отличит
#:   «адрес заменён» от «страницу отдал кэш».
#:
#: Без исключений проверка падала бы на собственном инструментарии, и это был
#: бы отказ об инструменте, а не о сети.
РАЗРЕШЁННЫЕ_УПОМИНАНИЯ = frozenset({
    КОРЕНЬ / "factory" / "contact.py",
    Path(__file__).resolve(),
    КОРЕНЬ / "automation" / "host" / "contact-email-live-check.py",
    КОРЕНЬ / "factory" / "cell" / "check_templates" / "contact_email.py.tmpl",
    КОРЕНЬ / "automation" / "host" / "apply-contact-email-animego-root.sh",
})

#: Где искать. Отчёты, журналы проверок и история переписки не входят: они
#: описывают прошлое, и переписывать прошлое ради зелёного теста неверно.
ОБЛАСТИ = ("factory", "config", "tests", "schemas", "automation")

РАСШИРЕНИЯ = {".py", ".json", ".ts", ".tsx", ".js", ".css", ".yaml", ".yml",
              ".tmpl", ".sh"}


def _файлы():
    for область in ОБЛАСТИ:
        корень = КОРЕНЬ / область
        if not корень.is_dir():
            continue
        for п in корень.rglob("*"):
            if not п.is_file() or п.suffix not in РАСШИРЕНИЯ:
                continue
            if "__pycache__" in п.parts or "node_modules" in п.parts:
                continue
            yield п


def test_адрес_сети_пригоден():
    assert contact.пригоден(contact.ПОЧТА_СЕТИ), contact.ПОЧТА_СЕТИ
    assert contact.ПОЧТА_СЕТИ != ПРЕЖНИЙ


def test_прежнего_адреса_не_осталось():
    """Ни одного значения с прежним адресом — только объяснение замены."""
    нашлось = []
    for п in _файлы():
        if п.resolve() in РАЗРЕШЁННЫЕ_УПОМИНАНИЯ:
            continue
        текст = п.read_text(encoding="utf-8", errors="replace")
        if ПРЕЖНИЙ in текст:
            номера = [n + 1 for n, s in enumerate(текст.split("\n")) if ПРЕЖНИЙ in s]
            нашлось.append(f"{п.relative_to(КОРЕНЬ)}:{номера}")
    assert not нашлось, (
        "прежний адрес обратной связи остался: " + "; ".join(нашлось)
        + f". Он обязан быть заменён на {contact.ПОЧТА_СЕТИ}. Если это не "
        "контакт сайта, а адрес учётной записи или инфраструктуры — такие "
        "адреса в этой замене не участвуют, и файл надо исключить из ОБЛАСТИ "
        "осознанно, а не чинить замену.")


def test_код_не_объявляет_адрес_литералом():
    """Второй литерал адреса сети — это будущий расход копий.

    Проверяется именно ЛИТЕРАЛ рядом с объявлением: сам `factory/contact.py`
    держит значение, остальные обязаны импортировать его.
    """
    нашлось = []
    for п in _файлы():
        if п.resolve() in РАЗРЕШЁННЫЕ_УПОМИНАНИЯ or п.suffix != ".py":
            continue
        if п.name.startswith("test_"):
            continue
        текст = п.read_text(encoding="utf-8", errors="replace")
        for n, строка in enumerate(текст.split("\n"), 1):
            голый = строка.strip()
            if голый.startswith("#"):
                continue
            if f'"{contact.ПОЧТА_СЕТИ}"' in строка or f"'{contact.ПОЧТА_СЕТИ}'" in строка:
                нашлось.append(f"{п.relative_to(КОРЕНЬ)}:{n}")
    assert not нашлось, (
        "адрес вписан литералом вместо импорта factory.contact: "
        + "; ".join(нашлось))


def _ячейки_с_репозиторием():
    реестр = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text(encoding="utf-8"))
    ячейки = реестр.get("cells") or реестр.get("sites") or []
    сп = ячейки if isinstance(ячейки, list) else list(ячейки.values())
    итог = []
    for я in сп:
        путь = (я.get("repo") or {}).get("path") or ""
        if not путь:
            continue
        ф = КОРЕНЬ / путь / "config" / "site.json"
        if ф.is_file():
            итог.append((я.get("site_id") or "?", ф))
    return итог


@pytest.mark.parametrize("site_id,файл", _ячейки_с_репозиторием(),
                         ids=lambda з: з if isinstance(з, str) else "")
def test_у_витрины_адрес_сети(site_id, файл):
    д = json.loads(файл.read_text(encoding="utf-8"))
    assert д.get("contact_email") == contact.ПОЧТА_СЕТИ, (
        f"{site_id}: contact_email={д.get('contact_email')!r}, "
        f"а у сети {contact.ПОЧТА_СЕТИ!r} ({файл})")


def test_профили_витрин_несут_адрес_сети():
    расхождения = []
    for ф in sorted((КОРЕНЬ / "config" / "site-profiles").glob("*.json")):
        д = json.loads(ф.read_text(encoding="utf-8"))
        свой = (д.get("legal_profile") or {}).get("contact_email")
        if свой is None:
            continue
        if свой != contact.ПОЧТА_СЕТИ:
            расхождения.append(f"{ф.name}: {свой!r}")
    assert not расхождения, (
        "профили с чужим адресом обратной связи: " + "; ".join(расхождения))


@pytest.mark.parametrize("site_id,файл", _ячейки_с_репозиторием(),
                         ids=lambda з: з if isinstance(з, str) else "")
def test_проверка_витрины_называет_адрес_сети(site_id, файл):
    """Копия адреса в проверке витрины сторожится отсюда.

    Репозиторий витрины отдельный и импортировать фабрику не может, поэтому
    `checks/contact_email.py` держит значение литералом. Копия без сторожа
    разошлась бы молча: витрина проходила бы свою проверку на прежнем адресе,
    и выпуск считался бы законным.
    """
    проверка = файл.parent.parent / "checks" / "contact_email.py"
    assert проверка.is_file(), (
        f"{site_id}: нет {проверка} — выпуск не проверяет публичную почту")
    текст = проверка.read_text(encoding="utf-8")
    assert f'ОЖИДАЕТСЯ = "{contact.ПОЧТА_СЕТИ}"' in текст, (
        f"{site_id}: {проверка} ожидает не тот адрес. У сети "
        f"{contact.ПОЧТА_СЕТИ!r}; копию надо привести к нему, а не наоборот")


@pytest.mark.parametrize("site_id,файл", _ячейки_с_репозиторием(),
                         ids=lambda з: з if isinstance(з, str) else "")
def test_проверка_почты_стоит_в_пути_выпуска(site_id, файл):
    """Проверка, которую никто не вызывает, выпуск не держит.

    Отдельное утверждение от предыдущего: файл может быть на месте и при этом
    отсутствовать в `checks/run.sh` — тогда релиз пройдёт мимо него.
    """
    бегунок = файл.parent.parent / "checks" / "run.sh"
    assert бегунок.is_file(), f"{site_id}: нет checks/run.sh"
    текст = бегунок.read_text(encoding="utf-8")
    assert "checks/contact_email.py" in текст, (
        f"{site_id}: checks/contact_email.py не вызывается из checks/run.sh — "
        "проверка существует, но выпуск её не исполняет")



class TestНовыйСайт:
    """Новый сайт получает адрес и ИСПОЛНЯЕМУЮ проверку, а не только значение.

    Требование владельца: «новый сайт должен автоматически получать эту почту
    в контактах, подвале и ссылках mailto», и «обновление шаблона или
    повторное развёртывание не должно возвращать старую почту».

    Проверяется поведением генератора, а не чтением его кода: собирается
    настоящий проект во временном каталоге.
    """

    @staticmethod
    def _профили() -> list[str]:
        """Все профили, из которых вообще можно создать сайт.

        Проверять один — значит проверить один. Пул семейства `lords` и есть
        «все используемые семейства» пути создания: у `dle20` и
        `payload-next-multisite` профилей нет, и генератор их не принимает.
        """
        каталог = КОРЕНЬ / "blueprints" / "lords" / "profiles"
        return sorted(p.stem for p in каталог.glob("*.yaml"))

    @staticmethod
    def _собрать(куда, профиль: str = "lords-general"):
        from factory.cell import newsite

        заказ = newsite.Заказ(
            site_id="probe-contact", domain="probe-contact.test",
            profile=профиль, port=9999, family="lords",
            site_name="Проба контакта",
            remote="https://example.invalid/probe.git")
        newsite.создать(заказ, корень=КОРЕНЬ, куда=куда,
                        регистрировать=False, допустить_грязное=True)
        return куда

    def test_каждый_профиль_пула_даёт_адрес_сети(self, tmp_path):
        """Адрес — умолчание для ВСЕХ профилей, а не для того, что проверяли.

        Семь профилей, три из них свободны и будут выданы следующему заказу.
        Профиль, забытый здесь, обнаружился бы на публичной странице нового
        сайта.
        """
        профили = self._профили()
        assert профили, "пул профилей пуст — проверять нечего"
        беды = []
        for n, профиль in enumerate(профили):
            проект = self._собрать(tmp_path / f"p{n}", профиль)
            конфиг = json.loads((проект / "config" / "site.json").read_text(encoding="utf-8"))
            if конфиг.get("contact_email") != contact.ПОЧТА_СЕТИ:
                беды.append(f"{профиль}: адрес {конфиг.get('contact_email')!r}")
            if not (проект / "checks" / "contact_email.py").is_file():
                беды.append(f"{профиль}: нет checks/contact_email.py")
            бегунок = (проект / "checks" / "run.sh").read_text(encoding="utf-8")
            if "checks/contact_email.py" not in бегунок:
                беды.append(f"{профиль}: проверка не вызывается из run.sh")
        assert not беды, "; ".join(беды)

    def test_путь_извлечения_тоже_объявляет_адрес(self):
        """`cell extract` — тоже путь создания проекта, и он адрес не ставил.

        Все семнадцать действующих ячеек созданы извлечением, не генератором.
        Пока `extract` не объявлял `contact_email`, следующий извлечённый
        проект уехал бы БЕЗ адреса, и подвал вышел бы без строки обратной
        связи — при зелёных проверках.
        """
        from factory.cell import extract

        assert extract._адрес_сети() == contact.ПОЧТА_СЕТИ
        тело = extract._проверка_контакта()
        assert "@@АДРЕС@@" not in тело, "метка шаблона осталась неподставленной"
        assert f'ОЖИДАЕТСЯ = "{contact.ПОЧТА_СЕТИ}"' in тело
        # Вызов живёт в шаблоне run.sh, который получают оба пути создания.
        шаблон = (КОРЕНЬ / "factory" / "cell" / "site_checks" / "run.sh").read_text(
            encoding="utf-8")
        assert "checks/contact_email.py" in шаблон, (
            "в шаблоне checks/run.sh нет вызова проверки — извлечённый проект "
            "получил бы файл, который никто не исполняет")

    def test_адрес_попадает_в_конфигурацию(self, tmp_path):
        проект = self._собрать(tmp_path / "проект")
        конфиг = json.loads((проект / "config" / "site.json").read_text(encoding="utf-8"))
        assert конфиг["contact_email"] == contact.ПОЧТА_СЕТИ

    def test_проверка_выдаётся_и_исполняется(self, tmp_path):
        """Файл проверки мало: он должен ВЫЗЫВАТЬСЯ из checks/run.sh.

        Цена известна: сначала генератор писал проверку ДО `add_tooling`,
        который перезаписывает `checks/run.sh` целиком. Проверка лежала в
        проекте и не исполнялась ни разу — ровно тот случай, когда зелёный
        прогон ничего не значит.
        """
        проект = self._собрать(tmp_path / "проект")
        проверка = проект / "checks" / "contact_email.py"
        assert проверка.is_file(), "генератор не выдал checks/contact_email.py"
        тело = проверка.read_text(encoding="utf-8")
        assert f'ОЖИДАЕТСЯ = "{contact.ПОЧТА_СЕТИ}"' in тело
        assert "@@АДРЕС@@" not in тело, "метка шаблона осталась неподставленной"
        бегунок = (проект / "checks" / "run.sh").read_text(encoding="utf-8")
        assert "checks/contact_email.py" in бегунок, (
            "проверка не вызывается из checks/run.sh — выпуск её не исполнит")

    def test_возврат_прежнего_адреса_валит_выпуск(self, tmp_path):
        """Повторное развёртывание с прежним адресом не проходит проверку."""
        import subprocess

        проект = self._собрать(tmp_path / "проект")
        свежий = subprocess.run(["python3", "checks/contact_email.py"],
                                cwd=проект, capture_output=True, text=True)
        assert свежий.returncode == 0, свежий.stderr

        конфиг_файл = проект / "config" / "site.json"
        конфиг = json.loads(конфиг_файл.read_text(encoding="utf-8"))
        конфиг["contact_email"] = ПРЕЖНИЙ
        конфиг_файл.write_text(json.dumps(конфиг, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        испорченный = subprocess.run(["python3", "checks/contact_email.py"],
                                     cwd=проект, capture_output=True, text=True)
        assert испорченный.returncode != 0, (
            "прежний адрес прошёл проверку — выпуск вернул бы старую почту")
        assert ПРЕЖНИЙ in испорченный.stderr
