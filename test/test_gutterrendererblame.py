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

from meld.gutterrendererblame import parse_git_blame


def test_parse_git_blame_empty():
    assert parse_git_blame("") == []


def test_parse_git_blame_standard():
    porcelain_output = (
        "3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d 1 1 2\n"
        "author Kai Willadsen\n"
        "author-mail <kai.willadsen@gmail.com>\n"
        "author-time 1448924400\n"
        "author-tz +1000\n"
        "summary Add line annotations\n"
        "filename meldwindow.py\n"
        "\timport logging\n"
        "3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d 2 2\n"
        "\timport os\n"
        "0000000000000000000000000000000000000000 3 3 1\n"
        "author Not Committed Yet\n"
        "author-mail <not.committed.yet>\n"
        "author-time 1448924410\n"
        "author-tz +1000\n"
        "summary Local edit\n"
        "filename meldwindow.py\n"
        "\timport sys\n"
    )
    result = parse_git_blame(porcelain_output)
    assert len(result) == 3

    # First line
    assert result[0]["sha"] == "3d3d3d3d"
    assert result[0]["author"] == "Kai Willadsen"
    assert result[0]["date"] == "2015-12-01"

    # Second line (same commit)
    assert result[1]["sha"] == "3d3d3d3d"

    # Third line (uncommitted)
    assert result[2]["sha"] == "Uncommitted"
    assert result[2]["author"] == "You"
    assert result[2]["date"] == "Today"
