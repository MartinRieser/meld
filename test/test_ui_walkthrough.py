from meld.dirdiff import DirDiff
from meld.filediff import FileDiff
from meld.meldwindow import MeldWindow
from meld.newdifftab import DiffType, NewDiffTab


def test_gui_walkthrough(meld_app):
    app = meld_app
    window = MeldWindow()
    app.add_window(window)

    # 1. New comparison tab interactions
    new_tab = window.append_new_comparison()
    assert window.tabview.get_n_pages() == 1
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
    assert window.tabview.get_n_pages() == 1

    file_diff = window.tabview.get_nth_page(0).get_child()
    assert isinstance(file_diff, FileDiff)

    # Switch page to FileDiff
    window.tabview.set_selected_page(window.tabview.get_nth_page(0))
    window.on_notify_selected_page(window.tabview, None)

    # Interact with FileDiff actions when no chunk is selected
    # Upstream design raises ValueError when executing actions without an active chunk.
    # We wrap them in try-except to verify the methods execute without crashing on internal UI state.
    for action_method, *args in [
        (file_diff.action_push_change_left,),
        (file_diff.action_push_change_right,),
        (file_diff.action_pull_change_left,),
        (file_diff.action_pull_change_right,),
        (file_diff.action_copy_change_left_up,),
        (file_diff.action_copy_change_right_up,),
        (file_diff.action_copy_change_left_down,),
        (file_diff.action_copy_change_right_down,),
        (file_diff.action_delete_change, 0),
    ]:
        try:
            action_method(*args)
        except ValueError:
            pass

    file_diff.action_previous_conflict()
    file_diff.action_next_conflict()
    file_diff.action_previous_diff()
    file_diff.action_next_diff()

    # Append another new comparison
    new_tab2 = window.append_new_comparison()
    assert window.tabview.get_n_pages() == 2
    assert isinstance(new_tab2, NewDiffTab)

    # Switch to the new tab page (index 1)
    window.tabview.set_selected_page(window.tabview.get_nth_page(1))
    window.on_notify_selected_page(window.tabview, None)

    # Switch to folder tab
    new_tab2.button_type_dir.set_active(True)
    new_tab2.on_button_type_toggled(new_tab2.button_type_dir)

    # Open new blank folder comparison (replaces new_tab2)
    new_tab2.on_button_new_blank_clicked()
    assert window.tabview.get_n_pages() == 2
    dir_diff = window.tabview.get_nth_page(1).get_child()
    assert isinstance(dir_diff, DirDiff)

    # Switch to DirDiff
    window.tabview.set_selected_page(window.tabview.get_nth_page(1))
    window.on_notify_selected_page(window.tabview, None)

    # Close pages one by one
    window.action_close(None)
    assert window.tabview.get_n_pages() == 1

    window.tabview.set_selected_page(window.tabview.get_nth_page(0))
    window.action_close(None)
    assert window.tabview.get_n_pages() == 0
