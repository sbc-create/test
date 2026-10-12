"""Ни данных, ни секретов среди файлов, которые Git действительно хранит.

Проверяется индекс, а не рабочий каталог: `config/player.json` обязан лежать
рядом с работающим сайтом и обязан отсутствовать в Git. Отдельно сверяется, что
git отвечает про ЭТОТ проект, иначе распакованное дерево опросило бы
объемлющий репозиторий и прошло проверку, ничего не проверив.

Имени файла недостаточно, и это измерено на живых ячейках: копии этой проверки
в трёх репозиториях AnimeGo искали секрет ВНУТРИ файлов — значение
`publisher_id` и блок приватного ключа, — и находили то, чего список имён не
ловит: секрет, попавший в файл с безобидным названием. Обратное тоже верно: те
копии потеряли сторож про «git отвечает не про этот проект», и их `git
ls-files` при сбое давал пустой список, то есть проверка печатала «чисто», не
проверив ничего. Здесь собрано и то, и другое.

Значение найденного секрета НЕ печатается никогда: называются файл и вид
находки. Отчёт, в который попал сам секрет, — это второй экземпляр утечки.
"""
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ("*.sqlite3", "*.db", "*.dump", "*.sql", ".env", "*.pem", "*.key",
             "player.json", "*-catalog.json", "*-details.json", "*community*.json")

#: Расширения, которые не читаются как текст: искать в них подстроку
#: бессмысленно, а время на больших файлах тратится заметное.
НЕ_ТЕКСТ = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".gz", ".zip",
            ".woff", ".woff2", ".ttf", ".pdf", ".mp4", ".apk"}

#: Что ищется внутри файлов. `publisher_id` — четыре и больше цифр подряд в
#: значении: в коде его быть не может, он принадлежит рабочему окружению
#: (решение D177 — у каждого домена свой).
#:
#: Очевидная подстановка (все цифры одинаковые: 00000, 99999) пропускается
#: нарочно. Проверено 12.10 на живых ячейках: правдоподобное значение в
#: индексе от настоящего не отличить даже сверкой, потому что живой
#: `player.json` лежит с правами 0600 под учётной записью сайта. Поэтому норма
#: такая: подстановка обязана БЫТЬ ВИДНА подстановкой.
ОБРАЗЦЫ = (
    (re.compile(r'"publisher_id"\s*:\s*"\d{4,}"'),
     "значение publisher_id — если это подстановка, сделайте её очевидной "
     "(00000): значение, которое не отличить от настоящего, делает проверку "
     "глазами невозможной"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "приватный ключ"),
    (re.compile(r'"(?:api_token|secret|password)"\s*:\s*"[^"]{8,}"'),
     "значение секрета в JSON"),
)

top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                     text=True, check=False, cwd=ROOT)
if top.returncode != 0 or Path(top.stdout.strip()).resolve() != ROOT:
    print("git отвечает не про этот проект: проверка прошла бы впустую",
          file=sys.stderr)
    sys.exit(1)

tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                         check=False, cwd=ROOT).stdout.split()
bad = [p for p in tracked
       if not p.endswith(".example")
       and any(fnmatch.fnmatch(p.rsplit("/", 1)[-1], pat) for pat in FORBIDDEN)]
if bad:
    print("эти файлы не должны быть в Git:", ", ".join(sorted(bad)), file=sys.stderr)
    sys.exit(1)

# Содержимое проверяется и у файлов с разрешённым именем, включая `.example`:
# настоящий ключ в образце — такой же настоящий ключ.
внутри = []
for отн in tracked:
    путь = ROOT / отн
    if путь.suffix.lower() in НЕ_ТЕКСТ or not путь.is_file():
        continue
    try:
        текст = путь.read_text(encoding="utf-8", errors="replace")
    except OSError as сбой:
        внутри.append(f"{отн}: не прочитан ({type(сбой).__name__})")
        continue
    for образец, что in ОБРАЗЦЫ:
        найдено = образец.search(текст)
        if not найдено:
            continue
        цифры = re.sub(r"\D", "", найдено.group(0)[len('"publisher_id": "'):]) \
            if "publisher_id" in найдено.group(0) else ""
        if цифры and len(set(цифры)) == 1:
            continue  # очевидная подстановка — см. комментарий к ОБРАЗЦЫ
        внутри.append(f"{отн}: {что}")
if внутри:
    print("секрет внутри файлов, которые хранит Git:", file=sys.stderr)
    for строка in sorted(внутри):
        print(f"  — {строка}", file=sys.stderr)
    sys.exit(1)
