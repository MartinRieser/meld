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

import logging
import os
import subprocess
import threading

from gi.repository import GLib, GtkSource, Pango

from meld.vc._vc import SafePopen

log = logging.getLogger(__name__)


def parse_git_blame(porcelain_output: str) -> list[dict]:
    lines = porcelain_output.splitlines()
    commits = {}
    line_infos = []

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith('\t'):
            i += 1
            continue

        parts = line.split()
        if not parts:
            i += 1
            continue

        sha = parts[0]
        if sha not in commits:
            commits[sha] = {
                "sha": sha[:8],
                "author": "Unknown",
                "date": "",
                "summary": ""
            }

        if sha == "0000000000000000000000000000000000000000":
            commits[sha] = {
                "sha": "Uncommitted",
                "author": "You",
                "date": "Today",
                "summary": "Uncommitted changes"
            }

        i += 1
        while i < n and not lines[i].startswith('\t'):
            header_line = lines[i]
            if sha != "0000000000000000000000000000000000000000":
                if header_line.startswith('author '):
                    commits[sha]['author'] = header_line[len('author '):].strip()
                elif header_line.startswith('author-time '):
                    import datetime
                    try:
                        time_val = int(header_line[len('author-time '):].strip())
                        date_str = datetime.date.fromtimestamp(time_val).strftime('%Y-%m-%d')
                        commits[sha]['date'] = date_str
                    except Exception:
                        pass
                elif header_line.startswith('summary '):
                    commits[sha]['summary'] = header_line[len('summary '):].strip()
            i += 1

        line_infos.append(commits[sha])
        if i < n:
            i += 1

    return line_infos


def fetch_blame_async(filepath: str, buffer_text: str, callback) -> None:
    def run_blame():
        try:
            from meld.vc.git import Vc as GitVc
            dirpath = os.path.dirname(filepath)
            git_vc = GitVc(dirpath)

            relpath = os.path.relpath(filepath, git_vc.location)
            cmd = ["git", "blame", "--contents", "-", "--porcelain", relpath]
            proc = SafePopen(
                cmd, cwd=git_vc.location,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            stdout, stderr = proc.communicate(input=buffer_text)
            if proc.returncode == 0:
                blame_data = parse_git_blame(stdout)
                GLib.idle_add(callback, blame_data)
            else:
                log.warning("git blame returned exit code %d for %s", proc.returncode, filepath)
                GLib.idle_add(callback, None)
        except Exception as e:
            log.warning("Git blame failed for %s: %s", filepath, e)
            GLib.idle_add(callback, None)

    threading.Thread(target=run_blame, daemon=True).start()


class GutterRendererGitBlame(GtkSource.GutterRendererText):
    __gtype_name__ = "GutterRendererGitBlame"

    def __init__(self):
        super().__init__()
        self.set_alignment_mode(GtkSource.GutterRendererAlignmentMode.FIRST)
        self.props.xpad = 6
        self.props.ypad = 0
        self.props.xalign = 0.0
        self.props.yalign = 0.5
        self.blame_data = []

        # Connect to notify::view style handling
        self.connect("notify::view", self.on_view_changed)

    def on_view_changed(self, *args) -> None:
        view = self.get_view()
        if view:
            view.connect("style-updated", self.on_view_style_updated)
            self.on_view_style_updated(view)

    def on_view_style_updated(self, view) -> None:
        self.recalculate_size()

    def set_blame_data(self, blame_data):
        self.blame_data = blame_data or []
        self.recalculate_size()
        view = self.get_view()
        if view:
            view.queue_draw()

    def recalculate_size(self) -> None:
        view = self.get_view()
        if not view:
            return

        max_text = "12345678 (Unknown 2026-06-15)"
        if self.blame_data:
            for info in self.blame_data:
                text = f"{info['sha']} ({info['author']} {info['date']})"
                if len(text) > len(max_text):
                    max_text = text

        layout = view.create_pango_layout()
        layout.set_text(max_text)
        w, h = layout.get_size()
        self.set_size(w / Pango.SCALE + 12)

    def do_query_data(self, start, end, state):
        line = start.get_line()
        if not self.blame_data or line >= len(self.blame_data):
            self.set_text("", -1)
            return

        info = self.blame_data[line]
        # Clean look: do not repeat details for consecutive lines from the same commit
        if line > 0 and line - 1 < len(self.blame_data) and self.blame_data[line - 1]["sha"] == info["sha"]:
            self.set_markup("<span foreground='#888888'>│</span>", -1)
            return

        # Render author and date in slightly smaller/dimmer font
        markup = f"<b>{info['sha']}</b> <span foreground='#888888' size='small'>{info['author']} {info['date']}</span>"
        self.set_markup(markup, -1)
