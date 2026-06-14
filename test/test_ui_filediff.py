from gi.repository import Gio

from meld.filediff import FileDiff


def test_filediff_instantiation():
    filediff = FileDiff(2)
    assert filediff.num_panes == 2
    assert len(filediff.textbuffer) == 3  # Meld always creates 3 buffers internally
    assert len(filediff.textview) == 3
    assert filediff.grid is not None

def test_filediff_comparison_and_merge():
    filediff = FileDiff(2)
    
    buf0 = filediff.textbuffer[0]
    buf1 = filediff.textbuffer[1]

    # Set initial text
    buf0.set_text("line 1\nline 2 changed\nline 3\n")
    buf1.set_text("line 1\nline 2 original\nline 3\n")

    # Trigger comparison by calling set_files with None values to skip file loading but trigger comparison
    filediff.set_files([None, None])

    # Run the comparison scheduler tasks to completion
    filediff.scheduler.complete_tasks()

    # Get computed difference chunks between pane 0 and pane 1
    chunks = list(filediff.linediffer.pair_changes(0, 1))
    assert len(chunks) == 1
    
    chunk = chunks[0]
    # The chunk type should be 'replace' since line 2 differs
    assert chunk.tag == 'replace'
    assert chunk.start_a == 1
    assert chunk.end_a == 2
    assert chunk.start_b == 1
    assert chunk.end_b == 2

    # Simulate copy_chunk from pane 0 to pane 1
    filediff.replace_chunk(0, 1, chunk)

    # Verify that the text in pane 1 is updated to match pane 0
    start, end = buf1.get_bounds()
    assert buf1.get_text(start, end, False) == "line 1\nline 2 changed\nline 3\n"
    assert buf1.get_modified() is True

def test_filediff_delete_chunk():
    filediff = FileDiff(2)
    
    buf0 = filediff.textbuffer[0]
    buf1 = filediff.textbuffer[1]

    # Set initial text
    buf0.set_text("line 1\nline 2 to delete\nline 3\n")
    buf1.set_text("line 1\nline 3\n")

    # Trigger comparison
    filediff.set_files([None, None])
    filediff.scheduler.complete_tasks()

    # Get computed difference chunks
    chunks = list(filediff.linediffer.pair_changes(0, 1))
    assert len(chunks) == 1
    
    chunk = chunks[0]
    # The chunk in pane 0 is 'delete' relative to pane 1
    assert chunk.tag == 'delete'

    # Delete the chunk in pane 0
    filediff.delete_chunk(0, chunk)

    # Verify that the line was removed
    start, end = buf0.get_bounds()
    assert buf0.get_text(start, end, False) == "line 1\nline 3\n"

def test_filediff_save_file(tmp_path):
    import time

    from gi.repository import GLib

    from meld.meldbuffer import MeldBufferState

    # Create temporary files
    file_a_path = tmp_path / "file_a.txt"
    file_b_path = tmp_path / "file_b.txt"
    file_a_path.write_text("Hello World A\n")
    file_b_path.write_text("Hello World B\n")

    # Instantiate FileDiff
    filediff = FileDiff(2)

    # Set files
    file_a = Gio.File.new_for_path(str(file_a_path))
    file_b = Gio.File.new_for_path(str(file_b_path))
    filediff.set_files([file_a, file_b])

    # Wait for the files to load. Since file loading is async, we spin the GLib main context.
    context = GLib.MainContext.default()
    start_time = time.time()
    while (filediff.textbuffer[0].data.state != MeldBufferState.LOAD_FINISHED or
           filediff.textbuffer[1].data.state != MeldBufferState.LOAD_FINISHED):
        if time.time() - start_time > 2.0:
            raise TimeoutError("Loading files took too long")
        while context.pending():
            context.iteration(False)
        time.sleep(0.01)

    # Mock _get_focused_pane to return pane 0
    filediff._get_focused_pane = lambda: 0

    # Modify pane 0 buffer
    buf0 = filediff.textbuffer[0]
    buf0.set_text("Hello Modified World\n")
    assert buf0.get_modified() is True
    filediff._set_save_action_sensitivity()

    # Retrieve the 'save' action
    action = filediff.view_action_group.lookup_action('save')
    assert action is not None

    # Activate the 'save' action
    action.activate(None)

    # Spin GLib main loop until the buffer is no longer modified
    start_time = time.time()
    while buf0.get_modified():
        if time.time() - start_time > 2.0:
            raise TimeoutError("Saving file took too long")
        while context.pending():
            context.iteration(False)
        time.sleep(0.01)

    # Verify that the file content on disk has been updated
    assert file_a_path.read_text().strip() == "Hello Modified World"


def test_filediff_exit_code_no_output():
    filediff = FileDiff(2)
    
    emitted_code = None
    def on_close(obj, exit_code):
        nonlocal emitted_code
        emitted_code = exit_code
    filediff.close_signal.connect(on_close)
    
    filediff.on_delete_event()
    assert emitted_code == 0


def test_filediff_exit_code_with_output_not_saved():
    filediff = FileDiff(3)
    filediff.set_merge_output_file(Gio.File.new_for_path("dummy"))
    
    emitted_code = None
    def on_close(obj, exit_code):
        nonlocal emitted_code
        emitted_code = exit_code
    filediff.close_signal.connect(on_close)
    
    filediff.on_delete_event()
    assert emitted_code == 1


def test_filediff_exit_code_with_output_saved():
    filediff = FileDiff(3)
    filediff.set_merge_output_file(Gio.File.new_for_path("dummy"))
    filediff.merge_output_saved = True
    
    emitted_code = None
    def on_close(obj, exit_code):
        nonlocal emitted_code
        emitted_code = exit_code
    filediff.close_signal.connect(on_close)
    
    filediff.on_delete_event()
    assert emitted_code == 0


def test_filediff_exit_code_with_output_saved_but_modified():
    from gi.repository import Gtk
    filediff = FileDiff(3)
    filediff.set_merge_output_file(Gio.File.new_for_path("dummy"))
    filediff.merge_output_saved = True
    
    # Modify buffer
    filediff.textbuffer[1].set_text("unsaved modifications")
    # Mock check_save_modified to simulate choosing "Close without Saving" (returning OK)
    filediff.check_save_modified = lambda *args: Gtk.ResponseType.OK
    
    emitted_code = None
    def on_close(obj, exit_code):
        nonlocal emitted_code
        emitted_code = exit_code
    filediff.close_signal.connect(on_close)
    
    filediff.on_delete_event()
    assert emitted_code == 1


def test_filediff_auto_merge_conflict_free(tmp_path):
    import time

    from gi.repository import GLib

    from meld.const import FileComparisonMode
    from meld.meldbuffer import MeldBufferState
    
    file_l = tmp_path / "left.txt"
    file_m = tmp_path / "mid.txt"
    file_r = tmp_path / "right.txt"
    out_path = tmp_path / "output.txt"
    
    # Conflict-free 3-way merge
    file_l.write_text("line 1 left\nline 2\nline 3\n")
    file_m.write_text("line 1\nline 2\nline 3\n")
    file_r.write_text("line 1\nline 2\nline 3 right\n")
    
    filediff = FileDiff(3, comparison_mode=FileComparisonMode.AutoMerge)
    filediff.set_files([
        Gio.File.new_for_path(str(file_l)),
        Gio.File.new_for_path(str(file_m)),
        Gio.File.new_for_path(str(file_r)),
    ])
    filediff.set_merge_output_file(Gio.File.new_for_path(str(out_path)))
    
    emitted_code = None
    def on_close(obj, exit_code):
        nonlocal emitted_code
        emitted_code = exit_code
    filediff.close_signal.connect(on_close)
    
    # Wait for loading to finish
    context = GLib.MainContext.default()
    start_time = time.time()
    while any(buf.data.state != MeldBufferState.LOAD_FINISHED for buf in filediff.textbuffer[:3]):
        if time.time() - start_time > 3.0:
            raise TimeoutError("Loading files took too long")
        while context.pending():
            context.iteration(False)
        time.sleep(0.01)
        
    # Execute the comparison and auto-merge tasks
    filediff.scheduler.complete_tasks()
    
    # Wait for saving and close_signal emission
    start_time = time.time()
    while emitted_code is None:
        if time.time() - start_time > 3.0:
            raise TimeoutError("Auto-merge save/close took too long")
        while context.pending():
            context.iteration(False)
        time.sleep(0.01)
        
    assert emitted_code == 0
    assert out_path.read_text() == "line 1 left\nline 2\nline 3 right\n"


def test_filediff_conflict_badge():
    filediff = FileDiff(3)
    
    # Verify initial state of middle pane status bar conflict label
    assert filediff.statusbar[1].conflict_label.props.visible is False
    
    # Update conflict count and verify badge visibility/text
    filediff.statusbar[1].set_conflict_count(5)
    assert filediff.statusbar[1].conflict_label.props.visible is True
    assert "5 conflicts" in filediff.statusbar[1].conflict_label.get_text()
    
    # Reset conflict count and verify it hides
    filediff.statusbar[1].set_conflict_count(0)
    assert filediff.statusbar[1].conflict_label.props.visible is False


def test_filediff_conflict_menu():
    filediff = FileDiff(3)
    
    # Verify that the action gutter is associated with the FileDiff instance
    gutter = filediff.actiongutter[0]
    assert gutter.filediff == filediff
    
    # Mock a conflict chunk: (type, start_a, end_a, start_b, end_b)
    conflict_chunk = ('conflict', 1, 2, 1, 2)
    
    # Generate conflict menu
    menu = gutter._make_conflict_menu(conflict_chunk)
    assert menu is not None
    
    # Verify menu items exist and have correct labels
    box = menu.box
    items = []
    child = box.get_first_child()
    while child is not None:
        items.append(child)
        child = child.get_next_sibling()
        
    assert len(items) == 4
    assert "Keep Left" in items[0].props.label
    assert "Keep Right" in items[1].props.label
    assert "Keep Both" in items[2].props.label
    assert "Keep Both" in items[3].props.label


def test_scheduler_unhashable_task():
    from meld.task import FifoScheduler
    
    scheduler = FifoScheduler()
    
    # Define a custom unhashable class
    class UnhashableTask:
        def __init__(self):
            self.called = False
        def __call__(self):
            self.called = True
            return False
        def __hash__(self):
            raise TypeError("unhashable type")
            
    task = UnhashableTask()
    
    # Should not raise TypeError during add or remove
    scheduler.add_task(task)
    scheduler.remove_task(task)
    
    # Let's add it again and run it
    scheduler.add_task(task)
    assert not task.called
    scheduler.iteration()
    assert task.called


def test_filediff_actions_no_chunk():
    filediff = FileDiff(3)
    # Ensure chunk is None
    filediff.cursor.chunk = None
    
    # The following action methods should return early without throwing ValueError
    filediff.action_push_change_left()
    filediff.action_push_change_right()
    filediff.action_pull_change_left()
    filediff.action_pull_change_right()
    filediff.action_copy_change_left_up()
    filediff.action_copy_change_right_up()
    filediff.action_copy_change_left_down()
    filediff.action_copy_change_right_down()


