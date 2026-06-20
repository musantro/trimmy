"""Architectural standards tests.

These tests statically inspect the import graph of every source module and
enforce the project's hexagonal + vertical-slicing rules:

* **Layering (hexagonal).** Within any module the dependencies point inward:
  the ``domain`` layer imports neither ``application`` nor ``infrastructure``;
  the ``application`` layer imports no ``infrastructure``.

* **Top-level cleanliness.** ``src/trimmy`` itself contains only ``__init__``
  and ``__main__`` — all code lives inside a bounded context.

* **Context map (vertical slicing).** A bounded context may import only
  itself, the global ``shared`` kernel, and any context it is *explicitly*
  declared to consume. Cross-context imports must target the other context's
  ``shared`` published language, and a context's modules talk to each other
  only through that context's ``shared`` package — never sibling-to-sibling.

* **Shared kernel is a sink.** ``trimmy.shared`` depends on no other context.

The ``app`` package is the composition root (PySide6 UI + session wiring) and
is exempt from the context-map rules. Every offending import is reported, and
each source file is parameterized as its own case so one run surfaces them all.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
_PACKAGE_ROOT = _SRC_ROOT / "trimmy"
_ROOT_PACKAGE = "trimmy"

# Hexagonal layers, from the inside out.
_LAYERS = frozenset({"domain", "application", "infrastructure"})

# Layers an importing layer may not depend on (the dependency rule).
_FORBIDDEN_INNER_TARGETS: dict[str, frozenset[str]] = {
    "domain": frozenset({"application", "infrastructure"}),
    "application": frozenset({"infrastructure"}),
}

# The global shared kernel and the per-context published-language package
# happen to share the name ``shared`` at their respective levels.
_KERNEL = "shared"

# The composition root: wires the contexts together, exempt from the map.
_COMPOSITION_ROOT = "app"

# The executable context map: the only permitted cross-context dependencies.
# ``rendering`` consumes the ``editing`` context's published language because
# you cannot render a clip that has not been composed.
_DECLARED_CONTEXT_EDGES: frozenset[tuple[str, str]] = frozenset(
    {("rendering", "editing")},
)


# --------------------------------------------------------------------------- #
# Module-path helpers
# --------------------------------------------------------------------------- #
def _module_name(path: Path) -> str:
    """Return the dotted module name for a source file under ``src``."""
    relative = path.relative_to(_SRC_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _parts(module: str) -> list[str]:
    return module.split(".")


def _context_of(module: str) -> str | None:
    """Return the bounded context a ``trimmy`` module belongs to."""
    parts = _parts(module)
    if parts[0] != _ROOT_PACKAGE or len(parts) < 2:
        return None
    return parts[1]


def _submodule_of(module: str) -> str | None:
    """Return the module within a context, or ``None`` for context-level code.

    A context like ``editing`` is split into sub-packages (``crop``, ``trim``,
    ``shared``); ``rendering`` keeps its layers directly under the context, so
    its files are context-level (``None``).
    """
    parts = _parts(module)
    if len(parts) < 3 or parts[2] in _LAYERS:
        return None
    return parts[2]


def _layer_of(module: str) -> str | None:
    """Return the first hexagonal layer named in a dotted module path."""
    for part in _parts(module):
        if part in _LAYERS:
            return part
    return None


# --------------------------------------------------------------------------- #
# Import extraction
# --------------------------------------------------------------------------- #
def _resolve_relative(module: str | None, level: int, importer: str) -> str | None:
    """Resolve a relative ``from . import x`` target to an absolute module."""
    if level == 0:
        return module
    base = _parts(importer)
    base = base[: len(base) - level]
    if module:
        base.extend(_parts(module))
    return ".".join(base) if base else None


def _trimmy_imports(source: Path, importer: str) -> list[tuple[str, int]]:
    """Yield ``(module, lineno)`` for every ``trimmy`` import in *source*."""
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_relative(node.module, node.level, importer)
            if resolved is not None:
                found.append((resolved, node.lineno))
    return [(m, n) for m, n in found if _parts(m)[0] == _ROOT_PACKAGE]


# --------------------------------------------------------------------------- #
# File discovery
# --------------------------------------------------------------------------- #
def _all_source_files() -> list[Path]:
    return sorted(_PACKAGE_ROOT.rglob("*.py"))


def _hexagonal_files() -> list[Path]:
    """Domain/application files of every context except the composition root."""
    return [
        path
        for path in _all_source_files()
        if _layer_of(_module_name(path)) in _FORBIDDEN_INNER_TARGETS
        and _context_of(_module_name(path)) != _COMPOSITION_ROOT
    ]


def _context_mapped_files() -> list[Path]:
    """Files governed by the context map: every context except ``app``."""
    result: list[Path] = []
    for path in _all_source_files():
        module = _module_name(path)
        context = _context_of(module)
        if context in (None, _COMPOSITION_ROOT):
            continue
        if len(_parts(module)) < 3:  # bare context package __init__
            continue
        result.append(path)
    return result


_HEX_FILES = _hexagonal_files()
_MAP_FILES = _context_mapped_files()
_SHARED_FILES = [
    p for p in _all_source_files() if _context_of(_module_name(p)) == _KERNEL
]


# --------------------------------------------------------------------------- #
# 1. Top-level cleanliness
# --------------------------------------------------------------------------- #
def test_only_init_and_main_at_top_level() -> None:
    """``src/trimmy`` holds no modules other than ``__init__``/``__main__``."""
    offenders = sorted(
        path.name
        for path in _PACKAGE_ROOT.glob("*.py")
        if path.name not in {"__init__.py", "__main__.py"}
    )
    assert not offenders, (
        "only __init__.py and __main__.py may live directly under "
        f"src/trimmy; found: {offenders}"
    )


# --------------------------------------------------------------------------- #
# 2. Hexagonal layering (dependencies point inward)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "source",
    _HEX_FILES,
    ids=[_module_name(p) for p in _HEX_FILES],
)
def test_layers_depend_inward(source: Path) -> None:
    """A layer must not import a layer further out than itself."""
    importer = _module_name(source)
    layer = _layer_of(importer)
    assert layer is not None
    forbidden = _FORBIDDEN_INNER_TARGETS[layer]

    violations = [
        f"  {importer}:{lineno}: {layer} imports {_layer_of(module)} "
        f"layer via '{module}'"
        for module, lineno in _trimmy_imports(source, importer)
        if _layer_of(module) in forbidden
    ]
    assert not violations, (
        f"hexagonal dependency rule violated in {importer}:\n" + "\n".join(violations)
    )


# --------------------------------------------------------------------------- #
# 3. Context map (vertical slicing)
# --------------------------------------------------------------------------- #
def _context_violation(importer: str, target: str) -> str | None:
    """Return a reason string if importing *target* breaks the context map."""
    ci, mi = _context_of(importer), _submodule_of(importer)
    ct, mt = _context_of(target), _submodule_of(target)

    if ct is None or ct == _KERNEL:
        return None  # the global kernel is always importable

    if ci == ct:
        # Intra-context: only via the same module or the context's `shared`.
        if mi == mt or mt == _KERNEL or mt is None:
            return None
        return f"module '{mi}' imports sibling module '{mt}' directly"

    # Cross-context: only along a declared edge, and only its published language.
    if (ci, ct) not in _DECLARED_CONTEXT_EDGES:
        return f"undeclared cross-context dependency '{ci}' -> '{ct}'"
    if mt != _KERNEL:
        return (
            f"'{ci}' may consume only '{ct}.{_KERNEL}' (published language), "
            f"not module '{mt}'"
        )
    return None


@pytest.mark.parametrize(
    "source",
    _MAP_FILES,
    ids=[_module_name(p) for p in _MAP_FILES],
)
def test_respects_context_map(source: Path) -> None:
    """Every cross-package import obeys the declared context map."""
    importer = _module_name(source)
    violations = [
        f"  {importer}:{lineno}: {reason} (via '{module}')"
        for module, lineno in _trimmy_imports(source, importer)
        if (reason := _context_violation(importer, module)) is not None
    ]
    assert not violations, f"context-map violation in {importer}:\n" + "\n".join(
        violations
    )


# --------------------------------------------------------------------------- #
# 4. The shared kernel depends on nothing else
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "source",
    _SHARED_FILES,
    ids=[_module_name(p) for p in _SHARED_FILES],
)
def test_shared_kernel_is_a_sink(source: Path) -> None:
    """``trimmy.shared`` must not import any other bounded context."""
    importer = _module_name(source)
    violations = [
        f"  {importer}:{lineno}: shared kernel imports '{module}'"
        for module, lineno in _trimmy_imports(source, importer)
        if _context_of(module) not in (None, _KERNEL)
    ]
    assert not violations, (
        f"shared kernel must depend on nothing else, but {importer} does:\n"
        + "\n".join(violations)
    )


def test_governed_files_were_discovered() -> None:
    """Guard against the parametrization silently collecting nothing."""
    assert _HEX_FILES, "no hexagonal files discovered"
    assert _MAP_FILES, "no context-mapped files discovered"
    assert _SHARED_FILES, "no shared-kernel files discovered"
