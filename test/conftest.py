# ruff: noqa: E402
import os
import sys

import pytest

# Dynamic loading hack for meld.conf when running uninstalled (from git checkout)
melddir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.exists(os.path.join(melddir, "meld.doap")):
    sys.path.insert(0, melddir)
    import importlib.machinery
    import importlib.util
    try:
        loader = importlib.machinery.SourceFileLoader(
            'meld.conf', os.path.join(melddir, 'meld/conf.py.in'))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        import meld
        meld.conf = mod
        sys.modules['meld.conf'] = mod
    except Exception as e:
        print(f"Warning: failed to dynamically load meld.conf from conf.py.in: {e}", file=sys.stderr)

# Initialize uninstalled paths and resource overlays if meld.conf was successfully loaded
if 'meld.conf' in sys.modules:
    meld.conf.uninstalled()

# Compile and register resources before importing any UI components
resource_filename = meld.conf.APPLICATION_ID + ".gresource" if 'meld.conf' in sys.modules else "org.gnome.Meld.gresource"
resource_file = os.path.join(meld.conf.DATADIR, resource_filename) if 'meld.conf' in sys.modules else os.path.join(melddir, "data", resource_filename)

if not os.path.exists(resource_file):
    import subprocess
    try:
        subprocess.call(
            [
                "glib-compile-resources",
                "--target={}".format(resource_file),
                "--sourcedir=meld/resources",
                "--sourcedir=data/icons/hicolor",
                "meld/resources/meld.gresource.xml",
            ],
            cwd=melddir
        )
    except FileNotFoundError:
        print("Warning: glib-compile-resources command not found; skipping compilation.", file=sys.stderr)
    except Exception as e:
        print(f"Warning: glib-compile-resources failed: {e}", file=sys.stderr)

from gi.repository import Gio

if os.path.exists(resource_file):
    try:
        resources = Gio.resource_load(resource_file)
        Gio.resources_register(resources)
    except Exception as e:
        print(f"Warning: failed to register GResource file: {e}", file=sys.stderr)

# Setup GTK compatibility layers and require Gtk 4.0
import meld.ui.gtkcompat

# Register style schemes search path and prepare scheme files
if 'meld.conf' in sys.modules:
    from gi.repository import GtkSource
    style_path = os.path.join(meld.conf.DATADIR, "styles")
    GtkSource.StyleSchemeManager.get_default().append_search_path(style_path)

    for style in {'meld-base', 'meld-dark'}:
        path = os.path.join(style_path, '{}.style-scheme.xml'.format(style))
        if not os.path.exists(path):
            import shutil
            try:
                shutil.copyfile(path + '.in', path)
            except Exception as e:
                print(f"Warning: failed to copy style scheme template {style}: {e}", file=sys.stderr)

# Initialize GSettings settings
import meld.settings

if 'meld.conf' in sys.modules:
    schema_file = os.path.join(meld.conf.DATADIR, "gschemas.compiled")
    if not os.path.exists(schema_file):
        import subprocess
        try:
            subprocess.call(
                [
                    "glib-compile-schemas",
                    str(meld.conf.DATADIR),
                ],
                cwd=melddir
            )
        except FileNotFoundError:
            print("Warning: glib-compile-schemas command not found; skipping compilation.", file=sys.stderr)
        except Exception as e:
            print(f"Warning: glib-compile-schemas failed: {e}", file=sys.stderr)

try:
    meld.settings.create_settings()
except Exception as e:
    print(f"Warning: failed to create settings: {e}", file=sys.stderr)

from meld.meldapp import MeldApp


@pytest.fixture(scope="session")
def meld_app():
    orig_app_id = meld.conf.APPLICATION_ID
    meld.conf.APPLICATION_ID = f"{orig_app_id}.TestPid{os.getpid()}"
    try:
        app = MeldApp()
    finally:
        meld.conf.APPLICATION_ID = orig_app_id
    app.register(None)
    yield app
    app.quit()
