#!/usr/bin/env python3
"""Сообщество на живом экземпляре: голос, комментарий, модерация."""
import http.cookiejar, json, re, sys, urllib.error, urllib.parse, urllib.request

БАЗА = "http://127.0.0.1:9190"
СТРАНИЦА = "/title/kino-000/"
итог, провалы = [], []

def проверка(имя, условие, подр=""):
    итог.append((имя, "PASS" if условие else "FAIL", подр))
    if not условие: провалы.append(имя)

def клиент():
    jar = http.cookiejar.CookieJar()
    o = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),
                                    НеСледовать())
    return o, jar

class НеСледовать(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def get(o, путь):
    зпр = urllib.request.Request(БАЗА + urllib.parse.quote(путь, safe="/?=&#"))
    try:
        with o.open(зпр, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")

def post(o, путь, поля):
    данные = urllib.parse.urlencode(поля).encode()
    зпр = urllib.request.Request(БАЗА + путь, data=данные,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with o.open(зпр, timeout=30) as r:
            return r.status, r.headers.get("Location", "")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location", "")

def скрытые(html):
    """Скрытые поля любой формы сообщества.

    У проголосовавшего формы оценки нет — она заменена результатом, — поэтому
    берётся форма комментария: скрытые поля у них одинаковые.
    """
    for метка in ('data-community-form="vote"', 'data-community-form="comment"'):
        if метка in html:
            б = html.split(метка, 1)[1]
            return dict(re.findall(
                r'name="(subject|slug|back|csrf)" value="([^"]*)"', б))
    raise AssertionError("ни одной формы сообщества на странице")

# --- чистое хранилище --------------------------------------------------------
#
# Проверка создаёт свои голоса и сообщения, поэтому начинает с пустого
# ИЗОЛИРОВАННОГО хранилища этого экземпляра. Живых файлов сообщества здесь
# не открывается ни одного.
import os, signal, subprocess, time
ХРАНИЛИЩЕ = ("/tmp/claude-1001/-home-claude/9e5d5d7c-1b72-454b-9239-dbb120e73b48"
             "/scratchpad/lords-90-data/lords-90-community.json")
assert "/scratchpad/" in ХРАНИЛИЩЕ, "хранилище не изолировано"
if os.path.exists(ХРАНИЛИЩЕ):
    os.remove(ХРАНИЛИЩЕ)
    # Витрина открывает хранилище один раз на процесс: после удаления файла
    # её надо поднять заново, иначе она продолжит писать в снятый inode.
    ПРОЕКТ = ("/tmp/claude-1001/-home-claude/9e5d5d7c-1b72-454b-9239-dbb120e73b48"
              "/scratchpad/new-lords-90")
    ДАННЫЕ = os.path.dirname(ХРАНИЛИЩЕ)
    for pid in subprocess.run(["pgrep", "-f", "lords-frontend.py --port 9190"],
                              capture_output=True, text=True).stdout.split():
        os.kill(int(pid), signal.SIGTERM)
    time.sleep(2)
    subprocess.Popen([sys.executable, f"{ПРОЕКТ}/run.py", "--port", "9190",
                      "--data-dir", ДАННЫЕ], cwd=ПРОЕКТ,
                     env=dict(os.environ,
                              LORDS_90_COMMUNITY_MODERATOR_KEY="test-moderator-key-9190"),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            urllib.request.urlopen(БАЗА + "/healthz", timeout=5); break
        except Exception:
            time.sleep(0.5)

# --- посетитель A: голос ----------------------------------------------------
A, jarA = клиент()
код, стр = get(A, СТРАНИЦА)
проверка("страница отдана", код == 200)
проверка("кука посетителя выдана", any(c.name == "lords_90_v" for c in jarA), 
         str([c.name for c in jarA]))
поля = скрытые(стр)
проверка("тема — постоянный идентификатор", поля["subject"] == "cvh-kino-000", поля["subject"])
код, куда = post(A, "/community/vote", dict(поля, value="8"))
проверка("голос принят 303", код == 303 and "community=ok" in (куда or ""), f"{код} {куда}")
_, стр = get(A, СТРАНИЦА)
проверка("свой голос показан", 'data-my-vote="8"' in стр)
проверка("среднее и число голосов", 'data-community-score="8,0"' in стр
         and 'data-community-votes="1"' in стр)
проверка("формы смены оценки нет", 'data-rating="done"' in стр
         and 'action="/community/vote"' not in стр.split('id="community"',1)[1].split("</section>")[0])
проверка("подпись про неизменность", "не меняется" in стр)

# попытка сменить
поля2 = dict(поля)
код, куда = post(A, "/community/vote", dict(поля2, value="3"))
проверка("смена голоса отвергнута", "community=error" in (куда or ""), str(куда))
_, стр = get(A, СТРАНИЦА)
проверка("голос не изменился", 'data-my-vote="8"' in стр)

# --- комментарий ------------------------------------------------------------
код, куда = post(A, "/community/comment",
                 dict(поля, name="Автор", text="Первое сообщение проверки"))
проверка("комментарий принят", "community=ok" in (куда or ""), str(куда))
_, стрA = get(A, СТРАНИЦА)
проверка("автор видит своё ожидающее", "На проверке — видно только вам" in стрA)
ид = re.search(r'data-comment-id="([^"]+)"', стрA)
проверка("сообщение в ленте автора", bool(ид))

# --- посторонний не видит ---------------------------------------------------
B, _ = клиент()
_, стрB = get(B, СТРАНИЦА)
проверка("постороннему не видно", "Первое сообщение проверки" not in стрB)
проверка("у постороннего своя форма оценки", 'data-rating="form"' in стрB)

# --- модерация: без ключа нельзя -------------------------------------------
поляB = скрытые(стрB)
код, куда = post(B, "/community/comment/decide",
                 dict(поляB, id=ид.group(1), decision="approved"))
проверка("без ключа модерация запрещена", "community=forbidden" in (куда or ""), str(куда))

# --- модерация: с ключом ----------------------------------------------------
#
# Кука модератора ставится ЗАГОЛОВКОМ: её выдаёт владелец вручную, а не сайт,
# и подделать её через jar клиента значило бы проверять не тот путь.
КЛЮЧ = "test-moderator-key-9190"
_, стрM0 = get(A, СТРАНИЦА)          # A уже имеет куку посетителя
поляM = скрытые(стрM0)

def как_модератор(путь, поля=None):
    кука = f"lords_90_v={[c.value for c in jarA if c.name=='lords_90_v'][0]}; " \
           f"lords_90_mod={КЛЮЧ}"
    заг = {"Cookie": кука}
    if поля is None:
        зпр = urllib.request.Request(БАЗА + urllib.parse.quote(путь, safe="/?=&#"),
                                     headers=заг)
    else:
        заг["Content-Type"] = "application/x-www-form-urlencoded"
        зпр = urllib.request.Request(БАЗА + путь,
                                     data=urllib.parse.urlencode(поля).encode(),
                                     headers=заг)
    о = urllib.request.build_opener(НеСледовать())
    try:
        with о.open(зпр, timeout=30) as r:
            return r.status, r.headers.get("Location", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location", ""), e.read().decode("utf-8", "replace")

код, _, стрM = как_модератор(СТРАНИЦА)
проверка("модератор видит очередь", "На модерации" in стрM, f"код {код}")
поляM = скрытые(стрM)
код, куда, _ = как_модератор("/community/comment/decide",
                             dict(поляM, id=ид.group(1), decision="approved"))
проверка("модератор одобрил", "community=ok" in (куда or ""), str(куда))
C, _ = клиент()
_, стрC = get(C, СТРАНИЦА)
проверка("опубликованное видно всем", "Первое сообщение проверки" in стрC)

# --- отказ сохраняет текст --------------------------------------------------
D, jarD = клиент()
_, стрD = get(D, СТРАНИЦА)
поляD = скрытые(стрD)
код, куда = post(D, "/community/comment", dict(поляD, name="Пётр", text=""))
проверка("пустой текст отклонён", "community=error" in (куда or ""), str(куда))
проверка("черновик сохранён кукой", any(c.name == "lords_90_draft" for c in jarD),
         str([c.name for c in jarD]))
_, стрD = get(D, СТРАНИЦА)
проверка("имя вернулось в форму", 'value="Пётр"' in стрD)

print(f"{'проверка':<44} итог")
print("-" * 60)
for имя, статус, подр in итог:
    print(f"{имя:<44} {статус}" + (f"  {подр}" if статус == "FAIL" and подр else ""))
print("-" * 60)
print(f"всего {len(итог)}, провалов {len(провалы)}")
sys.exit(1 if провалы else 0)
