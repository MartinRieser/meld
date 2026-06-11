# Agents.md

## Build, Lint & Test Commands

### Build
```bash
meson setup builddir
meson compile -C builddir
meson install -C builddir
```
For a Python wheel:
```bash
pip install .   # uses meson-python with -Dis_wheel=true
```

### Lint & Format
```bash
# Run pre-commit (includes Ruff)
pre-commit run --all-files --show-diff-on-failure

# Or Ruff directly:
ruff check .

# Ruff rules selected in pyproject.toml:
# E4/E7/E9 = pycodestyle errors, F = pyflakes, I = isort
```

### Test
```bash
# All tests
pytest

# Single test file
pytest test/test_misc.py

# Single test function
pytest test/test_misc.py::test_merge_intervals

# Verbose
pytest -v test/test_misc.py::test_all_same
```

---

## Project Overview

- **Language**: Python 3 (>= 3.10)
- **UI Toolkit**: GTK4 + GtkSourceView-5 via PyGObject
- **Build System**: Meson + meson-python
- **Test Framework**: pytest
- **Linter**: Ruff (E4/E7/E9/F/I rules)
- **CI**: GitLab CI (`.gitlab-ci.yml`)
- **Optional**: pre-commit hooks configured

---

## Code Style Guidelines

### Imports

Strict ordering (enforced by Ruff isort): stdlib → third-party → first-party. Separate groups with blank lines. Use `order-by-type` (module imports before from-imports within a group).

```python
import copy
import functools
import logging
from enum import Enum
from typing import Optional, Tuple

from gi.repository import Gdk, Gio, GLib, GObject, Gtk

from meld import misc
from meld.conf import _
from meld.const import (
    ActionMode,
    ChunkAction,
    FileComparisonMode,
)
```

First-party imports use `from meld.xxx import yyy` or `import meld.xxx`.

### Formatting

- 4-space indentation for Python, 2-space for XML/JSON/Meson
- LF line endings, trailing whitespace trimmed, final newline
- Line length: ~80-100 chars (not strictly enforced)
- Break long strings with parentheses, not backslashes

### Types

Use Python type hints everywhere. Typing imports from `typing`:

```python
from typing import Callable, Generator, List, Mapping, Optional, Sequence, Tuple, Type, Union
```

Type aliases for complex types:
```python
ColourMap = Mapping[str, Gdk.RGBA]
SubprocessGenerator = Generator[Union[Tuple[int, str], None], None, None]
```

Use `GObject.Property` for GTK widget properties:
```python
ignore_blank_lines = GObject.Property(type=bool, default=False)
```

### Naming

| Style | Used For | Examples |
|---|---|---|
| `snake_case` | Variables, functions, methods, modules | `get_modal_parent()`, `self._keymask` |
| `PascalCase` | Classes, type aliases | `FileDiff`, `MeldDoc`, `ColourMap` |
| `UPPER_CASE` | Module-level constants | `MASK_SHIFT`, `LINE_LENGTH_LIMIT`, `COL_PATH` |
| `_leading_underscore` | "Private" methods/attributes | `_filter_text()`, `_sync_vscroll_lock` |
| `__dunder__` | GObject/GTK special names | `__gtype_name__`, `__gsignals__` |

Use `__slots__` in small data-holder classes:
```python
class CursorDetails:
    __slots__ = ("pane", "pos", "line", "chunk", "prev", "next")
```

### Error Handling

- Catch specific exception types, never bare `except:`
- Use `error_dialog()` from `meld.misc` for user-facing errors
- Use `@user_critical(primary, message)` decorator for operations where the user must be told about failures
- Log exceptions with `log.warning(...)` rather than swallowing silently
- Handle `GLib.Error` at GI boundaries with explicit error code checks
- Prefer early return pattern over deep nesting

```python
try:
    have_schema = schema_mtime < compiled_mtime
except OSError:
    have_schema = False

except GLib.Error as e:
    if e.code not in (Gio.IOErrorEnum.NOT_SUPPORTED, Gio.IOErrorEnum.FAILED):
        raise RuntimeError(str(e))
```

### GTK/GObject Patterns

- Use `@Gtk.Template(resource_path=...)` decorator with `__gtype_name__`
- Template children: `actiongutter0 = Gtk.Template.Child()`
- Signal handlers: `@Gtk.Template.Callback()` for UI signals
- Action handlers: name methods `action_*` (e.g., `action_next_change`)
- Use `@with_focused_pane` decorator for pane-specific operations
- Custom signals in `__gsignals__` dict
- GSettings bindings in `__gsettings_bindings_view__` tuple

```python
@Gtk.Template(resource_path='/org/gnome/meld/ui/filediff.ui')
class FileDiff(Gtk.Box, MeldDoc):
    __gtype_name__ = "FileDiff"
    __gsettings_bindings_view__ = (
        ('highlight-current-line', 'highlight_current_line', Gio.SettingsBindFlags.DEFAULT),
    )
    __gsignals__ = {
        'next-conflict-changed': (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    }
    actiongutter0 = Gtk.Template.Child()
```

### Docstrings & Comments

- Module docstrings: `"""Short module description"""`
- Function docstrings with description + parameter docs:
  ```python
  """Remove common parts of a list of paths

  For example, `('/tmp/foo1', '/tmp/foo2')` would be summarised as
  `('foo1', 'foo2')`.

  :param names: list of paths to shorten
  :returns: shortened path names
  """
  ```
- `# TRANSLATORS:` comments before translatable strings
- `# TODO:`, `# FIXME:`, `# XXX:` for known issues
- Bug references: `# See https://bugzilla.gnome.org/show_bug.cgi?id=...`

### Module-Level Conventions

- Logger at top: `log = logging.getLogger(__name__)`
- Singleton instances: `recent_comparisons = RecentFiles()`
- Enum classes for related constants: `class ActionMode(enum.IntEnum):`

### Organizing a Source File

1. Module docstring
2. Standard library imports
3. Third-party imports
4. First-party imports (from meld.*)
5. Module-level constants / enums
6. Logger
7. Type aliases
8. Class/function definitions

### Misc

- Use `isinstance()` checks instead of type() for type comparisons
- Prefer `@functools.wraps` in decorators
- GTK resource paths follow `/org/gnome/meld/...`
- UI templates are in `meld/resources/ui/`, loaded via resource path, never by file path
- Multiple inheritance is used (mixin pattern): `class VcView(Gtk.Box, tree.TreeviewCommon, MeldDoc)`
