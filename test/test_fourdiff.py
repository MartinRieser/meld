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

"""Unit tests for meld.fourdiff."""

from gi.repository import Gio

from meld.fourdiff import FourDiff


def test_fourdiff_instantiation():
    fourdiff = FourDiff()
    assert fourdiff.filediff_left is not None
    assert fourdiff.filediff_right is not None
    assert fourdiff.filediff_left.num_panes == 2
    assert fourdiff.filediff_right.num_panes == 2


def test_fourdiff_set_files(tmp_path):
    files = []
    for i in range(4):
        p = tmp_path / f"file_{i}.txt"
        p.write_text(f"content {i}")
        files.append(Gio.File.new_for_path(str(p)))

    fourdiff = FourDiff()
    fourdiff.set_files(files)

    # Verify writeability / editable states on text views
    assert fourdiff.filediff_left.textview[0].get_editable() is False
    assert fourdiff.filediff_left.textview[1].get_editable() is True
    assert fourdiff.filediff_right.textview[0].get_editable() is False
    assert fourdiff.filediff_right.textview[1].get_editable() is False


def test_fourdiff_open_paths(meld_app, tmp_path):
    from meld.meldwindow import MeldWindow
    window = MeldWindow()
    meld_app.add_window(window)

    files = []
    for i in range(4):
        p = tmp_path / f"file_{i}.txt"
        p.write_text(f"content {i}")
        files.append(Gio.File.new_for_path(str(p)))

    tab = window.open_paths(files)
    assert tab is not None
    assert window.notebook.get_n_pages() == 1
    assert window.notebook.get_nth_page(0) == tab
    from meld.fourdiff import FourDiff
    assert isinstance(tab, FourDiff)

