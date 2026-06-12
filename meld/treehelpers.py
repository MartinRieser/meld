# Copyright (C) 2002-2006 Stephen Kennedy <stevek@gnome.org>
# Copyright (C) 2011-2016 Kai Willadsen <kai.willadsen@gmail.com>
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

"""Helper utilities for working with GtkTreeStore and GtkTreePath."""

from typing import Any, Callable, Generator, List, Optional, Tuple

from gi.repository import Gtk


def tree_path_as_tuple(path: Gtk.TreePath) -> Tuple[int, ...]:
    """Get the path indices as a tuple.

    This helper only exists because we often want to use tree paths
    as set members or dictionary keys, and this is a convenient option.
    """
    return tuple(path.get_indices())


def tree_path_prev(path: List[int]) -> Optional[List[int]]:
    """Return the tree path of the previous sibling at the same depth level."""
    if not path or path[-1] == 0:
        return None
    return path[:-1] + [path[-1] - 1]


def tree_path_up(path: List[int]) -> Optional[List[int]]:
    """Return the parent tree path by moving up one level in depth."""
    if not path:
        return None
    return path[:-1]


def valid_path(model: Gtk.TreeModel, path: Any) -> bool:
    """Check if the tree path is valid within the tree model."""
    try:
        model.get_iter(path)
        return True
    except ValueError:
        return False


def refocus_deleted_path(model: Gtk.TreeModel, path: List[int]) -> Optional[List[int]]:
    """Find a new valid path to focus when the current path is deleted.

    It tries the following options in order:
    1. The successor path (which now occupies the deleted path's index).
    2. The predecessor sibling (immediate or earlier).
    3. The closest valid parent path.
    """
    if valid_path(model, path):
        return path

    new_path = tree_path_prev(path)
    while new_path:
        if valid_path(model, new_path):
            return new_path
        new_path = tree_path_prev(new_path)

    new_path = tree_path_up(path)
    while new_path:
        if valid_path(model, new_path):
            return new_path
        new_path = tree_path_up(new_path)
    return None


class SearchableTreeStore(Gtk.TreeStore):
    """Subclass of Gtk.TreeStore with helper methods for searching and traversing."""

    def inorder_search_down(self, it: Gtk.TreeIter) -> Generator[Gtk.TreeIter, None, None]:
        """Perform a depth-first traversal downwards starting from the given iterator."""
        while it:
            child = self.iter_children(it)
            if child:
                it = child
            else:
                next_it = self.iter_next(it)
                if next_it:
                    it = next_it
                else:
                    while True:
                        it = self.iter_parent(it)
                        if not it:
                            return
                        next_it = self.iter_next(it)
                        if next_it:
                            it = next_it
                            break
            yield it

    def inorder_search_up(self, it: Gtk.TreeIter) -> Generator[Gtk.TreeIter, None, None]:
        """Perform a depth-first traversal upwards starting from the given iterator."""
        while it:
            path = self.get_path(it)
            indices = path.get_indices()
            if indices[-1]:
                new_indices = list(indices[:-1]) + [indices[-1] - 1]
                it = self.get_iter(Gtk.TreePath.new_from_indices(new_indices))
                while 1:
                    nc = self.iter_n_children(it)
                    if nc:
                        it = self.iter_nth_child(it, nc - 1)
                    else:
                        break
            else:
                up = self.iter_parent(it)
                if up:
                    it = up
                else:
                    return
            yield it

    def get_previous_next_paths(
        self, path: Gtk.TreePath, match_func: Callable[[Gtk.TreeIter], bool]
    ) -> Tuple[Optional[Gtk.TreePath], Optional[Gtk.TreePath]]:
        """Find the closest matching previous and next paths matching the given function."""
        prev_path, next_path = None, None
        try:
            start_iter = self.get_iter(path)
        except ValueError:
            # Invalid tree path
            return None, None

        for it in self.inorder_search_up(start_iter):
            if match_func(it):
                prev_path = self.get_path(it)
                break

        for it in self.inorder_search_down(start_iter):
            if match_func(it):
                next_path = self.get_path(it)
                break

        return prev_path, next_path
