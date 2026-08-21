"""Адаптеры целей развёртывания."""
from factory.targets.base import DeployPlan, DeployResult, Target  # noqa: F401


def build_target(target_conf: dict, package: dict):
    from factory.errors import BlockedAccess
    adapter = target_conf.get("adapter")
    if adapter == "local_disposable":
        from factory.targets.local_disposable import LocalDisposableTarget
        return LocalDisposableTarget(target_conf, package)
    if adapter == "ssh_ansible":
        from factory.targets.ssh_ansible import SshAnsibleTarget
        return SshAnsibleTarget(target_conf, package)
    raise BlockedAccess(
        f"Неизвестный adapter цели: {adapter!r}.",
        field="inventory/targets.yaml",
        required_input="adapter: local_disposable | ssh_ansible",
        blocks_stage="STAGING_DEPLOY",
    )
