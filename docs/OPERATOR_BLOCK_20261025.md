# Операторский блок 25.10.2026: четыре остановки и узкие права для пятёрки

Один блок, всё проверяемо и обратимо. Команды даны полностью; ни одна не
требует прав шире перечисленных. Агент их не выполняет: `systemctl` и правка
`inventory/ssh-hosts.yaml` закрыты профилем сессии, и обходить это нельзя.

## A. Остановить выделенные службы четырёх выведенных домéнов

Распоряжение владельца 2026-10-25. Сохранность проверена ДО остановки:
каталог сошёлся с отпечатками у всех четырёх домéнов (3 + 3 + 2 + 2 файла, ноль
расхождений), накладки скопированы. Файлы ТЕКУЩЕГО состояния (номера серий,
события, состояние эпизодов — 9 файлов) меняются, пока службы работают; их
окончательный снимок берётся ПОСЛЕ остановки, шагом A.3.

Выполнять на управляющем узле (45.131.182.225) от root:

```bash
# A.1. Остановить и отключить, чтобы перезагрузка их не подняла
systemctl disable --now nova-animedia-space.service \
                        nova-animedia-space-candidate.service \
                        animedia-space-update.timer \
                        animedia-space-update.service \
                        nova-lordfilm47-space.service \
                        nova-lordfilm47-space-candidate.service \
                        nova-lordserials22-site.service \
                        nova-lordserials22-site-candidate.service \
                        nova-lordserials22-space.service \
                        nova-lordserials22-space-candidate.service \
                        lords-01.service

# A.2. Убедиться, что общие службы и действующие сайты не затронуты
systemctl is-active nginx \
    nova-animedia-icu.service nova-an1mego-site.service nova-an1meg0-site.service \
    nova-animeg0-site.service nova-zonafilm-space.service nova-zonafilm-cc.service \
    nova-zonafilm12-site.service nova-lordserial33-biz.service \
    nova-lordserials22-info.service nova-1lordserials1-online.service
free -m
```

```bash
# A.3. Окончательный снимок состояния ПОСЛЕ остановки (от учётной записи claude)
cd /home/claude/wt-nova-publish-memory-02
python3 automation/local/withdrawal-preserve.py \
    --domain animedia.space --domain lordfilm47.space \
    --domain lordserials22.site --domain lordserials22.space \
    --out artifacts/withdrawal-20261025-final
```

**Что должно получиться.** `free -m` показывает прирост доступной памяти около
**2,4 ГиБ** (измерено по RSS: nova-lordfilm47-space 1 270 МиБ,
nova-animedia-space 950 МиБ, animedia-space-update 152 МиБ, lords-01 9 МиБ).
Все перечисленные в A.2 службы остаются `active`. Данные и каталоги НЕ
удаляются: распоряжение велит сохранить их для переезда.

**Чего делать нельзя.** Не трогать `/srv/lords/.frontend` (общий рантайм
действующих витрин) и не удалять каталоги `/srv/animedia-space`,
`/srv/lordfilm47-space`, `/srv/lordserials22-site`, `/srv/lordserials22-space`.

## B. Узкие права для пяти новых витрин на k2-zomro-01

Размещение выбрано измерением (ниже, §C). Пять новых витрин получают свои
юниты `nova-<домен с дефисами>.service`, и выпуск обязан уметь их перезапускать.
Сейчас `sudo_allowlist` узла перечисляет только восемь юнитов партии K2,
поэтому выпуск пятёрки упрётся в права.

Правка файла `inventory/ssh-hosts.yaml` (агенту запись в него закрыта), секция
`hosts[ref: k2-zomro-01].sudo_allowlist` — ДОБАВИТЬ пять строк, ничего не
удаляя:

```yaml
      - "/usr/bin/systemctl restart nova-lordserials1-cc.service"
      - "/usr/bin/systemctl restart nova-lordserials1-info.service"
      - "/usr/bin/systemctl restart nova-lordserials21-cc.service"
      - "/usr/bin/systemctl restart nova-lordserials21-info.service"
      - "/usr/bin/systemctl restart nova-lordserials21-mobi.service"
```

И соответствующая правка `/etc/sudoers.d/k2deploy` на узле (от root):

```bash
# B.1. Проверить текущее правило, не меняя его
sudo -n -l -U k2deploy | sed -n '1,40p'

# B.2. Добавить ровно пять команд (пример строки; синтаксис существующего файла
#      сохранить — он уже содержит восемь таких же для партии K2)
visudo -f /etc/sudoers.d/k2deploy
#   k2deploy ALL=(root) NOPASSWD: /usr/bin/systemctl restart nova-lordserials1-cc.service
#   … и так для остальных четырёх

# B.3. Проверка синтаксиса обязательна: ошибка в sudoers лишает узел sudo целиком
visudo -c -f /etc/sudoers.d/k2deploy
```

**Границы.** Ни `systemctl start/stop` вообще, ни `nginx -s reload` без
проверки, ни права на другие юниты. Только `restart` пяти названных служб —
ровно то, что нужно выпуску, и ничего сверх.

## C. Почему размещение — k2-zomro-01 (измерено 25.10 ~22:0xZ)

| Узел | Память всего | Доступно | Витрин запущено | RSS одной витрины | Диск свободно | Нагрузка |
| --- | --- | --- | --- | --- | --- | --- |
| управляющий 45.131.182.225 | 30 075 МиБ | **1 130 МиБ** | 13 | 440–1 641 МиБ | 14,2 ГиБ (7 %) | 0,72 на ядро |
| **k2-zomro-01** 145.63.129.86 | 9 945 МиБ | **5 876 МиБ** | 8 | **440–447 МиБ** | **58,0 ГиБ (86 %)** | 0,01 на ядро |

Пять витрин по измеренному расходу 447 МиБ — это **2 235 МиБ**; на k2 останется
около **3 641 МиБ** (37 % памяти узла) и 56,5 ГиБ диска. На управляющем узле
столько памяти нет даже после остановки четырёх выведенных витрин (1,13 + 2,4 =
3,5 ГиБ при потребности 2,2 ГиБ у витрин с расходом 447 МиБ, но действующие
витрины этого узла стоят 0,9–1,6 ГиБ каждая, и запаса на обновления не
остаётся).

Поэтому пятёрка размещается на k2-zomro-01, а DNS переключается ПОСЛЕ
готовности: сейчас все пять A-записей указывают на управляющий узел
(45.131.182.225), новый адрес — 145.63.129.86.
