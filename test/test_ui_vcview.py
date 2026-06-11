import os
import subprocess
import pytest
from unittest import mock
from gi.repository import Gio
from meld.vcview import VcView
from meld.vc import _vc

def test_vcview_instantiation():
    vcview = VcView()
    assert vcview.model is not None
    assert vcview.treeview is not None

def test_vcview_scan_git(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), check=True)

    # 1. Create a committed file
    file_committed = repo_dir / "committed.txt"
    file_committed.write_text("initial content\n")
    subprocess.run(["git", "add", "committed.txt"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), check=True)

    # 2. Modify that committed file
    file_committed.write_text("modified content\n")

    # 3. Create an unversioned (untracked) file
    file_unversioned = repo_dir / "unversioned.txt"
    file_unversioned.write_text("new unversioned file\n")

    # 4. Create a staged/added file
    file_added = repo_dir / "added.txt"
    file_added.write_text("new added file\n")
    subprocess.run(["git", "add", "added.txt"], cwd=str(repo_dir), check=True)

    # Instantiate VcView
    vcview = VcView()
    # Explicitly enable unknown/untracked status filter so unversioned.txt is scanned and shown
    vcview.props.status_filters = ['flatten', 'modified', 'unknown', 'normal']
    vcview.set_location(str(repo_dir))

    # Run the VC scanning scheduler to completion
    vcview.scheduler.complete_tasks()

    # Traverse the tree model and check file states
    model = vcview.model
    assert len(model) > 0

    files_found = {}

    def traverse(model, it):
        while it:
            path = model.get_file_path(it)
            state = model.get_state(it, 0)
            if path:
                files_found[os.path.basename(path)] = state
            if model.iter_has_child(it):
                traverse(model, model.iter_children(it))
            it = model.iter_next(it)

    root_it = model.get_iter_first()
    traverse(model, root_it)

    # Verify that the files are present in the model with correct states
    assert "committed.txt" in files_found
    assert files_found["committed.txt"] == _vc.STATE_MODIFIED

    assert "unversioned.txt" in files_found
    assert files_found["unversioned.txt"] == _vc.STATE_NONE

    assert "added.txt" in files_found
    assert files_found["added.txt"] == _vc.STATE_NEW
