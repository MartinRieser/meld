
import importlib.machinery
import importlib.util
import sys
from unittest import mock

import meld.ui.gtkcompat

import pytest


@pytest.fixture(autouse=True)
def default_icon_theme():
    # Our tests need to run on a system with no default display, so all
    # our display-specific get_default() stuff will break.

    from gi.repository import Gtk
    with mock.patch(
            'gi.repository.Gtk.IconTheme.get_default',
            mock.Mock(spec=Gtk.IconTheme.get_default)):
        yield


@pytest.fixture(autouse=True)
def template_resources():
    import gi  # noqa: F401
    with mock.patch(
            'gi._gtktemplate.validate_resource_path',
            mock.Mock(return_value=True)):
        yield


def import_meld_conf():
    loader = importlib.machinery.SourceFileLoader(
        'meld.conf', './meld/conf.py.in')
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)

    import meld
    meld.conf = mod
    sys.modules['meld.conf'] = mod


import_meld_conf()


def setup_test_resources_and_settings():
    import os
    import subprocess
    from gi.repository import Gio, GtkSource
    import meld
    from meld.settings import create_settings

    meld.conf.uninstalled()
    melddir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    # Compile and load resources
    resource_filename = meld.conf.APPLICATION_ID + ".gresource"
    resource_file = os.path.join(meld.conf.DATADIR, resource_filename)

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
    except Exception as e:
        print("Failed glib-compile-resources:", e)

    try:
        resources = Gio.resource_load(resource_file)
        Gio.resources_register(resources)
    except Exception as e:
        print("Failed loading resource:", e)

    # Compile schemas
    try:
        subprocess.call(["glib-compile-schemas", meld.conf.DATADIR], cwd=melddir)
    except Exception as e:
        print("Failed glib-compile-schemas:", e)

    # Style Scheme paths
    style_path = os.path.join(meld.conf.DATADIR, "styles")
    if not os.path.exists(style_path):
        os.makedirs(style_path, exist_ok=True)
    GtkSource.StyleSchemeManager.get_default().append_search_path(style_path)

    for style in {'meld-base', 'meld-dark'}:
        path = os.path.join(style_path, '{}.style-scheme.xml'.format(style))
        if not os.path.exists(path):
            import shutil
            shutil.copyfile(os.path.join(melddir, 'data/styles', '{}.style-scheme.xml.in'.format(style)), path)

    # Initialize GSettings settings
    create_settings()


setup_test_resources_and_settings()

