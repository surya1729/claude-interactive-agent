"""SDK for discovering available tools at runtime.

Usage:
    from libs import sdk
    sdk.list()           # one-liner per tool
    sdk.help("github")   # full API with signatures
"""

import importlib
import inspect
import pkgutil
from datetime import datetime
from pathlib import Path

_LIBS_DIR = Path(__file__).parent
_SKIP = {"__init__", "sdk", "__pycache__"}
_LOG = _LIBS_DIR.parent / "logs" / "libs_calls.log"


def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    _LOG.parent.mkdir(exist_ok=True)
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def _first_line(docstring: str | None) -> str:
    """Extract first non-empty line from a docstring."""
    if not docstring:
        return "(no description)"
    for line in docstring.strip().splitlines():
        line = line.strip()
        if line:
            return line.rstrip(".")
    return "(no description)"


def _discover_modules() -> list[tuple[str, str, str]]:
    """Return [(name, import_path, first_line_of_docstring), ...] for all tool modules."""
    modules = []

    # Top-level .py files
    for f in sorted(_LIBS_DIR.glob("*.py")):
        name = f.stem
        if name in _SKIP:
            continue
        import_path = f"libs.{name}"
        mod = importlib.import_module(import_path)
        modules.append((name, f"from libs import {name}", _first_line(mod.__doc__)))

    # Subdirectories with __init__.py (packages)
    for d in sorted(_LIBS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        if not (d / "__init__.py").exists():
            continue
        # Find .py files inside the package (not __init__)
        for f in sorted(d.glob("*.py")):
            if f.stem.startswith("_"):
                continue
            name = f.stem
            import_path = f"libs.{d.name}.{name}"
            mod = importlib.import_module(import_path)
            modules.append((name, f"from libs.{d.name} import {name}", _first_line(mod.__doc__)))

    return modules


def list() -> str:
    """List all available tools with one-liner descriptions."""
    _log("sdk.list() called")
    modules = _discover_modules()
    if not modules:
        return "No tools found in libs/"

    max_name = max(len(m[0]) for m in modules)
    lines = []
    for name, import_path, desc in modules:
        lines.append(f"  {name:<{max_name}}  {desc}")
    return "\n".join(lines)


def help(tool_name: str) -> str:
    """Show full API for a tool: import path, function signatures, docstrings."""
    _log(f'sdk.help("{tool_name}") called')
    # Try direct import first
    mod = None
    import_line = None
    for name, imp, _ in _discover_modules():
        if name == tool_name:
            mod = importlib.import_module(imp.replace("from ", "").split(" import ")[0] + "." + tool_name
                                          if "." in imp.replace("from ", "").split(" import ")[0]
                                          else f"libs.{tool_name}")
            import_line = imp
            break

    if mod is None:
        return f"Unknown tool: {tool_name}. Run sdk.list() to see available tools."

    lines = [import_line, ""]

    for func_name, func in inspect.getmembers(mod, inspect.isfunction):
        if func_name.startswith("_"):
            continue
        # Only include functions defined in this module, not imports
        if func.__module__ != mod.__name__:
            continue
        sig = inspect.signature(func)
        doc = func.__doc__ or ""
        lines.append(f"{tool_name}.{func_name}{sig}")
        if doc:
            for doc_line in doc.strip().splitlines():
                lines.append(f"  {doc_line.strip()}")
        lines.append("")

    return "\n".join(lines).rstrip()
