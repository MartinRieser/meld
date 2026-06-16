# Copyright (C) 2026 Meld contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Experimental 4-pane merge interface for conflict resolution."""

import logging
from typing import Any, Dict, Sequence

from gi.repository import Gio, Gtk

from meld.filediff import FileDiff
from meld.melddoc import MeldDoc

log = logging.getLogger(__name__)


@Gtk.Template(resource_path='/org/gnome/meld/ui/fourdiff.ui')
class FourDiff(Gtk.Box, MeldDoc):
    """A 4-pane comparison tab orchestrating two side-by-side FileDiff widgets.

    The left FileDiff compares LOCAL vs. MERGED.
    The right FileDiff compares BASE vs. REMOTE.
    Scrolling is synchronized across all 4 panes.
    """
    __gtype_name__ = "FourDiff"

    close_signal = MeldDoc.close_signal
    create_diff_signal = MeldDoc.create_diff_signal
    file_changed_signal = MeldDoc.file_changed_signal
    label_changed = MeldDoc.label_changed
    move_diff = MeldDoc.move_diff
    tab_state_changed = MeldDoc.tab_state_changed

    paned_main = Gtk.Template.Child()

    def __init__(self):
        Gtk.Box.__init__(self)
        MeldDoc.__init__(self)

        self.filediff_left = FileDiff(2)
        self.filediff_right = FileDiff(2)

        self.paned_main.set_start_child(self.filediff_left)
        self.paned_main.set_end_child(self.filediff_right)

        self._sync_lock = False

        # Connect adjustments for scroll synchronization
        def sync_left_to_right(adj):
            if self._sync_lock:
                return
            self._sync_lock = True
            try:
                val = adj.get_value()
                for sw in self.filediff_right.scrolledwindow:
                    sw.get_vadjustment().set_value(val)
            finally:
                self._sync_lock = False

        def sync_right_to_left(adj):
            if self._sync_lock:
                return
            self._sync_lock = True
            try:
                val = adj.get_value()
                for sw in self.filediff_left.scrolledwindow:
                    sw.get_vadjustment().set_value(val)
            finally:
                self._sync_lock = False

        for sw in self.filediff_left.scrolledwindow:
            sw.get_vadjustment().connect('value-changed', sync_left_to_right)
        for sw in self.filediff_right.scrolledwindow:
            sw.get_vadjustment().connect('value-changed', sync_right_to_left)

        # Force read-only state for LOCAL, BASE, REMOTE panes
        self._make_read_only(self.filediff_left, 0)
        self._make_read_only(self.filediff_right, 0)
        self._make_read_only(self.filediff_right, 1)

    def _make_read_only(self, filediff, pane):
        buf = filediff.textbuffer[pane]
        original_update = filediff.update_buffer_writable

        def new_update(b):
            if b == buf:
                filediff.set_buffer_editable(b, False)
                filediff.readonlytoggle[pane].props.visible = False
            else:
                original_update(b)

        filediff.update_buffer_writable = new_update
        filediff.set_buffer_editable(buf, False)
        filediff.readonlytoggle[pane].props.visible = False

    def set_files(self, gfiles: Sequence[Gio.File], encodings=None):
        assert len(gfiles) == 4
        encs = encodings or [None] * 4

        # Left pair: LOCAL (0) vs MERGED (3)
        self.filediff_left.set_files([gfiles[0], gfiles[3]], [encs[0], encs[3]])
        # Right pair: BASE (1) vs REMOTE (2)
        self.filediff_right.set_files([gfiles[1], gfiles[2]], [encs[1], encs[2]])

        # Force read-only state for LOCAL, BASE, REMOTE
        self.filediff_left.set_buffer_editable(self.filediff_left.textbuffer[0], False)
        self.filediff_right.set_buffer_editable(self.filediff_right.textbuffer[0], False)
        self.filediff_right.set_buffer_editable(self.filediff_right.textbuffer[1], False)

        # Synchronize tab labels
        self.set_labels([
            gfiles[0].get_basename(),
            gfiles[1].get_basename(),
            gfiles[2].get_basename(),
            gfiles[3].get_basename(),
        ])

    def set_meta(self, meta: Dict[str, Any]):
        self.filediff_left.set_meta(meta)
        self.filediff_right.set_meta(meta)

    def on_container_close_request(self) -> int:
        # Check if Left/Right have unsaved changes
        left_res = self.filediff_left.on_container_close_request()
        right_res = self.filediff_right.on_container_close_request()
        if left_res == Gtk.ResponseType.CANCEL or right_res == Gtk.ResponseType.CANCEL:
            return Gtk.ResponseType.CANCEL
        return Gtk.ResponseType.OK
