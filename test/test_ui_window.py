import pytest
from gi.repository import Gio, Gtk
from meld.meldapp import MeldApp
from meld.meldwindow import MeldWindow
from meld.newdifftab import NewDiffTab
from meld.filediff import FileDiff

def test_meld_window_creation():
    app = MeldApp()
    app.register(None)  # Register application to trigger startup/registration safely
    
    window = MeldWindow()
    app.add_window(window)

    assert window.get_application() == app
    # Check that template children are initialized
    assert window.notebook is not None
    assert window.spinner is not None

def test_meld_window_tabs():
    app = MeldApp()
    app.register(None)
    
    window = MeldWindow()
    app.add_window(window)

    # Initial window doesn't have pages until we add some
    assert window.notebook.get_n_pages() == 0

    # 1. Append a new comparison (creates a NewDiffTab)
    window.append_new_comparison()
    assert window.notebook.get_n_pages() == 1
    page1 = window.notebook.get_nth_page(0)
    assert isinstance(page1, NewDiffTab)

    # 2. Append a file diff tab
    file_a = Gio.File.new_for_path("dummy_a.txt")
    file_b = Gio.File.new_for_path("dummy_b.txt")
    window.append_filediff([file_a, file_b])
    
    assert window.notebook.get_n_pages() == 2
    page2 = window.notebook.get_nth_page(1)
    assert isinstance(page2, FileDiff)

    # Verify active page index and switching
    window.notebook.set_current_page(0)
    # Since NewDiffTab is not a MeldDoc, current_doc() returns a DummyDoc
    assert not isinstance(window.current_doc(), FileDiff)

    window.notebook.set_current_page(1)
    assert window.current_doc() == page2

    # Close current page (page2: FileDiff)
    window.action_close(None, None)
    assert window.notebook.get_n_pages() == 1
    page_left = window.notebook.get_nth_page(0)
    assert isinstance(page_left, NewDiffTab)

def test_meld_window_actions():
    app = MeldApp()
    app.register(None)

    window = MeldWindow()
    app.add_window(window)

    # Initially, no pages
    assert window.notebook.get_n_pages() == 0

    # 1. Trigger "new-tab" action
    action = window.lookup_action("new-tab")
    assert action is not None
    action.activate(None)

    assert window.notebook.get_n_pages() == 1
    page = window.notebook.get_nth_page(0)
    assert isinstance(page, NewDiffTab)

    # 2. Trigger "close" action
    close_action = window.lookup_action("close")
    assert close_action is not None
    close_action.activate(None)

    assert window.notebook.get_n_pages() == 0
