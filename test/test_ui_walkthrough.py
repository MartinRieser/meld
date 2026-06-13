import pytest
from gi.repository import Gio, Gtk

from meld.dirdiff import DirDiff
from meld.filediff import FileDiff
from meld.meldapp import MeldApp
from meld.meldwindow import MeldWindow
from meld.newdifftab import NewDiffTab, DiffType




def test_gui_walkthrough(meld_app):
    app = meld_app
    window = MeldWindow()
    app.add_window(window)

    # 1. New comparison tab interactions
    new_tab = window.append_new_comparison()
    assert window.notebook.get_n_pages() == 1
    assert isinstance(new_tab, NewDiffTab)

    # Toggle type buttons
    new_tab.button_type_file.set_active(True)
    new_tab.on_button_type_toggled(new_tab.button_type_file)
    assert new_tab.diff_type == DiffType.File

    new_tab.button_type_dir.set_active(True)
    new_tab.on_button_type_toggled(new_tab.button_type_dir)
    assert new_tab.diff_type == DiffType.Folder

    new_tab.button_type_vc.set_active(True)
    new_tab.on_button_type_toggled(new_tab.button_type_vc)
    assert new_tab.diff_type == DiffType.Version

    # Switch back to file diff
    new_tab.button_type_file.set_active(True)
    new_tab.on_button_type_toggled(new_tab.button_type_file)

    # Click "New Blank" to create a new FileDiff
    new_tab.on_button_new_blank_clicked()
    # Creating a new blank comparison closes/replaces the "New comparison" tab
    assert window.notebook.get_n_pages() == 1

    file_diff = window.notebook.get_nth_page(0)
    assert isinstance(file_diff, FileDiff)

    # Switch page to FileDiff
    window.notebook.set_current_page(0)
    window.after_switch_page(window.notebook, file_diff, 0)

    # Interact with FileDiff actions when no chunk is selected
    file_diff.action_push_change_left()
    file_diff.action_push_change_right()
    file_diff.action_pull_change_left()
    file_diff.action_pull_change_right()
    file_diff.action_copy_change_left_up()
    file_diff.action_copy_change_right_up()
    file_diff.action_copy_change_left_down()
    file_diff.action_copy_change_right_down()
    file_diff.action_delete_change()
    file_diff.action_previous_conflict()
    file_diff.action_next_conflict()
    file_diff.action_previous_diff()
    file_diff.action_next_diff()

    # Append another new comparison
    new_tab2 = window.append_new_comparison()
    assert window.notebook.get_n_pages() == 2
    assert isinstance(new_tab2, NewDiffTab)

    # Switch to the new tab page (index 1)
    window.notebook.set_current_page(1)
    window.after_switch_page(window.notebook, new_tab2, 1)

    # Switch to folder tab
    new_tab2.button_type_dir.set_active(True)
    new_tab2.on_button_type_toggled(new_tab2.button_type_dir)
    
    # Open new blank folder comparison (replaces new_tab2)
    new_tab2.on_button_new_blank_clicked()
    assert window.notebook.get_n_pages() == 2
    dir_diff = window.notebook.get_nth_page(1)
    assert isinstance(dir_diff, DirDiff)

    # Switch to DirDiff
    window.notebook.set_current_page(1)
    window.after_switch_page(window.notebook, dir_diff, 1)

    # Close pages one by one
    window.action_close()
    assert window.notebook.get_n_pages() == 1
    
    window.notebook.set_current_page(0)
    window.action_close()
    assert window.notebook.get_n_pages() == 0


def test_infobar_compatibility():
    from gi.repository import Gtk
    
    infobar = Gtk.InfoBar()
    
    # Verify our monkey-patches exist and return Gtk.Box objects
    content_area = infobar.get_content_area()
    action_area = infobar.get_action_area()
    
    assert isinstance(content_area, Gtk.Box)
    assert isinstance(action_area, Gtk.Box)
