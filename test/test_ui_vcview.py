import os
import subprocess

import pytest

from meld.vc import _vc
from meld.vcview import VcView


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


@pytest.mark.skipif(os.name != 'nt', reason="os.path.normcase is case-sensitive on non-Windows")
def test_case_insensitive_path_dict():
    from meld.vc._vc import CaseInsensitivePathDefaultDict, CaseInsensitivePathDict

    d = CaseInsensitivePathDict()
    d["C:\\Path\\To\\File.txt"] = "val"
    assert d["c:\\path\\to\\file.txt"] == "val"
    assert "c:\\path\\to\\file.txt" in d

    dd = CaseInsensitivePathDefaultDict(set)
    dd["C:\\Path\\To\\Folder"].add("file.txt")
    assert "file.txt" in dd["c:\\path\\to\\folder"]


def test_commit_dialog(meld_app):
    vcview = VcView()
    import meld.vc.git
    vcview.vc = meld.vc.git.Vc(os.path.abspath('.'))
    vcview.location = vcview.vc.location

    from meld.ui.vcdialogs import CommitDialog
    dialog = CommitDialog()
    assert dialog is not None


def test_path_normalization_casing():
    from meld.vc._vc import Entry
    e = Entry("c:\\path\\to\\file.txt", "file.txt", 2, False)
    if os.name == 'nt':
        assert e.path.startswith("C:\\")
    else:
        assert e.path == os.path.realpath(os.path.abspath("c:\\path\\to\\file.txt"))


def test_is_in_repo_normalization(tmp_path):
    from meld.vc.git import Vc
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True)

    test_path = str(repo_dir)
    if os.name == 'nt' and test_path[0].isupper():
        test_path = test_path[0].lower() + test_path[1:]

    root, location = Vc.is_in_repo(test_path)
    if os.name == 'nt':
        assert root[0].isupper()
        assert location[0].isupper()


@pytest.mark.skipif(os.name != 'nt', reason="Path casing comparison is only case-insensitive on Windows")
def test_vcview_find_iter_by_name_casing():
    vcview = VcView()
    vcview.model.add_entries(None, ["C:\\path\\to\\file.txt"])
    found = vcview.find_iter_by_name("c:\\path\\to\\file.txt")
    assert found is not None


def test_vcview_scan_git_subdirectory(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), check=True)

    # Create a subdirectory
    sub_dir = repo_dir / "subdir"
    sub_dir.mkdir()

    # 1. Create a committed file in the subdirectory
    file_committed = sub_dir / "committed.txt"
    file_committed.write_text("initial content\n")
    subprocess.run(["git", "add", "subdir/committed.txt"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), check=True)

    # 2. Modify that committed file in the subdirectory
    file_committed.write_text("modified content\n")

    # Instantiate VcView
    vcview = VcView()
    # Explicitly enable status filters
    vcview.props.status_filters = ['flatten', 'modified', 'normal']

    # Test path casing: use lowercase drive letter if on Windows
    repo_dir_str = str(repo_dir)
    if os.name == 'nt' and repo_dir_str[0].isupper():
        repo_dir_str = repo_dir_str[0].lower() + repo_dir_str[1:]

    vcview.set_location(repo_dir_str)

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

    # Verify that the modified file in the subdirectory is found
    assert "committed.txt" in files_found
    assert files_found["committed.txt"] == _vc.STATE_MODIFIED


def test_vcview_run_diff_casing(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), check=True)

    file_path = repo_dir / "file.txt"
    file_path.write_text("hello\n")
    subprocess.run(["git", "add", "file.txt"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(repo_dir), check=True)

    file_path.write_text("hello world\n")

    vcview = VcView()
    repo_dir_str = str(repo_dir)
    if os.name == 'nt' and repo_dir_str[0].isupper():
        repo_dir_str = repo_dir_str[0].lower() + repo_dir_str[1:]

    vcview.set_location(repo_dir_str)
    vcview.scheduler.complete_tasks()

    file_path_str = str(file_path)
    if os.name == 'nt' and file_path_str[0].isupper():
        file_path_str = file_path_str[0].lower() + file_path_str[1:]

    diff_args = vcview.get_diff_arguments_by_path(file_path_str)
    assert diff_args is not None


def test_vcview_sibling_navigation_integration(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), check=True)

    # Create two committed files
    file_a = repo_dir / "file_a.txt"
    file_b = repo_dir / "file_b.txt"
    file_a.write_text("hello a\n")
    file_b.write_text("hello b\n")
    subprocess.run(["git", "add", "file_a.txt", "file_b.txt"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(repo_dir), check=True)

    # Modify both
    file_a.write_text("hello a modified\n")
    file_b.write_text("hello b modified\n")

    vcview = VcView()
    # ensure modified files are visible
    vcview.props.status_filters = ['flatten', 'modified']
    vcview.set_location(str(repo_dir))
    vcview.scheduler.complete_tasks()

    # Get diff arguments for file_a.txt
    gfiles, kwargs = vcview.get_diff_arguments_by_path(str(file_a))
    assert gfiles is not None

    # Instantiate FileDiff and set it up
    from meld.filediff import FileDiff
    filediff = FileDiff(len(gfiles))
    filediff.set_files(gfiles)
    if 'meta' in kwargs:
        filediff.set_meta(kwargs['meta'])

    # Verify initial navigation state (we are at file_a.txt, so we should be able to go to file_b.txt)
    action_prev = filediff.view_action_group.lookup_action('previous-file')
    action_next = filediff.view_action_group.lookup_action('next-file')

    assert action_prev is not None
    assert action_next is not None

    has_prev = action_prev.get_enabled()
    has_next = action_next.get_enabled()
    print(f"Initial: has_prev={has_prev}, has_next={has_next}")

    # They should not be both False if both files are modified and visible!
    assert has_prev or has_next

    if has_next:
        action_next.activate(None)
        filediff.scheduler.complete_tasks()
        assert filediff.meta['current_path'] is not None


def test_vcview_find_iter_by_name_casing_integration(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), check=True)

    file_a = repo_dir / "file_a.txt"
    file_a.write_text("hello\n")
    subprocess.run(["git", "add", "file_a.txt"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(repo_dir), check=True)

    vcview = VcView()
    vcview.props.status_filters = ['flatten', 'modified', 'unknown', 'normal']
    vcview.set_location(str(repo_dir))
    vcview.scheduler.complete_tasks()

    # Get path of file_a, but toggle the case of the first character (drive letter or first letter of path)
    path_str = str(file_a)
    if path_str[0].isalpha():
        toggled_char = path_str[0].lower() if path_str[0].isupper() else path_str[0].upper()
        toggled_path = toggled_char + path_str[1:]
    else:
        toggled_path = path_str

    # Currently, find_iter_by_name should find it regardless of casing if it is case-insensitive.
    # Let's assert that it is found.
    it = vcview.find_iter_by_name(toggled_path)
    assert it is not None



