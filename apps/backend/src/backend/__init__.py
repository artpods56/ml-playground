"""Backend package bootstrap and compatibility helpers.

The project historically imported internal modules as top-level packages
(`schemas`, `algorithms`, `utils`, etc.) while the code now lives under the
`backend` package. We register lightweight aliases so the FastAPI app can be
started as a normal installed package without rewriting the whole codebase at
once.
"""

from importlib import import_module
import sys


def _register_legacy_package_aliases() -> None:
    for package_name in ("algorithms", "frontends", "interface", "schemas", "utils"):
        sys.modules.setdefault(package_name, import_module(f"backend.{package_name}"))


_register_legacy_package_aliases()
