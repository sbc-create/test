#!/usr/bin/env python3
"""Редакционные подборки и анонсы против ТЕКУЩЕГО снимка каталога.

ЗАЧЕМ. Состав подборки выбирает человек однажды, а каталог меняется каждую
ночь. Между выпусками работа может пропасть из снимка, потерять источник
видео или постер; анонс может стать доступным просмотром, а его дата —
пройти. Ни одно из этих событий не видно по коду ответа страницы: она
продолжает отдавать 200.

ЧЕГО ЭТА ПРОВЕРКА НЕ ДЕЛАЕТ. Она ничего не правит и не «добивает» состав.
Поручение владельца 27.10: при отказе источника сохраняется проверенный
состав либо блок скрывается, но случайными карточками он не заполняется.
Поэтому здесь только измерение и перечень — решение за человеком и за
рантаймом, который умеет назвать потерю на самой странице.

ЧТО ПРОВЕРЯЕТСЯ у подборки:

* каждая работа находится в снимке по ПОСТОЯННОМУ id (не по слугу);
* у найденной работы есть источник видео и постер;
* состав соответствует направлению витрины: на аниме-сайте — аниме, на
  витрине фильмов и сериалов — не аниме;
* год в заголовке подборки совпадает с годами состава;
* у промежуточной подборки («лучшее года») есть дата обновления.

ЧТО ПРОВЕРЯЕТСЯ у анонсов:

* работа ещё не доступна к просмотру (иначе это больше не ожидание);
* хотя бы одна объявленная дата не в прошлом;
* у позиции есть официальный источник и человеческое пояснение.

    python3 automation/local/editorial-sets-validate.py            # все витрины
    python3 automation/local/editorial-sets-validate.py --site zona-01 --json
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import gc
import re
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]

#: Витрина → (каталог, подробности, каталог проекта, направление).
#: Направление закрытое: `films_series` или `anime`. Угадывать его по домену
#: нельзя — витрины одной линии бывают разных профилей.
ВИТРИНЫ = {
    "zona-01": ("/srv/zonafilm-space/data/zona-01-catalog.json",
                "/srv/zonafilm-space/data/zona-01-details.json",
                "var/site-repos/zonafilm-space", "films_series"),
    "zona-03": ("/srv/zonafilm12-site/data/zona-03-catalog.json",
                "/srv/zonafilm12-site/data/zona-03-details.json",
                "var/site-repos/zonafilm12-site", "films_series"),
    "animedia-01": ("/srv/animedia-icu/data/animedia-01-catalog.json",
                    "/srv/animedia-icu/data/animedia-01-details.json",
                    "var/site-repos/animedia-icu", "anime"),
}
ЧИСТО, ДЕФЕКТ, НЕ_ИЗМЕРЕНО = "чисто", "найден дефект", "НЕ ИЗМЕРЕНО"


#: Поля подробностей, которые проверки действительно читают. Всё остальное из
#: записи выбрасывается сразу: у `zona-01` подробностей 70 077, и держать их
#: целиком незачем.
НУЖНЫЕ_ПОЛЯ = ("playable", "poster_url", "genres", "year")
#: Поля каталога, которые читают проверки.
НУЖНЫЕ_КАТАЛОГ = ("poster", "year")
#: Сколько текста держать в буфере потокового разбора. Миллион знаков заведомо
#: больше самой длинной записи подробностей и при этом ничтожен против файла.
ШАГ_БУФЕРА = 1 << 20


def _пары_потоком(путь: str, ключ: str):
    """Пары «имя → запись» из большого JSON-объекта, по одной за раз.

    ЗАЧЕМ ПОТОКОМ, а не `json.loads` целиком. Измерено 27.10: у `zona-01`
    файл подробностей 99 МБ, и один только его текст в памяти даёт 406 МБ
    (кириллица в `str` занимает вчетверо против UTF-8), а с разобранным
    объектом пик доходит до 472 МБ. Юнит регулярной проверки живёт под
    `MemoryMax=512M`, поэтому шаг проверки состава обрывался на Zona — это
    сообщила линия, которая этот таймер ведёт. Потоковый разбор держит в
    памяти буфер и накопленный результат, но никогда — весь файл.

    ЧТО ИМЕННО ДЕЛАЕТСЯ. Файл читается кусками; `raw_decode` снимает с буфера
    по одному значению и возвращает, где оно кончилось; разобранная часть
    отбрасывается. Если значение в буфер не поместилось, буфер дочитывается и
    попытка повторяется — поэтому длина записи ограничения не создаёт.

    ЧЕГО НЕ ДЕЛАЕТСЯ: это не общий потоковый парсер JSON. Он знает ровно одну
    форму — объект верхнего уровня, в нём ключ `ключ`, а в нём объект
    «имя → запись». Любая другая форма — исключение, а не молчаливый пропуск:
    молча вернуть пустоту значило бы выдать «дефектов нет» за измерение.
    """
    декодер = json.JSONDecoder()
    with open(путь, encoding="utf-8") as ф:
        буфер = ""
        место = 0

        def дочитать() -> bool:
            nonlocal буфер, место
            кусок = ф.read(ШАГ_БУФЕРА)
            if not кусок:
                return False
            буфер = буфер[место:] + кусок
            место = 0
            return True

        def снять():
            """Одно значение с текущего места; None — не хватило текста."""
            nonlocal место
            while место < len(буфер) and буфер[место] in " \t\r\n":
                место += 1
            if место >= len(буфер):
                return ("мало",)
            try:
                значение, конец = декодер.raw_decode(буфер, место)
            except ValueError:
                return ("мало",)
            место = конец
            return ("есть", значение)

        def символ():
            nonlocal место
            while True:
                while место < len(буфер) and буфер[место] in " \t\r\n":
                    место += 1
                if место < len(буфер):
                    return буфер[место]
                if not дочитать():
                    return ""

        if символ() != "{":
            raise ValueError("подробности: ожидался объект верхнего уровня")
        место += 1
        # Ищем нужный ключ верхнего уровня, остальные значения пропускаем.
        найден = False
        while not найден:
            с = символ()
            if с == ",":
                место += 1
                continue
            if с in ("}", ""):
                raise ValueError(f"подробности: ключа «{ключ}» нет")
            исход = снять()
            while исход[0] == "мало":
                if not дочитать():
                    raise ValueError("подробности: файл кончился на имени ключа")
                исход = снять()
            имя = исход[1]
            if символ() != ":":
                raise ValueError("подробности: после имени ключа нет двоеточия")
            место += 1
            if имя == ключ:
                найден = True
                break
            исход = снять()
            while исход[0] == "мало":
                if not дочитать():
                    raise ValueError("подробности: файл кончился на значении")
                исход = снять()
        if символ() != "{":
            raise ValueError(f"подробности: «{ключ}» не объект")
        место += 1
        while True:
            с = символ()
            if с == ",":
                место += 1
                continue
            if с == "}" or с == "":
                return
            исход = снять()
            while исход[0] == "мало":
                if not дочитать():
                    raise ValueError("подробности: файл кончился на имени записи")
                исход = снять()
            слаг = исход[1]
            if символ() != ":":
                raise ValueError("подробности: после имени записи нет двоеточия")
            место += 1
            исход = снять()
            while исход[0] == "мало":
                if not дочитать():
                    raise ValueError("подробности: файл кончился на записи")
                исход = снять()
            yield слаг, исход[1]


#: Разобранный снимок витрины. Обе проверки — подборок и анонсов — читают один
#: и тот же снимок, и прежде каждая разбирала файлы заново: один и тот же 99-МБ
#: файл читался дважды за прогон.
_СНИМКИ: dict = {}


def _снимок(кат_путь: str, дет_путь: str) -> tuple[dict, dict, dict]:
    ключ = (кат_путь, дет_путь)
    если_есть = _СНИМКИ.get(ключ)
    if если_есть is not None:
        return если_есть
    кат_полный = json.loads(pathlib.Path(кат_путь).read_text(encoding="utf-8"))
    по_слагу = {}
    for з in кат_полный.get("items") or []:
        слаг = з.get("slug")
        if слаг:
            по_слагу[слаг] = {п: з.get(п) for п in НУЖНЫЕ_КАТАЛОГ}
    кат = {"revision": кат_полный.get("revision", "")}
    del кат_полный
    gc.collect()
    по_иденту = {}
    for слаг, о in _пары_потоком(дет_путь, "details"):
        о = о or {}
        идент = str(о.get("id") or "").strip()
        if идент and идент not in по_иденту:
            по_иденту[идент] = (слаг, {п: о.get(п) for п in НУЖНЫЕ_ПОЛЯ})
    _СНИМКИ[ключ] = (кат, по_слагу, по_иденту)
    return _СНИМКИ[ключ]


def _забыть_снимок(кат_путь: str, дет_путь: str) -> None:
    """Снимок витрины больше не нужен — отдать память до следующей.

    Витрины проверяются по очереди, и держать разобранную Zona, пока меряется
    Animedia, незачем.
    """
    _СНИМКИ.pop((кат_путь, дет_путь), None)
    gc.collect()


#: Порог длины вступления — ПОВОД ИЗМЕРИТЬ, а не вердикт. Это главное про
#: него, и спутать одно с другим уже обошлось дорого.
#:
#: Прежде здесь стоял предел 230 со словами «не вкусовое ограничение, а то,
#: что видно числом». Он был выведен из ОДНОГО замера и пропустил дефект:
#: вступление в 202 знака дало низ первого ряда 859 при окне 844 — поймала
#: приёмка, а не эта проверка.
#:
#: Три измерения 27.10 на ширине 390 показывают, почему порог по знакам не
#: чинится подбором числа:
#:   zonafilm.space, лента, 217 знаков → низ ряда 693, запас 151;
#:   animedia.icu, лента, 227 знаков → низ ряда 834, запас 10;
#:   animedia.icu, «на вечер», 202 знака → низ ряда 859, ПРОВАЛ.
#: Внутри ОДНОГО семейства и одной раскладки больший текст занял меньше
#: места: строки переносятся по словам, и число знаков не упорядочивает
#: страницы по высоте. А между семействами разница ещё грубее — у Zona над
#: сеткой меньше содержимого, и тот же текст стоит там вчетверо меньшего
#: запаса.
#:
#: Поэтому превышение порога даёт отдельный исход «требует замера» и НЕ
#: красит витрину дефектом. Единственный вердикт выносит измеренный низ
#: первого ряда — automation/local/collection-visual-check.py на ширине 390;
#: он обязан пройти перед выпуском изменённой страницы подборки.
ПРЕДЕЛ_ВСТУПЛЕНИЯ = 180
#: Справка об источниках занимает строки наравне со вступлением: у «лучшего
#: 2026» она была 187 знаков и съедала две.
ПРЕДЕЛ_СПРАВКИ = 120


def проверить_подборки(ячейка: str) -> dict:
    кат_путь, дет_путь, проект, направление = ВИТРИНЫ[ячейка]
    файл = КОРЕНЬ / проект / "config" / "collections.json"
    итог = {"витрина": ячейка, "файл": str(файл), "подборок": 0, "работ": 0,
            "беды": [], "требует замера": [], "исход": ЧИСТО}
    if not файл.is_file():
        итог["исход"] = НЕ_ИЗМЕРЕНО
        итог["беды"].append("файла подборок нет")
        return итог
    try:
        кат, по_слагу, по_иденту = _снимок(кат_путь, дет_путь)
    except (OSError, ValueError, KeyError) as сбой:
        итог["исход"] = НЕ_ИЗМЕРЕНО
        итог["беды"].append(f"снимок каталога не прочитан: {type(сбой).__name__}")
        return итог
    данные = json.loads(файл.read_text(encoding="utf-8"))
    итог["ревизия каталога"] = кат.get("revision", "")
    for к in данные.get("collections") or []:
        итог["подборок"] += 1
        ключ = к.get("key") or "?"
        годы = set()
        for р in к.get("items") or []:
            итог["работ"] += 1
            идент = str(р.get("id") or "")
            пара = по_иденту.get(идент)
            if not пара:
                итог["беды"].append(
                    f"{ключ}: «{р.get('name')}» (id {идент[:8]}…) пропала из снимка")
                continue
            слаг, о = пара
            з = по_слагу.get(слаг) or {}
            годы.add(int(з.get("year") or о.get("year") or 0))
            if not о.get("playable"):
                итог["беды"].append(f"{ключ}: «{р.get('name')}» без источника видео")
            if not (з.get("poster") or о.get("poster_url")):
                итог["беды"].append(f"{ключ}: «{р.get('name')}» без постера")
            # Числовое утверждение без источника запрещено правилом витрины,
            # а в позиции подборки числом говорит отбор: оценка, число голосов,
            # принадлежность вещателю. Поле названо по-разному в двух поколениях
            # выдачи линии SEO (`basis` и `rating_basis`), и внешняя ссылка
            # (`source_url`) годится наравне с ними. Схема ни одного из трёх не
            # требует, поэтому требование стоит здесь, а не выдаётся за схему.
            if not (р.get("basis") or р.get("rating_basis") or р.get("source_url")):
                итог["беды"].append(
                    f"{ключ}: «{р.get('name')}» без основания отбора — нет ни "
                    "basis, ни rating_basis, ни source_url")
            жанры = {str(ж).lower() for ж in (о.get("genres") or [])}
            аниме = "аниме" in жанры or "дунхуа" in жанры
            if направление == "anime" and not аниме:
                итог["беды"].append(
                    f"{ключ}: «{р.get('name')}» не подходит профилю аниме-витрины")
            if направление == "films_series" and аниме:
                итог["беды"].append(
                    f"{ключ}: «{р.get('name')}» — аниме на витрине фильмов и сериалов")
        в_имени = re.findall(r"\b(20\d\d)\b", str(к.get("title") or ""))
        if len(в_имени) == 1 and годы:
            объявлен = int(в_имени[0])
            чужие = sorted(г for г in годы if г and г != объявлен)
            if чужие:
                итог["беды"].append(
                    f"{ключ}: в заголовке {объявлен}, а в составе годы {чужие}")
        if "лучшее" in str(к.get("title") or "").lower() and not к.get("updated"):
            итог["беды"].append(f"{ключ}: промежуточная подборка без даты обновления")
        # Бюджет текста над сеткой. Измерено 27.10: на телефоне каждая лишняя
        # строка вступления стоит около 21 пикселя, и при 265 знаках первый
        # ряд постеров уезжает за край экрана (852 при окне 844). Справка
        # занимает строки наравне со вступлением. Предел назвала линия SEO,
        # которой этот текст принадлежит, — здесь он только сторожится.
        длина_вступления = len(str(к.get("intro") or ""))
        if длина_вступления > ПРЕДЕЛ_ВСТУПЛЕНИЯ:
            итог["требует замера"].append(
                f"{ключ}: вступление {длина_вступления} знаков при пороге "
                f"{ПРЕДЕЛ_ВСТУПЛЕНИЯ} — измерьте низ первого ряда на 390 "
                "(collection-visual-check.py); порог сам по себе дефектом не "
                "является")
        длина_справки = len(str(к.get("sources_note") or ""))
        if длина_справки > ПРЕДЕЛ_СПРАВКИ:
            итог["требует замера"].append(
                f"{ключ}: справка об источниках {длина_справки} знаков при "
                f"пороге {ПРЕДЕЛ_СПРАВКИ} — измерьте вместе со вступлением")
    if итог["беды"]:
        итог["исход"] = ДЕФЕКТ
    return итог


def проверить_анонсы(ячейка: str, сегодня: str) -> dict:
    кат_путь, дет_путь, проект, _ = ВИТРИНЫ[ячейка]
    файл = КОРЕНЬ / проект / "config" / "announcements.json"
    итог = {"витрина": ячейка, "файл": str(файл), "анонсов": 0, "показано": 0,
            "беды": [], "исход": ЧИСТО}
    if not файл.is_file():
        # Отсутствие файла — рабочее состояние, а не «не измерено»: витрина
        # просто не показывает блок. У аниме-витрины западные премьеры и не
        # должны лежать: профиль решает состав.
        итог["примечание"] = "файла анонсов нет — блок на витрине не показывается"
        return итог
    данные = json.loads(файл.read_text(encoding="utf-8"))
    try:
        _, _, по_иденту = _снимок(кат_путь, дет_путь)
    except (OSError, ValueError, KeyError) as сбой:
        итог["исход"] = НЕ_ИЗМЕРЕНО
        итог["беды"].append(f"снимок каталога не прочитан: {type(сбой).__name__}")
        return итог
    for п in данные.get("items") or []:
        итог["анонсов"] += 1
        имя = str(п.get("name") or "?")
        каталог = п.get("catalog") or {}
        идент = str(каталог.get("id") or "")
        пара = по_иденту.get(идент) if идент else None
        доступно = bool(пара and (пара[1] or {}).get("playable"))
        выпуск = п.get("release") or {}
        даты = [str(выпуск.get("date") or "")]
        второй = выпуск.get("second") or {}
        if второй.get("date"):
            даты.append(str(второй["date"]))
        будущее = any(д >= сегодня for д in даты if д)
        if доступно:
            итог["беды"].append(
                f"«{имя}»: работа уже доступна к просмотру — это не ожидание")
        if not будущее:
            итог["беды"].append(
                f"«{имя}»: все объявленные даты в прошлом ({', '.join(даты)})")
        if not str(п.get("source") or "").startswith("http"):
            итог["беды"].append(f"«{имя}»: нет официального источника")
        if len(str(п.get("reason") or "")) < 20:
            итог["беды"].append(f"«{имя}»: нет человеческого пояснения")
        if not доступно and будущее:
            итог["показано"] += 1
    if итог["беды"]:
        итог["исход"] = ДЕФЕКТ
    if итог["анонсов"] and not итог["показано"]:
        итог["беды"].append("показывать нечего — блок скроется, и это верно: "
                            "заполнять его случайными карточками нельзя")
    return итог


def _normalize_next_stream(body):
    """Reconstruct only the pinned React stream moves; never execute scripts."""
    import hashlib
    import re
    from html.parser import HTMLParser
    # Exact runtime preambles observed in the admitted Next HTML. A runtime
    # upgrade requires a new fixture/review, not permissive JavaScript parsing.
    PREAMBLES = frozenset({'7a3c441a297b4368e7168f53d44323873b11a160d3567f2d4695187785c22646', 'ae43f2863da498ae6e297e928af4b7bb581afa935a8f2f3105606210f5e134c0'})
    call = re.compile(r'\$(RS|RC)\("([SPB]:[0-9a-f]+)","([SPB]:[0-9a-f]+)"\);?')
    void = frozenset('area base br col embed hr img input link meta param source track wbr'.split())
    def fail():
        raise ValueError('unsupported or incomplete Next stream')
    class Node:
        def __init__(self, tag='', raw='', attrs=()):
            self.tag,self.raw,self.attrs,self.children,self.parent=tag,raw,dict(attrs),[],None
    class Tree(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.root=Node();self.stack=[self.root];self.ids={};self.scripts=[];self.count=0
        def add(self,n):
            self.count+=1
            if self.count>100000 or len(self.stack)>256: fail()
            n.parent=self.stack[-1];n.parent.children.append(n)
        def handle_starttag(self,t,a):
            n=Node(t,self.get_starttag_text(),a);self.add(n)
            if len(dict(a))!=len(a): fail()
            ident=n.attrs.get('id')
            if ident:
                if ident in self.ids: fail()
                self.ids[ident]=n
            if t=='script': self.scripts.append(n)
            if t not in void:self.stack.append(n)
        def handle_startendtag(self,t,a):
            self.handle_starttag(t,a)
            if t not in void:self.stack.pop()
        def handle_endtag(self,t):
            if t in void:return
            if len(self.stack)<2 or self.stack[-1].tag!=t:fail()
            n=self.stack.pop()
            if t=='script':n.available=frozenset(self.ids)
        def handle_data(self,s):self.add(Node(raw=s))
        def handle_entityref(self,s):self.handle_data('&'+s+';')
        def handle_charref(self,s):self.handle_data('&#'+s+';')
        def handle_comment(self,s):self.add(Node('!comment','<!--'+s+'-->'))
        def handle_decl(self,s):self.add(Node(raw='<!'+s+'>'))
    if not isinstance(body,str) or len(body.encode())>5000000:fail()
    tree=Tree();tree.feed(body);tree.close()
    if len(tree.stack)!=1:fail()
    moves=[]
    for script in tree.scripts:
        s=''.join(n.raw for n in script.children).strip()
        if not s.startswith(('$RS(', '$RC(', '$RS=function', '$RB=[];')):continue
        if 'src' in script.attrs or script.attrs.get('type','') not in ('','text/javascript','application/javascript'):fail()
        match=call.search(s)
        if not match:fail()
        prefix=s[:match.start()]
        if prefix and hashlib.sha256(prefix.encode()).hexdigest() not in PREAMBLES:fail()
        suffix=s[match.start():]
        while suffix:
            m=call.match(suffix)
            if not m:fail()
            if m.group(2) not in script.available or m.group(3) not in script.available:fail()
            moves.append(m.groups());suffix=suffix[m.end():]
        if len(moves)>1024:fail()
    used=set()
    for kind,left,right in moves:
        source_id,target_id=(left,right) if kind=='RS' else (right,left)
        if not source_id.startswith('S:') or not target_id.startswith('P:' if kind=='RS' else 'B:'):fail()
        if source_id in used or target_id in used:fail()
        source,target=tree.ids.get(source_id),tree.ids.get(target_id)
        if not source or not target or source.tag!='div' or 'hidden' not in source.attrs or target.tag!='template':fail()
        if not source.parent or not target.parent:fail()
        ancestor=target
        while ancestor:
            if ancestor is source:fail()
            ancestor=ancestor.parent
        parent=target.parent;pos=parent.children.index(target);end=pos+1
        if kind=='RC':
            if pos<1 or parent.children[pos-1].raw!='<!--$?-->':fail()
            depth=0
            while end<len(parent.children):
                raw=parent.children[end].raw
                if raw in ('<!--$-->','<!--$?-->','<!--$!-->'):depth+=1
                if raw=='<!--/$-->':
                    if depth==0:break
                    depth-=1
                end+=1
            if end==len(parent.children):fail()
            parent.children[pos-1].raw='<!--$-->'
        source.parent.children.remove(source)
        source.parent=None
        parent.children[pos:end]=source.children
        for n in source.children:n.parent=parent
        source.children=[];target.parent=None;used.update((source_id,target_id))
    def render(n):
        ident=n.attrs.get('id','')
        if re.fullmatch(r'[SPB]:[0-9a-f]+',ident):fail()
        if n.tag=='script':return ''
        if not n.tag:return n.raw+''.join(render(c) for c in n.children)
        if n.tag=='!comment':return n.raw
        opening=n.raw[:-2]+'>' if n.tag not in void and n.raw.endswith('/>') else n.raw
        return opening+''.join(render(c) for c in n.children)+('' if n.tag in void else '</'+n.tag+'>')
    return render(tree.root)


def _next_runtime_context(binding, sources, hashes, read_public, today, now, failure):
    """Explicit immutable Next artifact binding; no Docker or writer capability."""
    import hashlib, json, pathlib, re, subprocess, datetime, time
    started=time.monotonic()
    guard=binding['next_runtime'];site=binding['site_id'];domain=binding['domain']
    if site!='yummy-org' or domain!='yummyani.org':raise failure('Next site binding not admitted')
    if set(sources)!={'watcher','events','manual'}:raise failure('Next source binding incomplete')
    manifest_path=pathlib.Path(guard['manifest_path'])
    if manifest_path.is_symlink():raise failure('Next manifest must be a regular published file')
    manifest_raw=manifest_path.read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest()!=guard['manifest_sha256']:raise failure('Next manifest changed')
    m=json.loads(manifest_raw);commit=guard['expected_commit'];image=guard['expected_image_digest']
    if (m.get('schema')!='k2-next-runtime/1' or m.get('site_id')!=site
            or m.get('source_commit')!=commit or not re.fullmatch('[0-9a-f]{40}',commit)
            or m.get('image_digest')!=image or not re.fullmatch('sha256:[0-9a-f]{64}',image)
            or m.get('source_paths')!=sources or m.get('node_major')!=22):
        raise failure('Next immutable identity differs')
    if subprocess.check_output(['/usr/bin/node','--version'],text=True,timeout=5).strip().split('.')[0]!='v22':
        raise failure('Next helper Node major differs')
    artifact_root=pathlib.Path(guard['artifact_root']).resolve(strict=True)
    if artifact_root.name!=commit:raise failure('Next artifact root is not commit addressed')
    pinned={}
    for name in ('helper','shim','policy'):
        p=pathlib.Path(m[name+'_path'])
        if p.is_symlink() or p.resolve(strict=True).parent!=artifact_root:raise failure('Next helper outside immutable artifact')
        raw=p.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=m[name+'_sha256']:raise failure('Next helper artifact changed')
        pinned[str(p)]=raw
    if (m['policy_path']!=m['helper_path'] or m['policy_sha256']!=m['helper_sha256']
            or pathlib.Path(binding['helper_path']).resolve()!=pathlib.Path(m['shim_path']).resolve()
            or binding['helper_sha256']!=m['shim_sha256']):
        raise failure('Next policy and shim pins differ')
    if guard['public_health_path']!='/api/health?collections=1':raise failure('Next public proof route differs')
    url='https://'+domain+guard['public_health_path'];observation={}
    def public_identity():
        raw=read_public(url)
        if not isinstance(raw,str) or len(raw.encode())>200000:raise failure('Next public proof exceeds bound')
        value=json.loads(raw).get('collections_policy')
        if not isinstance(value,dict):raise failure('Next public proof missing')
        generation={'watcher_sha256':hashes['watcher'],'events_sha256':hashes['events']}
        if (value.get('schema')!='org-home-policy-proof/1' or value.get('site_id')!=site
                or value.get('status')!='ready' or value.get('build_revision')!=commit
                or value.get('policy_sha256')!=m['policy_sha256']
                or value.get('policy_version')!=guard['policy_version']
                or value.get('source_generation')!=generation
                or value.get('manual_fingerprint')!=hashes['manual']):
            raise failure('Next published policy generation differs')
        stamp=datetime.datetime.fromisoformat(value['observed_at'].replace('Z','+00:00'))
        if (stamp.tzinfo is None or stamp.utcoffset()!=datetime.timedelta(0)
                or stamp.date().isoformat()!=today
                or not -60<=((now+datetime.timedelta(seconds=time.monotonic()-started))-stamp).total_seconds()<=180):
            raise failure('Next public proof timestamp not current UTC')
        for field in ('canonical_mapping','base_newest'):
            rows=value.get(field)
            if not isinstance(rows,list) or len(rows)>256:raise failure('Next public mapping exceeds bound')
            ids=set()
            for row in rows:
                if (not isinstance(row,dict) or set(row)!={'id','href'} or not isinstance(row['id'],str)
                        or not row['id'] or row['id'] in ids or not isinstance(row['href'],str)
                        or not re.fullmatch(r'/anime/[a-zA-Z0-9_%.-]+/?',row['href'])):
                    raise failure('Next public mapping invalid')
                import urllib.parse
                segment=row['href'][len('/anime/'):].rstrip('/')
                decoded=urllib.parse.unquote(segment)
                if (re.search(r'%(?![0-9a-fA-F]{2})',segment) or decoded in ('.','..')
                        or any(c in decoded for c in '/\\?#') or any(ord(c)<32 for c in decoded)):
                    raise failure('Next public mapping unsafe path')
                ids.add(row['id'])
        allowed=('schema','site_id','status','build_revision','policy_version','policy_sha256','source_generation','manual_fingerprint','canonical_mapping','base_newest')
        identity={k:value[k] for k in allowed};observation.clear();observation.update(identity,observed_at=value['observed_at'])
        return identity
    identity=public_identity();first_observation=dict(observation)
    def stable():
        if manifest_path.read_bytes()!=manifest_raw:raise failure('Next manifest changed during check')
        if any(pathlib.Path(p).read_bytes()!=raw for p,raw in pinned.items()):raise failure('Next helper changed during check')
    return {'identity':identity,'public_identity':public_identity,'stable':stable,
            'manifest_raw':manifest_raw,'release':artifact_root,
            'helper_sources':dict(sources,_public_observation=first_observation)}


# Deterministic daily adapter. All inputs are read-only; only stdout is produced.
def проверить_суточные_подборки(policy_path, *, now=None, fetch=None, budget_seconds=110, retry_wait=None, _policy_override=None, _retry_source_races=True):
    import hashlib
    import time
    import urllib.request
    import urllib.parse
    from html.parser import HTMLParser

    class CheckFailure(ValueError):
        """Only fixed, secret-free diagnostics generated by this adapter."""
        pass

    now = now or datetime.datetime.now(datetime.timezone.utc)
    today = now.astimezone(datetime.timezone.utc).date().isoformat()
    check_started = time.monotonic()
    deadline = check_started + max(0, budget_seconds)
    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise CheckFailure("daily confirmation time budget exhausted")
        return value
    def read_public(url):
        remaining()
        return (fetch or public_get)(url)
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                         separators=(",", ":")).encode()).hexdigest()
    def stamp(value):
        v = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if v.tzinfo is None:
            raise CheckFailure("timestamp must have timezone")
        return v
    class RegionCards(HTMLParser):
        """Ordered card anchors in exactly one explicitly marked subtree."""
        VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
        def __init__(self, attr, value, card_class, source_guard=False):
            super().__init__(convert_charrefs=True)
            self.attr, self.value, self.card_class = attr, value, card_class
            self.stack, self.hrefs = [], []
            self.region_depth = None
            self.source_guard = source_guard
            self.source_depth = None
            self.source_sections = 0
            self.source_invalid = False
            self.regions = 0
            self.invalid = False
        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            matching = values.get(self.attr) == self.value
            if self.source_guard and tag == "section" and (
                    (self.source_guard == "animedia-01" and values.get("id") == "new-episodes") or
                    (self.source_guard in {"animego-02", "animego-03", "animego-04"} and values.get("data-collection-policy") == "new_episodes")):
                self.source_sections += 1
                if self.source_depth is not None or values.get("data-episode-feed-source") != "snapshot-diff":
                    self.source_invalid = True
                self.source_depth = len(self.stack)
            if matching and self.source_guard and self.source_depth is None:
                self.source_invalid = True
            if matching:
                self.regions += 1
                if self.region_depth is not None or tag in self.VOID:
                    self.invalid = True
                else:
                    self.region_depth = len(self.stack)
            if self.region_depth is not None:
                if len(values) != len(attrs):
                    self.invalid = True
                if tag == "a" and self.card_class in values.get("class", "").split():
                    self.hrefs.append(values.get("href"))
            if tag not in self.VOID:
                self.stack.append(tag)
        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)
            if tag not in self.VOID:
                self.handle_endtag(tag)
        def handle_endtag(self, tag):
            if tag in self.VOID:
                return
            if tag not in self.stack:
                if self.region_depth is not None:
                    self.invalid = True
                return
            pos = len(self.stack) - 1 - self.stack[::-1].index(tag)
            if self.region_depth is not None:
                if pos != len(self.stack) - 1:
                    self.invalid = True
                if pos <= self.region_depth:
                    self.region_depth = None
            if self.source_depth is not None and pos <= self.source_depth:
                self.source_depth = None
            del self.stack[pos:]
        def valid(self):
            return self.regions == 1 and self.region_depth is None and not self.invalid
    def public_get(url):
        class SameOrigin(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                if urllib.parse.urlsplit(newurl)[:2] != urllib.parse.urlsplit(url)[:2]:
                    raise CheckFailure("cross-origin redirect")
                return super().redirect_request(req, fp, code, msg, headers, newurl)
        request = urllib.request.Request(url, headers={"User-Agent": "k2-collections-readonly/1"})
        with urllib.request.build_opener(SameOrigin).open(request, timeout=min(12, remaining())) as response:
            raw = response.read(5_000_001)
            if response.status != 200 or len(raw) > 5_000_000:
                raise CheckFailure("public response failed or too large")
            return raw.decode("utf-8")
    report = {"schema": "collections-public-check-v1", "checked_at": now.isoformat(),
              "policy_day": today, "sites": []}
    try:
        policy = (_policy_override if _policy_override is not None else json.loads(pathlib.Path(policy_path).read_text()))
        if policy.get("schema") != "collections-refresh-bindings-v1":
            raise CheckFailure("unknown binding schema")
        report["coverage"] = policy.get("coverage") or {"network_complete": False}
        entries = policy.get("sites")
        if not isinstance(entries, list) or not entries or len(entries) > 20:
            raise CheckFailure("missing or excessive coverage")
        registry = json.loads(pathlib.Path(policy["registry"]).read_text())
        cells = {c["site_id"]: c for c in registry["cells"]}
        excluded = {"animedia.space", "lordfilm47.space", "lordserials22.site", "lordserials22.space", "lords3rial.site"}
        seen = set()
        for binding in entries:
            site = binding.get("site_id")
            row = {"site_id": site, "measured": False, "healthy": False}
            report["sites"].append(row)
            try:
                if site in seen: raise CheckFailure("duplicate binding")
                seen.add(site)
                cell = cells[site]
                domain = binding["domain"]
                if (domain != cell["domain"] or domain in excluded
                        or cell.get("status") == "retired"
                        or (cell.get("withdrawal") or {}).get("withdrawn")):
                    raise CheckFailure("inactive or mismatched domain")
                if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)+", domain):
                    raise CheckFailure("invalid public domain")
                if binding.get("enabled") is not True:
                    raise CheckFailure("trusted live provenance not admitted")
                sources = dict(binding["sources"])
                optional = binding.get("optional_sources", {})
                if not isinstance(optional, dict) or set(optional)-{"events", "availability"} or set(optional)&set(sources):
                    raise CheckFailure("optional source binding invalid")
                presence = {}
                for name,path in optional.items():
                    p=pathlib.Path(path)
                    try:p.stat();present=True
                    except FileNotFoundError:present=False
                    presence[name]=present
                    if present:sources[name]=path
                is_next = "next_runtime" in binding
                if not isinstance(sources,dict) or (not is_next and not {"catalog","details"}<=set(sources)):
                    raise CheckFailure("source binding missing")
                hashes = {name: hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
                          for name, path in sources.items()}
                row["input_sha256_observed"] = dict(hashes)
                helper_sources = sources
                next_context = None
                if is_next:
                    if "local_runtime" in binding:raise CheckFailure("ambiguous runtime binding")
                    next_context=_next_runtime_context(binding,sources,hashes,read_public,today,
                        now + datetime.timedelta(seconds=time.monotonic()-check_started),CheckFailure)
                    local={};release=next_context["release"];manifest_raw=next_context["manifest_raw"]
                    public_identity=next_context["public_identity"];identity_before=next_context["identity"]
                    helper_sources=next_context["helper_sources"]
                else:
                    local = binding["local_runtime"]
                    current = pathlib.Path(local["current_path"])
                    if not current.is_symlink():
                        raise CheckFailure("local current must be an existing release link")
                    release = current.resolve(strict=True)
                    manifest_raw = (release / "release-manifest.json").read_bytes()
                    manifest = json.loads(manifest_raw)
                    commit = manifest.get("commit") or manifest.get("source_commit")
                    if (manifest.get("site_id") != site or commit != local["expected_commit"]
                            or not re.fullmatch(r"[a-f0-9]{40}", commit or "")):
                        raise CheckFailure("local release identity differs from admitted rollout")
                    catalog = json.loads(pathlib.Path(sources["catalog"]).read_bytes())
                    revision = catalog.get("revision")
                    if catalog.get("site") != site or not revision:
                        raise CheckFailure("catalog identity missing")
                    del catalog
                    details = json.loads(pathlib.Path(sources["details"]).read_bytes())
                    if details.get("site") != site or details.get("catalog_revision") != revision:
                        raise CheckFailure("local source pair differs")
                    del details
                    metadata_url = "https://" + domain + "/__template_version"
                    commit_field = local.get("public_commit_field", "site_repo_commit")
                    if commit_field not in ("site_repo_commit", "live_build_id"):
                        raise CheckFailure("unsupported explicit public identity field")
                    expected_public_commit = (commit if commit_field == "site_repo_commit"
                                              else commit[:12] + "-" + site)
                    def public_identity():
                        raw = read_public(metadata_url)
                        if not isinstance(raw, str) or len(raw.encode()) > 100000:
                            raise CheckFailure("public metadata exceeds bound")
                        value = json.loads(raw)
                        if (value.get(commit_field) != expected_public_commit
                                or value.get("catalog_revision") != revision
                                or value.get("details_catalog_revision") != revision):
                            raise CheckFailure("public and local release/source pair differ")
                        return {k: value[k] for k in (commit_field, "catalog_revision",
                                                    "details_catalog_revision")}
                    identity_before = public_identity()
                helper = pathlib.Path(binding["helper_path"]).resolve(strict=True)
                if not helper.is_relative_to(release):
                    raise CheckFailure("helper is outside the actually serving local release")
                raw = helper.read_bytes()
                if hashlib.sha256(raw).hexdigest() != binding["helper_sha256"]:
                    raise CheckFailure("site policy helper changed")
                # Site helpers may import modules with the same names. A fresh
                # interpreter prevents one site's cached modules serving another.
                import subprocess
                invocation = (
                    "import json,runpy,sys; "
                    "m=runpy.run_path(sys.argv[1],run_name='collections_policy_readonly'); "
                    "print(json.dumps(m['collections_check'](json.loads(sys.argv[2]),sys.argv[3])))"
                )
                proc = subprocess.run([sys.executable, "-B", "-c", invocation,
                                       str(helper), json.dumps(helper_sources), today],
                                      cwd=str(release), capture_output=True, text=True, timeout=min(90, remaining()))
                if proc.returncode or len(proc.stdout.encode()) > 1_000_000:
                    raise CheckFailure("isolated policy helper failed")
                if helper.read_bytes() != raw:
                    raise CheckFailure("policy helper changed during check")
                result = json.loads(proc.stdout)
                if not isinstance(result, dict) or result.get("complete") is not True:
                    raise CheckFailure("policy eligibility incomplete")
                eligible = result["eligible_ids"]
                if not isinstance(eligible, list) or not all(isinstance(x, str) for x in eligible):
                    raise CheckFailure("invalid eligible identities")
                runtime_binding = result.get("required_runtime_binding")
                if runtime_binding is not None and (site not in {"animedia-01", "animego-02", "animego-03", "animego-04"} or runtime_binding != {"episode_feed_source":"snapshot-diff"}):
                    raise CheckFailure("unsupported required runtime binding")
                pages = result["expected_public"]
                if not isinstance(pages, list) or not 1 <= len(pages) <= 8:
                    raise CheckFailure("bounded public expectations missing")
                if runtime_binding is not None and sum(p.get("region",{}).get("value")=="new_episodes" for p in pages)!=1:
                    raise CheckFailure("runtime binding lacks exact episode region")
                fetched = {}
                def assess():
                    defects, public = [], []
                    regions_seen = set()
                    for page in pages:
                        path = page["path"]
                        if not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or "\\" in path:
                            raise CheckFailure("invalid public path")
                        url = "https://" + domain + path
                        if url not in fetched:
                            if len(fetched) >= 4:
                                raise CheckFailure("too many distinct public pages")
                            fetched[url] = read_public(url)
                        body = fetched[url]
                        if not isinstance(body, str) or len(body.encode("utf-8")) > 5_000_000:
                            raise CheckFailure("public response too large")
                        region = page["region"]
                        if (region.get("attr") not in (("data-home-block",) if is_next else ("data-collection-policy",))
                                or not isinstance(region.get("value"), str) or not region["value"]):
                            raise CheckFailure("explicit collection region required")
                        card_class = page["card_class"]
                        if not isinstance(card_class, str) or not re.fullmatch(r"[A-Za-z_][\w-]*", card_class):
                            raise CheckFailure("invalid card class")
                        region_key = (path, region["value"])
                        if region_key in regions_seen:
                            raise CheckFailure("duplicate policy expectation")
                        regions_seen.add(region_key)
                        expected = page["ordered_hrefs"]
                        absent = page.get("absent_region") is True
                        if (not isinstance(expected, list) or (not expected and not absent)
                                or (expected and absent)
                                or not all(isinstance(x, str) and x for x in expected)
                                or len(expected) != len(set(expected))):
                            raise CheckFailure("nonempty deduplicated ordered composition required")
                        source_guard = site if runtime_binding is not None and region["value"] == "new_episodes" else False
                        parsed = RegionCards(region["attr"], region["value"], card_class, source_guard)
                        parsed.feed(_normalize_next_stream(body) if is_next else body); parsed.close()
                        region_ok = (parsed.regions == 0 if absent else parsed.valid())
                        if source_guard:
                            region_ok = region_ok and not parsed.source_invalid and parsed.source_sections <= 1 and (absent or parsed.source_sections == 1)
                        if not region_ok or parsed.hrefs != expected:
                            defects.append({"path": path, "region": region,
                                            "region_valid": region_ok,
                                            "expected": expected, "actual": parsed.hrefs})
                        public.append({"url": url, "region": region,
                                       "ordered_hrefs": parsed.hrefs,
                                       "sha256": hashlib.sha256(body.encode()).hexdigest()})
                    return defects, public
                def stable_inputs():
                    if public_identity()!=identity_before:
                        raise CheckFailure("public/local release changed during check")
                    if next_context:
                        next_context["stable"]()
                    else:
                        if current.resolve(strict=True)!=release:
                            raise CheckFailure("public/local release changed during check")
                        if (release / "release-manifest.json").read_bytes()!=manifest_raw:
                            raise CheckFailure("release manifest changed during check")
                    if any(hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()!=hashes[name]
                           for name,path in sources.items()):
                        raise CheckFailure("source data changed during check")
                    if any(pathlib.Path(optional[name]).exists()!=exists for name,exists in presence.items()):
                        raise CheckFailure("optional source presence changed during check")
                def wait_for_existing_refresh():
                    path = local.get("readiness_path")
                    if path is None:
                        return
                    if path != "/__site":
                        raise CheckFailure("unsupported explicit readiness contract")
                    limit = min(deadline - 1, time.monotonic() + 60)
                    while True:
                        status = json.loads(read_public("https://" + domain + path))
                        freshness = status.get("freshness")
                        if (status.get("site_id") != site or not isinstance(freshness, dict)
                                or type(freshness.get("reload_in_progress")) is not bool):
                            raise CheckFailure("readiness identity or state missing")
                        if not freshness["reload_in_progress"]:
                            if freshness.get("last_error"):
                                # Do not log a runtime-supplied error string or follow it.
                                raise CheckFailure("existing site refresh reports an error")
                            return
                        delay = min(2, limit - time.monotonic())
                        if delay <= 0:
                            raise CheckFailure("existing site refresh did not settle within budget")
                        (retry_wait or time.sleep)(delay)
                defects, public = assess()
                confirmations = 0
                # The existing site's date/mtime refresh may return last-good HTML
                # once while rebuilding. GET triggers that existing path; wait only
                # for a bounded confirmation, never write or fabricate content.
                while defects and confirmations < 2:
                    wait_for_existing_refresh()
                    stable_inputs()
                    if remaining() <= 1:
                        raise CheckFailure("daily confirmation time budget exhausted")
                    (retry_wait or time.sleep)(1)
                    for path in {defect["path"] for defect in defects}:
                        url = "https://" + domain + path
                        fetched[url] = read_public(url)
                    defects, public = assess()
                    confirmations += 1
                stable_inputs()
                if runtime_binding is not None:
                    episode_page = next(p for p in pages if p["region"]["value"] == "new_episodes")
                    episode_url = "https://" + domain + episode_page["path"]
                    fetched[episode_url] = read_public(episode_url)
                    defects, public = assess()
                    stable_inputs()
                # Recompute every day, including 90/180-day boundaries. The stable
                # composition identity changes only when the policy result changes.
                composition = {"eligible_ids": eligible, "expectations": pages,
                               "manual_fingerprint": result["manual_fingerprint"],
                               "policy_version": result["policy_version"]}
                fingerprint = digest(composition)
                row.update(measured=True, healthy=not defects, fingerprint=fingerprint,
                           eligible_fingerprint=digest(eligible), composition=composition,
                           helper_sha256=binding["helper_sha256"],
                           defects=defects, public=public, source_sha256=hashes, optional_source_presence=presence,
                           refresh_confirmations=confirmations,
                           local_release=str(release), public_identity=identity_before,
                           manifest_sha256=hashlib.sha256(manifest_raw).hexdigest())
            except Exception as exc:
                # Report type/reason, not paths, response bodies, or secret-bearing exception URLs.
                row["reason"] = str(exc) if isinstance(exc, CheckFailure) else type(exc).__name__
                row["reason_code"] = "CHECK_REJECTED" if isinstance(exc, CheckFailure) else "SOURCE_UNAVAILABLE"
        if _retry_source_races:
            # An ordinary producer may atomically replace a paired source during
            # measurement. Retry only that site's full proof once, never others.
            race_reasons = {"source data changed during check", "optional source presence changed during check"}
            for index, failed in enumerate(report["sites"]):
                if failed.get("measured") or failed.get("reason") not in race_reasons:
                    continue
                available = deadline - time.monotonic() - 1
                if available <= 1:
                    failed["source_race_retry"] = "remaining budget exhausted"
                    continue
                scoped = dict(policy)
                scoped["sites"] = [b for b in entries if b.get("site_id") == failed["site_id"]]
                retried = проверить_суточные_подборки(
                    policy_path, now=now + datetime.timedelta(seconds=time.monotonic()-check_started),
                    fetch=fetch, budget_seconds=available, retry_wait=retry_wait,
                    _policy_override=scoped, _retry_source_races=False)
                if retried.get("policy_day") != report["policy_day"]:
                    failed["source_race_retry"] = "UTC policy day changed"
                    continue
                rows = retried.get("sites", [])
                if len(rows) == 1 and rows[0].get("site_id") == failed["site_id"]:
                    replacement = rows[0]
                    replacement["source_race_attempts"] = [dict(failed)]
                    report["sites"][index] = replacement
                else:
                    failed["source_race_retry"] = "fresh proof unavailable"
        measured = bool(report["sites"]) and all(r["measured"] for r in report["sites"])
        report["measured"] = measured
        report["healthy"] = measured and all(r["healthy"] for r in report["sites"])
        report["fingerprint"] = digest([(r["site_id"], r.get("fingerprint")) for r in report["sites"]])
    except Exception as exc:
        report.update(measured=False, healthy=False, reason=str(exc) if isinstance(exc, CheckFailure) else type(exc).__name__)
    return report


def главная(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--site", action="append", default=[],
                   choices=sorted(ВИТРИНЫ), help="по умолчанию — все витрины")
    р.add_argument("--json", action="store_true")
    р.add_argument("--policy-bindings", default="")
    р.add_argument("--policy-budget-seconds", type=float, default=110)
    р.add_argument("--today", default="",
                   help="дата сравнения дат анонсов (по умолчанию сегодня, UTC)")
    а = р.parse_args(аргв)
    if а.policy_bindings:
        if not 1 <= а.policy_budget_seconds <= 590:
            р.error("policy budget must be between 1 and 590 seconds")
        report = проверить_суточные_подборки(а.policy_bindings, budget_seconds=а.policy_budget_seconds)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if report.get("healthy") else 1 if report.get("measured") else 2
    сегодня = а.today or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    витрины = а.site or sorted(ВИТРИНЫ)
    отчёт = {"измерено": datetime.datetime.now(datetime.timezone.utc)
             .strftime("%Y-%m-%dT%H:%M:%SZ"), "сегодня": сегодня, "витрины": []}
    дефектов = не_измерено = поводов = 0
    for ячейка in витрины:
        подборки = проверить_подборки(ячейка)
        анонсы = проверить_анонсы(ячейка, сегодня)
        # Снимок этой витрины больше не нужен. Без этого разобранная Zona
        # оставалась бы в памяти, пока меряется следующая витрина, и пик
        # прогона равнялся бы сумме, а не самой тяжёлой из них.
        кат_путь, дет_путь, _, _ = ВИТРИНЫ[ячейка]
        _забыть_снимок(кат_путь, дет_путь)
        отчёт["витрины"].append({"витрина": ячейка, "подборки": подборки,
                                 "анонсы": анонсы})
        поводов += len(подборки.get("требует замера") or [])
        for часть in (подборки, анонсы):
            дефектов += int(часть["исход"] == ДЕФЕКТ)
            не_измерено += int(часть["исход"] == НЕ_ИЗМЕРЕНО)
    if а.json:
        print(json.dumps(отчёт, ensure_ascii=False, indent=1))
    else:
        for в in отчёт["витрины"]:
            п, ан = в["подборки"], в["анонсы"]
            print(f"== {в['витрина']}: подборок {п['подборок']}, работ {п['работ']} "
                  f"→ {п['исход']}; анонсов {ан['анонсов']}, показывается "
                  f"{ан['показано']} → {ан['исход']}")
            for б in п["беды"] + ан["беды"]:
                print(f"   - {б}")
            # Поводы измерить печатаются ОТДЕЛЬНО и всегда. Молча копить их
            # нельзя: так и выглядит проверка, которая ничего не говорит, —
            # а порог по знакам уже успел и пропустить дефект, и покраснеть
            # зря на двенадцати живых страницах.
            for з in п.get("требует замера") or []:
                print(f"   ? {з}")
        print(f"\nитог: витрин {len(отчёт['витрины'])}, с дефектом {дефектов}, "
              f"не измерено {не_измерено}, требует замера {поводов}")
    if не_измерено:
        return 2
    return 1 if дефектов else 0


if __name__ == "__main__":
    raise SystemExit(главная())
