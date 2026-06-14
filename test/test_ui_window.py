from gi.repository import Gio

from meld.filediff import FileDiff
from meld.meldwindow import MeldWindow
from meld.newdifftab import NewDiffTab


def test_meld_window_creation(meld_app):
    app = meld_app
    window = MeldWindow()
    app.add_window(window)

    assert window.get_application() == app
    assert window.notebook is not None
    assert window.spinner is not None


def test_meld_window_tabs(meld_app):
    app = meld_app
    window = MeldWindow()
    app.add_window(window)

    assert window.notebook.get_n_pages() == 0

    window.append_new_comparison()
    assert window.notebook.get_n_pages() == 1
    page1 = window.notebook.get_nth_page(0)
    assert isinstance(page1, NewDiffTab)

    file_a = Gio.File.new_for_path("dummy_a.txt")
    file_b = Gio.File.new_for_path("dummy_b.txt")
    window.append_filediff([file_a, file_b])

    assert window.notebook.get_n_pages() == 2
    page2 = window.notebook.get_nth_page(1)
    assert isinstance(page2, FileDiff)

    window.notebook.set_current_page(0)
    assert not isinstance(window.current_doc(), FileDiff)

    window.notebook.set_current_page(1)
    assert window.current_doc() == page2

    window.action_close(None, None)
    assert window.notebook.get_n_pages() == 1
    page_left = window.notebook.get_nth_page(0)
    assert isinstance(page_left, NewDiffTab)


def test_meld_window_actions(meld_app):
    app = meld_app
    window = MeldWindow()
    app.add_window(window)

    assert window.notebook.get_n_pages() == 0

    action = window.lookup_action("new-tab")
    assert action is not None
    action.activate(None)

    assert window.notebook.get_n_pages() == 1
    page = window.notebook.get_nth_page(0)
    assert isinstance(page, NewDiffTab)

    close_action = window.lookup_action("close")
    assert close_action is not None
    close_action.activate(None)

    assert window.notebook.get_n_pages() == 0
