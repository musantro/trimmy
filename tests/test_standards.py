"""Architectural standards tests for the hexagonal layering.

These tests enforce the dependency rule of the hexagonal architecture by
statically inspecting the import graph of every source module:

* the **domain** layer may not import the **application** or
  **infrastructure** layers (nor the **presentation** layer);
* the **application** layer may not import the **infrastructure** layer
  (nor the **presentation** layer).

Each source file is parameterized as its own test case and every offending
import it contains is reported, so a single run surfaces *all* violations
rather than failing on the first one.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Root of the importable package, e.g. ``…/src/trimmy``.
_SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
_PACKAGE_ROOT = _SRC_ROOT / "trimmy"
_ROOT_PACKAGE = "trimmy"

# Layers that constitute an inbound dependency violation, keyed by the layer
# of the importing module. The domain sits at the centre of the hexagon and
# must depend on nothing outwards; the application orchestrates the domain but
# must stay free of any concrete adapter (infrastructure/presentation).
_FORBIDDEN_TARGETS: dict[str, frozenset[str]] = {
    "domain": frozenset({"application", "infrastructure", "presentation"}),
    "application": frozenset({"infrastructure", "presentation"}),
}

# Layer segments understood by the resolver. Anything else (``shared`` sub
# packages, top-level modules, …) is classified by these tokens appearing as a
# path segment of the dotted module name.
_LAYER_TOKENS = frozenset({"domain", "application", "infrastructure", "presentation"})


def _module_name(path: Path) -> str:
    """Return the dotted module name for a source file under ``src``."""
    relative = path.relative_to(_SRC_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _layer_of(module: str) -> str | None:
    """Return the architectural layer of a dotted ``trimmy`` module, if any."""
    parts = module.split(".")
    for token in _LAYER_TOKENS:
        if token in parts:
            return token
    return None


def _resolve_relative(module: str | None, level: int, importer: str) -> str | None:
    """Resolve a relative ``from . import x`` target to an absolute module."""
    if level == 0:
        return module
    base = importer.split(".")
    # ``level`` dots ascend ``level`` packages from the importing *module*.
    base = base[: len(base) - level]
    if module:
        base.extend(module.split("."))
    return ".".join(base) if base else None


def _imported_modules(tree: ast.AST, importer: str) -> list[tuple[str, int]]:
    """Yield ``(absolute_module, lineno)`` for every import in ``tree``."""
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_relative(node.module, node.level, importer)
            if resolved is not None:
                found.append((resolved, node.lineno))
    return found


def _source_files() -> list[Path]:
    """Return every ``trimmy`` source file that lives in a governed layer."""
    return sorted(
        path
        for path in _PACKAGE_ROOT.rglob("*.py")
        if _layer_of(_module_name(path)) in _FORBIDDEN_TARGETS
    )


_SOURCE_FILES = _source_files()
_TEST_IDS = [_module_name(path) for path in _SOURCE_FILES]


def test_source_files_were_discovered() -> None:
    """Guard against the parametrization silently collecting nothing."""
    assert _SOURCE_FILES, "no governed source files were discovered under src/trimmy"


@pytest.mark.parametrize("source", _SOURCE_FILES, ids=_TEST_IDS)
def test_layer_does_not_import_forbidden_layers(source: Path) -> None:
    """A module must not import any layer forbidden by its own layer."""
    importer = _module_name(source)
    layer = _layer_of(importer)
    assert layer is not None  # guaranteed by the discovery filter
    forbidden = _FORBIDDEN_TARGETS[layer]

    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))

    violations: list[str] = []
    for module, lineno in _imported_modules(tree, importer):
        if module.split(".")[0] != _ROOT_PACKAGE:
            continue
        target_layer = _layer_of(module)
        if target_layer in forbidden:
            violations.append(
                f"  {importer}:{lineno}: {layer} layer imports "
                f"{target_layer} layer via '{module}'"
            )

    assert not violations, (
        f"hexagonal dependency rule violated in {importer}:\n"
        + "\n".join(violations)
    )
