"""Executable architecture standards for Trimmy.

The source tree deliberately follows the Codely-style, module-first layout:

* ``editing/{crop,trim}/{domain,application,infrastructure}``
* ``rendering/{domain,application,infrastructure}``
* ``preferences/{domain,application,infrastructure}``

``apps`` contains executable adapters and composition roots, not business
contexts.  These checks make that distinction, the hexagonal dependency
direction, and the small published API between modules executable.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

import pytest

_SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
_PACKAGE_ROOT = _SRC_ROOT / "trimmy"
_ROOT_PACKAGE = "trimmy"
_LAYERS = frozenset({"domain", "application", "infrastructure"})
_FORBIDDEN_TARGET_LAYERS = {
    "domain": frozenset({"application", "infrastructure"}),
    "application": frozenset({"infrastructure"}),
}

# An area can contain vertical modules, or be one module itself (``None``).
_CORE_MODULES = frozenset(
    {
        ("editing", "crop"),
        ("editing", "trim"),
        ("rendering", None),
        ("preferences", None),
    }
)
_CORE_AREAS = frozenset(area for area, _ in _CORE_MODULES)
_SHARED = "shared"
_APPS = frozenset({"desktop", "cli"})

# Rendering consumes only the published domain language of editing modules.
_DECLARED_CROSS_MODULE_EDGES = frozenset(
    {
        (("rendering", None), ("editing", "crop")),
        (("rendering", None), ("editing", "trim")),
        # Preferences currently persists the crop selection as part of the
        # desktop session.  It therefore consumes the crop module's public
        # value-object language, never its application or infrastructure.
        (("preferences", None), ("editing", "crop")),
    }
)

# Framework imports turn a domain model into an adapter.  Keep this list
# intentionally short: the standard protects architectural boundaries, not
# arbitrary standard-library preferences such as dataclasses or pathlib.
_FORBIDDEN_DOMAIN_IMPORT_ROOTS = frozenset({"PySide6", "pydantic", "typer"})


def _module_name(path: Path) -> str:
    relative = path.relative_to(_SRC_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _parts(module: str) -> tuple[str, ...]:
    return tuple(part for part in module.split(".") if part)


def _layer_of(module: str) -> str | None:
    return next((part for part in _parts(module) if part in _LAYERS), None)


def _module_of(module: str) -> tuple[str, str | None] | None:
    """Return the vertical module containing a core module path."""
    parts = _parts(module)
    if len(parts) < 2 or parts[0] != _ROOT_PACKAGE:
        return None
    area = parts[1]
    if area not in _CORE_AREAS:
        return None
    candidate = parts[2] if len(parts) > 2 and parts[2] not in _LAYERS else None
    key = (area, candidate)
    return key if key in _CORE_MODULES else None


def _is_app(module: str) -> bool:
    parts = _parts(module)
    return len(parts) >= 2 and parts[:2] == (_ROOT_PACKAGE, "apps")


def _app_name(module: str) -> str | None:
    parts = _parts(module)
    if len(parts) >= 3 and parts[:2] == (_ROOT_PACKAGE, "apps"):
        return parts[2]
    return None


def _resolve_relative(module: str | None, level: int, importer: str) -> str | None:
    if level == 0:
        return module
    base = list(_parts(importer))
    base = base[: len(base) - level]
    if module:
        base.extend(_parts(module))
    return ".".join(base) or None


def _imports(source: Path, importer: str) -> Iterable[tuple[str, int]]:
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from ((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            target = _resolve_relative(node.module, node.level, importer)
            if target is not None:
                yield target, node.lineno


def _trimmy_imports(source: Path, importer: str) -> list[tuple[str, int]]:
    return [
        (module, line)
        for module, line in _imports(source, importer)
        if _parts(module) and _parts(module)[0] == _ROOT_PACKAGE
    ]


def _all_source_files() -> list[Path]:
    return sorted(_PACKAGE_ROOT.rglob("*.py"))


def _core_files() -> list[Path]:
    return [path for path in _all_source_files() if _module_of(_module_name(path))]


def _layered_core_files() -> list[Path]:
    return [path for path in _core_files() if _layer_of(_module_name(path))]


def _domain_files() -> list[Path]:
    return [
        path
        for path in _layered_core_files()
        if _layer_of(_module_name(path)) == "domain"
    ]


def _shared_files() -> list[Path]:
    return [
        path
        for path in _all_source_files()
        if _parts(_module_name(path))[:2] == (_ROOT_PACKAGE, _SHARED)
    ]


_LAYERED_CORE_FILES = _layered_core_files()
_DOMAIN_FILES = _domain_files()
_SHARED_FILES = _shared_files()


def test_only_init_and_main_at_top_level() -> None:
    offenders = sorted(
        path.name
        for path in _PACKAGE_ROOT.glob("*.py")
        if path.name not in {"__init__.py", "__main__.py"}
    )
    assert not offenders, f"unexpected top-level modules: {offenders}"


def test_core_module_structure_is_explicit() -> None:
    """Core modules are module-first and expose no fourth top-level layer."""
    for area, module in sorted(_CORE_MODULES):
        root = _PACKAGE_ROOT / area
        if module is not None:
            root /= module
        assert root.is_dir(), (
            f"missing declared core module: {root.relative_to(_SRC_ROOT)}"
        )
        children = {
            path.name
            for path in root.iterdir()
            if path.is_dir() and path.name != "__pycache__"
        }
        assert children == _LAYERS, (
            f"{root.relative_to(_SRC_ROOT)} must contain exactly domain, application, "
            f"and infrastructure; found {sorted(children)}"
        )


def test_core_areas_contain_only_declared_modules_or_layers() -> None:
    """Prevent catch-all core packages such as ``utils`` or ``shared``."""
    expected_by_area = {
        "editing": {"crop", "trim"},
        "rendering": set(_LAYERS),
        "preferences": set(_LAYERS),
    }
    for area, expected in expected_by_area.items():
        actual = {
            path.name
            for path in (_PACKAGE_ROOT / area).iterdir()
            if path.is_dir() and path.name != "__pycache__"
        }
        assert actual == expected, (
            f"unexpected structure below {area}: {sorted(actual)}"
        )


def test_core_areas_do_not_hold_unlayered_source_files() -> None:
    """Business code belongs to a module layer, never beside its packages."""
    for area in _CORE_AREAS:
        files = {
            path.name
            for path in (_PACKAGE_ROOT / area).glob("*.py")
            if path.name != "__init__.py"
        }
        assert not files, f"unlayered source files below {area}: {sorted(files)}"
    for area, module in _CORE_MODULES:
        if module is None:
            continue
        files = {
            path.name
            for path in (_PACKAGE_ROOT / area / module).glob("*.py")
            if path.name != "__init__.py"
        }
        assert not files, (
            f"unlayered source files below {area}/{module}: {sorted(files)}"
        )


@pytest.mark.parametrize("source", _LAYERED_CORE_FILES, ids=_module_name)
def test_layers_depend_inward(source: Path) -> None:
    importer = _module_name(source)
    layer = _layer_of(importer)
    assert layer is not None
    forbidden = _FORBIDDEN_TARGET_LAYERS.get(layer, frozenset())
    violations = [
        f"{importer}:{line}: {layer} imports {_layer_of(target)} via {target}"
        for target, line in _trimmy_imports(source, importer)
        if _layer_of(target) in forbidden
    ]
    assert not violations, "hexagonal dependency rule violated:\n" + "\n".join(
        violations
    )


@pytest.mark.parametrize("source", _DOMAIN_FILES, ids=_module_name)
def test_domain_does_not_import_frameworks(source: Path) -> None:
    importer = _module_name(source)
    violations = [
        f"{importer}:{line}: imports framework {target}"
        for target, line in _imports(source, importer)
        if _parts(target) and _parts(target)[0] in _FORBIDDEN_DOMAIN_IMPORT_ROOTS
    ]
    assert not violations, "domain must not depend on frameworks:\n" + "\n".join(
        violations
    )


def _module_import_violation(importer: str, target: str) -> str | None:
    source_module, target_module = _module_of(importer), _module_of(target)
    if target_module is None or source_module is None or source_module == target_module:
        return None
    if (source_module, target_module) not in _DECLARED_CROSS_MODULE_EDGES:
        return f"undeclared dependency {source_module} -> {target_module}"
    target_parts = _parts(target)
    if _layer_of(target) != "domain":
        return "cross-module dependencies may target only a domain API"
    # A dependency on ``domain.models`` is an implementation dependency.  The
    # module's ``domain/__init__.py`` is the deliberate published surface.
    domain_index = target_parts.index("domain")
    if len(target_parts) != domain_index + 1:
        return "cross-module dependencies must use the published domain API"
    return None


@pytest.mark.parametrize("source", _LAYERED_CORE_FILES, ids=_module_name)
def test_core_modules_follow_the_context_map(source: Path) -> None:
    importer = _module_name(source)
    violations = [
        f"{importer}:{line}: {reason} (via {target})"
        for target, line in _trimmy_imports(source, importer)
        if (reason := _module_import_violation(importer, target)) is not None
    ]
    assert not violations, "module context-map violation:\n" + "\n".join(violations)


@pytest.mark.parametrize("source", _core_files() + _SHARED_FILES, ids=_module_name)
def test_core_never_depends_on_an_app(source: Path) -> None:
    importer = _module_name(source)
    violations = [
        f"{importer}:{line}: imports app module {target}"
        for target, line in _trimmy_imports(source, importer)
        if _is_app(target)
    ]
    assert not violations, "business core must not depend on apps:\n" + "\n".join(
        violations
    )


@pytest.mark.parametrize("source", _SHARED_FILES, ids=_module_name)
def test_shared_kernel_is_a_sink(source: Path) -> None:
    importer = _module_name(source)
    violations = [
        f"{importer}:{line}: shared imports {target}"
        for target, line in _trimmy_imports(source, importer)
        if _module_of(target) is not None or _is_app(target)
    ]
    assert not violations, "shared kernel must be a dependency sink:\n" + "\n".join(
        violations
    )


def test_apps_are_explicit_composition_roots() -> None:
    apps_root = _PACKAGE_ROOT / "apps"
    assert apps_root.is_dir(), "apps must hold executable adapters"
    actual = {
        path.name
        for path in apps_root.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    assert actual == _APPS, f"unexpected app roots: {sorted(actual)}"
    for app in _APPS:
        assert (apps_root / app / "bootstrap.py").is_file(), (
            f"trimmy.apps.{app} needs bootstrap.py as its composition root"
        )


def test_only_bootstrap_imports_core_infrastructure_from_apps() -> None:
    """Views/controllers consume application APIs; bootstrap chooses adapters."""
    violations: list[str] = []
    for source in _all_source_files():
        importer = _module_name(source)
        app = _app_name(importer)
        if app is None or source.name == "bootstrap.py":
            continue
        for target, line in _trimmy_imports(source, importer):
            is_core_infrastructure = (
                _module_of(target) is not None and _layer_of(target) == "infrastructure"
            )
            is_shared_infrastructure = _parts(target)[:3] == (
                _ROOT_PACKAGE,
                _SHARED,
                "infrastructure",
            )
            if is_core_infrastructure or is_shared_infrastructure:
                violations.append(f"{importer}:{line}: imports infrastructure {target}")
    assert not violations, (
        "only apps/*/bootstrap.py may select core infrastructure:\n"
        + "\n".join(violations)
    )


def test_architecture_checks_discover_source_files() -> None:
    assert _LAYERED_CORE_FILES, "no layered core files discovered"
    assert _DOMAIN_FILES, "no domain files discovered"
    assert _SHARED_FILES, "no shared-kernel files discovered"
