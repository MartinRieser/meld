import os
from unittest import mock

from gi.repository import Gio

from meld.dirdiff import DirDiff


def test_dirdiff_instantiation():
    dirdiff = DirDiff(2)
    assert dirdiff.num_panes == 2
    assert dirdiff.model is not None
    assert len(dirdiff.treeview) == 3  # Meld always creates 3 treeviews internally

def test_dirdiff_scan_and_activation(tmp_path):
    # Setup temporary directories
    dir_a = tmp_path / "dir_a"
    dir_b = tmp_path / "dir_b"
    dir_a.mkdir()
    dir_b.mkdir()

    # Create files
    file1_a = dir_a / "file1.txt"
    file1_b = dir_b / "file1.txt"
    file1_a.write_text("hello")
    file1_b.write_text("hello different")  # differing contents

    file2_a = dir_a / "file2.txt"
    file2_a.write_text("only in A")

    file3_b = dir_b / "file3.txt"
    file3_b.write_text("only in B")

    # Instantiate DirDiff
    dirdiff = DirDiff(2)

    # Set comparison directories using on_file_selected
    dirdiff.on_file_selected(None, 0, Gio.File.new_for_path(str(dir_a)))
    dirdiff.on_file_selected(None, 1, Gio.File.new_for_path(str(dir_b)))

    # Run the scanning scheduler to completion
    dirdiff.scheduler.complete_tasks()

    # Traverse the tree model
    model = dirdiff.model
    assert len(model) > 0

    # Retrieve all files in the model
    files_found = []
    
    def traverse(model, it):
        while it:
            paths = model.value_paths(it)
            files_found.append(paths)
            if model.iter_has_child(it):
                traverse(model, model.iter_children(it))
            it = model.iter_next(it)

    root_it = model.get_iter_first()
    traverse(model, root_it)

    # Verify that the files are present in the model paths, filtering by existence on disk
    basenames = []
    for p in files_found:
        name_a = os.path.basename(p[0]) if (p[0] and os.path.exists(p[0])) else None
        name_b = os.path.basename(p[1]) if (p[1] and os.path.exists(p[1])) else None
        basenames.append((name_a, name_b))
    
    assert ("file1.txt", "file1.txt") in basenames
    assert ("file2.txt", None) in basenames
    assert (None, "file3.txt") in basenames

    # Test double-clicking / activating a row to trigger file comparison
    mock_callback = mock.Mock()
    dirdiff.create_diff_signal.connect(mock_callback)

    # Find the row path for file1.txt
    file1_path = None
    it = model.get_iter_first()
    # Find child iter for file1.txt
    child = model.iter_children(it)
    while child:
        paths = model.value_paths(child)
        if paths[0] and os.path.basename(paths[0]) == "file1.txt":
            file1_path = model.get_path(child)
            break
        child = model.iter_next(child)

    assert file1_path is not None

    # Simulate treeview row activation
    dirdiff.on_treeview_row_activated(dirdiff.treeview[0], file1_path, None)

    # Assert that create_diff_signal was emitted with the correct Gio.File arguments
    assert mock_callback.called
    args, kwargs = mock_callback.call_args
    # args[1] is the gfiles list
    gfiles = args[1]
    assert len(gfiles) == 2
    assert gfiles[0].get_basename() == "file1.txt"
    assert gfiles[1].get_basename() == "file1.txt"
