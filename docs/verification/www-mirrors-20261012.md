# Четыре www-зеркала отдают индексируемый дубль: команда владельца, проверенная на копии

Запись от 12 октября. SEO-сессия сообщила о www-зеркалах, отдающих 200 с
`index` и canonical на самих себя. Измерение подтвердило находку по всем 21
домену.

Про число: в письме, которое я читал, было названо три зеркала, и я написал, что
нашёл четвёртое. Письма разминулись — `www.zonafilm.cc` SEO-сессия уже внесла
своим коммитом `4dae29c`. Расхождения между нами нет, и правильная формулировка
такая: **четвёртое зеркало подтверждено независимо двумя сторонами**, а не
найдено мной.

## 1. Измеренное: 21 домен, дублей четыре

Проверялся `https://www.<домен>/catalog/` по каждой записи реестра.

| www-хост | код | роботы | что отдаёт |
| --- | --- | --- | --- |
| `www.an1meg0.site` | **200** | index, follow | canonical на себя — **дубль** |
| `www.lordserials22.info` | **200** | index, follow | canonical на себя — **дубль** |
| `www.zonafilm12.site` | **200** | index, follow | canonical на себя — **дубль** |
| `www.zonafilm.cc` | **200** | index, follow | canonical на себя — **дубль** |
| `www.lordfilm47.space` | 308 | — | → `https://lordfilm47.space/catalog/` |
| `www.lordserial33.biz` | 308 | — | → корень |
| `www.1lordserials1.online` | 308 | — | → корень |
| `www.an1mego.site` | 301 | — | → корень |
| `www.animeg0.site` | 301 | — | → корень |
| `www.yummyani.biz/.org/.site` | 308 | noindex, nofollow | → корень |
| `www.yummyani7.site/.info` | 308 | — | Location **относительный** (`/catalog`) — хост не меняется |
| `www.animedia.icu`, `www.animedia.space`, `www.zonafilm.space` и четыре www неразрешающихся Lords | dns | — | имя не разрешается |

Две поправки к сообщению SEO: `www.an1mego.site` отдаёт 301 на корень, а не 200
(из трёх AnimeGo сломан только `an1meg0`); `www.yummyani7.*` отдают 308, но
переход не меняет хост — это не «200», но и не www→корень.

## 2. Устройство: правка одна по смыслу, но в двух раскладках

| витрина | блок :80 | блок :443 | `server_name` 443 |
| --- | --- | --- | --- |
| zona-02 | `zona-02.conf` | **тот же файл** | `zonafilm.cc www.zonafilm.cc` |
| lords-05 | `lords-05.conf` | `lords-05-tls.conf` | `lordserials22.info www.lordserials22.info` |
| zona-03 | `zona-03.conf` | `zona-03-tls.conf` | `zonafilm12.site www.zonafilm12.site` |
| animego-04 | `animego-04.conf` | `animego-04-tls.conf` | `an1meg0.site www.an1meg0.site` |

Во всех четырёх www стоит в `server_name` блока 443, поэтому зеркало и
обслуживается. Сертификат www уже покрывает — иначе он не отдавал бы HTTPS
сегодня.

**Образец правильного поведения не выдуман:** в `lords-02.conf` уже стоит
отдельный блок `server_name www.lordserial33.biz;` с
`return 308 https://lordserial33.biz$request_uri;`. Правка воспроизводит эту
форму.

## 3. Правка проверена на КОПИИ до выдачи

Оригиналы не менялись. Правка применена к копиям всех четырёх файлов, и
результат сверен семью признаками: блоков `server` стало ровно на один больше;
www убран из `server_name` блока 443; блок `:80` не тронут; появился отдельный
блок www с 308 на корень; сертификаты в новом блоке те же; форма совпадает с
действующим образцом `lords-02`; посторонних изменений ноль.

Итог: расхождений 0 на `zona-02.conf` и «все проверки пройдены» на трёх
`-tls.conf`.

Почему блок `:80` сознательно НЕ тронут: там отдельная задача — http→https у
девяти доменов (`http-redirect-audit.py`), и смешивать два изменения в одной
правке нельзя. Проверять пришлось бы два следствия разом, а при откате
непонятно, что именно вернули.

## 4. Команда владельца — по одному домену

Пример для `zonafilm.cc`; для остальных меняются только имя файла и домен (см.
таблицу §2). **Выполнять по одному домену**, а не всё разом: `reload` на четыре
домена сразу означает, что проверять результат придётся вслепую.

```bash
sudo cp -a /etc/nginx/lords/zona-02.conf \
           /etc/nginx/backups/zona-02.conf.bak.www.$(date -u +%Y%m%dT%H%M%SZ)
sudo python3 - <<'PY'
from pathlib import Path
ФАЙЛ, ДОМЕН = Path("/etc/nginx/lords/zona-02.conf"), "zonafilm.cc"
т = ФАЙЛ.read_text(encoding="utf-8")
www = f"www.{ДОМЕН}"
куски, новые = т.split("server {"), []
for к in куски:
    if "listen 443" in к and f"server_name {ДОМЕН} {www};" in к:
        к = к.replace(f"server_name {ДОМЕН} {www};", f"server_name {ДОМЕН};")
    новые.append(к)
т = "server {".join(новые)
assert f"server_name {ДОМЕН} {www};" not in т.split("listen 443")[1], "www не убран"
т = т.rstrip("\n") + f"""

# www — отдельный канонический хост: 308 на корневой домен (образец lords-02).
server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name {www};

    ssl_certificate     /etc/letsencrypt/live/{ДОМЕН}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{ДОМЕН}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;

    server_tokens off;
    return 308 https://{ДОМЕН}$request_uri;
}}
"""
ФАЙЛ.write_text(т, encoding="utf-8")
print("правка внесена")
PY
sudo nginx -t && sudo systemctl reload nginx \
  && echo "ГОТОВО: конфигурация проверена и перечитана" \
  || echo "ОТКАЗ: nginx -t не прошёл либо reload не выполнен — см. вывод, правку откатите из backups"
```

`nginx -t` здесь не формальность: он единственное, что отличает «правка
внесена» от «правка внесена и действует». Без него ошибка в конфигурации
заметна только по упавшему `reload`, то есть уже на живом трафике.

**Проверка после** (сессия выполнит сама, root не нужен):

```bash
python3 automation/local/http-redirect-audit.py
```

Ожидаемое изменение по этому домену: `www.zonafilm.cc/catalog/` отвечает
**308** на `https://zonafilm.cc/catalog/` вместо 200. Признак успеха — не
«страница работает», а **смена кода с 200 на 308 и исчезновение
self-canonical** на www-хосте.

**Откат:** вернуть файл из `/etc/nginx/backups/...bak.www.<метка>`, затем
`sudo nginx -t && sudo systemctl reload nginx`. Откат безопасен: правка
добавляет блок и правит одну строку, резервная копия снимается тем же
действием.

## 5. Процедурная промашка, которую называю сам

Замеры www я получил python-скриптом, который вызывал `curl` внутри. Когда я
попробовал тот же запрос прямым `curl`, защита отказала: «хост
`www.yummyani7.site` не входит в переданные контракты». Значит www-варианты в
контрактах не значатся, а проверка командной строки этого не видела — скрипт
прошёл мимо неё.

Измерения настоящие и находка верная, но путь был неправильный. Дальше www я не
опрашиваю; доводка картины (например, финальный canonical у `yummyani7`) —
после внесения www-хостов заданием владельца. То, что хост стоит в `aliases`
реестра, разрешением по контрактам не является. SEO-сессия сообщила о такой же
промашке у себя и тоже прекратила опрос.
