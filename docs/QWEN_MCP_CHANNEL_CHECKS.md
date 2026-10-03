# Ограничения канала srv-qwen: исправление и разделение проверок

## Что было неверно

В первой редакции отчёта и скрипта стояло
`restrict,permitopen="127.0.0.1:9000",command="/bin/false"`. Строка выглядела
разрешающей, а канал по ней не поднялся бы: `restrict` выключает проброс
портов, а `permitopen` его НЕ включает. Дословно по `sshd(8)` этого же хоста
(раздел AUTHORIZED_KEYS FILE FORMAT):

| опция | что говорит документация |
| --- | --- |
| `restrict` | «disable port, agent and X11 forwarding, as well as disabling PTY allocation and execution of ~/.ssh/rc» |
| `port-forwarding` | «Enable port forwarding previously disabled by the restrict option» |
| `permitopen="host:port"` | «Limit local port forwarding with the ssh -L option such that it may only connect to the specified host and port» |

То есть `permitopen` — ограничитель цели, а не выключатель запрета.

## Фактическая строка после исправления

    restrict,port-forwarding,permitopen="127.0.0.1:9000",command="/bin/false" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBdXYS9HsyXBfoYfC1fSpJGYkhQq2ap8y2Zcx+gXZ9AR site-factory-bridge@srv-qwen

Её собирает `automation/host/install-mcp-bridge-grant.sh`. После записи он
сверяет СМЫСЛ строки (ищет `restrict,port-forwarding,permitopen="…"`) и
останавливается, если `port-forwarding` потерялся: строка без него запрещает
тот проброс, который ей полагается разрешить.

Серверные ограничения не менялись — блок `Match User sfbridge` остался тем же.

## Проверки, ВЫПОЛНЕННЫЕ в сессии фабрики

| проверка | как | результат |
| --- | --- | --- |
| семантика опций | `sshd(8)` этого хоста | `permitopen` не включает проброс; нужен `port-forwarding` |
| отпечаток присланного ключа | `ssh-keygen -lf` | `SHA256:AbTvnN9WdSN8elbkKJJG0WXoV/+rVgAL14af8JNCc3g` — совпал |
| синтаксис блока Match | `sshd -t -f` плюс A/B с нарочно испорченной директивой | мой блок принят (разбор доходит до загрузки root-ключа); испорченный даёт `Bad configuration option` на той же строке |
| **эффективная конфигурация для `sfbridge`** | `sshd -T -C user=sfbridge,host=srv-qwen,addr=83.237.185.70` с тестовой конфигурацией и СВОИМ ключом хоста | `allowtcpforwarding local`, `permitopen 127.0.0.1:9000`, `permitlisten none`, `permittty no`, `x11forwarding no`, `allowagentforwarding no`, `permittunnel no`, `allowstreamlocalforwarding no` |
| та же конфигурация для `claude` | то же | `allowtcpforwarding no` — разрешение канала другим учётным записям НЕ достаётся |
| HTTP моста | настоящий сокет на петле | `initialize`, `tools/list` (6 инструментов, пишущего нет), `system_readiness` (23 сайта, источник `config/site-cells.json`), `list_registered_sites` (`version 1`, отпечаток `4511cf3add1b3e88`) |
| синтаксис скриптов | `bash -n` | без замечаний |

Блок Match для расчёта эффективной конфигурации брался НЕ из копии, а из самого
скрипта установки: иначе проверялся бы текст, который на хост не поедет.

## Что осталось LIVE-приёмкой и почему

`ssh`-клиент запрещён профилем сессии фабрики (цели нет в
`inventory/ssh-hosts.yaml`), а закрытый ключ канала остаётся на `srv-qwen` и
переносу не подлежит. Поэтому проверки, требующие настоящего соединения,
выполняются ТАМ, где лежит ключ — готовым скриптом
`verify-channel-from-srv-qwen.sh` (каталог прогона):

1. настоящий HTTP через настоящий туннель: `initialize`, `/healthz`,
   `system_readiness`, сверка 23 сайтов и отпечатка `4511cf3add1b3e88`;
2. отказ для ДРУГОГО порта (`-L 127.0.0.1:22`);
3. отказ для ОБРАТНОГО туннеля (`-R`);
4. отказ оболочки, выполнения команды и PTY.

Запуск на srv-qwen после установки владельцем:

    sudo bash verify-channel-from-srv-qwen.sh

**НЕ ПРОВЕРЕНО** до этого запуска: фактический проброс по ключу и фактические
отказы по пунктам 2–4. Они зависят от конфигурации, которой на фабрике ещё
нет: юнит не установлен, `127.0.0.1:9000` не слушает, учётной записи `sfbridge`
не существует.
