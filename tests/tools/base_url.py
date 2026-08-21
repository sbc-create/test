"""Печатает базовый URL текущей цели пилота."""
import sys

sys.path.insert(0, ".")
from factory import inventory, validation  # noqa: E402
from factory.targets import build_target  # noqa: E402

package = validation.load_package("pilot-local")
print(build_target(inventory.target(package["target_ref"]), package).base_url())
