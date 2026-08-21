# automation/ansible

Декларативный слой развёртывания по SSH. Вызывается **только** через
`factory/targets/ssh_ansible.py`, который перед запуском проверяет:
inventory-цель, host key pinning, наличие ключа через `secret_ref`, авторизацию
пакета и наличие бэкапа.

Инварианты playbook'ов:

- deploy-пользователь least-privilege, root-логин запрещён;
- `become` разрешён только для команд из `sudo_allowlist` записи хоста;
- релизы атомарны: `releases/<build_id>` + симлинк `current`, переключение только
  после успешного config test и health check;
- предыдущий рабочий релиз сохраняется (`keep_releases`);
- повторный запуск идемпотентен: `changed=0` при неизменном `build_id`;
- world-writable права не выставляются никогда.

**Ansible в текущем окружении не установлен** (проверено `command -v ansible-playbook`),
поэтому playbook'и не исполнялись: `factory deploy` на SSH-цель вернёт `BLOCKED_ACCESS`
с этим объяснением. Синтаксис проверяется `ansible-playbook --syntax-check` на машине,
где Ansible установлен, и `python3 -c "import yaml; yaml.safe_load(...)"` — здесь.
