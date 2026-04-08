"""Web application package bootstrap and compatibility helpers."""

from importlib import import_module
import sys


def _register_legacy_package_aliases() -> None:
    for package_name in ("core", "endpoints", "playgrounds"):
        sys.modules.setdefault(package_name, import_module(f"webapp.{package_name}"))


_register_legacy_package_aliases()
