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

"""Unit tests for meld.archivediff."""

import os
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from gi.repository import Gio

from meld.archivediff import (
    _has_archive_extension,
    cleanup_extracted_dir,
    extract_archive,
    file_is_archive,
    files_are_archives,
)


def _gfile(path):
    return Gio.File.new_for_path(str(path))


@pytest.mark.parametrize(
    'name, expected',
    [
        ('foo.zip', True),
        ('FOO.ZIP', True),
        ('foo.tar', True),
        ('foo.tar.gz', True),
        ('foo.tgz', True),
        ('foo.tar.bz2', True),
        ('foo.tbz', True),
        ('foo.tbz2', True),
        ('foo.tar.xz', True),
        ('foo.txz', True),
        ('foo.gz', False),
        ('foo.bz2', False),
        ('foo.7z', False),
        ('foo.txt', False),
        ('archive', False),
    ],
)
def test_has_archive_extension(name, expected):
    assert _has_archive_extension(name) is expected


@pytest.fixture
def sample_zip(tmp_path):
    p = tmp_path / 'sample.zip'
    with zipfile.ZipFile(p, 'w') as zf:
        zf.writestr('a.txt', 'hello\n')
        zf.writestr('sub/b.txt', 'world\n')
    return p


@pytest.fixture
def sample_tar_gz(tmp_path):
    p = tmp_path / 'sample.tar.gz'
    with tarfile.open(p, 'w:gz') as tf:
        for name, data in (('a.txt', b'hello\n'),
                           ('sub/b.txt', b'world\n')):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, BytesIO(data))
    return p


@pytest.fixture
def plain_text_file(tmp_path):
    p = tmp_path / 'note.txt'
    p.write_text('not an archive')
    return p


def test_file_is_archive_zip(sample_zip):
    assert file_is_archive(_gfile(sample_zip)) is True


def test_file_is_archive_tar_gz(sample_tar_gz):
    assert file_is_archive(_gfile(sample_tar_gz)) is True


def test_file_is_archive_plain_text(plain_text_file):
    assert file_is_archive(_gfile(plain_text_file)) is False


def test_file_is_archive_missing(tmp_path):
    assert file_is_archive(_gfile(tmp_path / 'nope.zip')) is False


def test_file_is_archive_none():
    assert file_is_archive(None) is False


def test_file_is_archive_extension_lies(tmp_path):
    # Filename advertises an archive but the bytes do not back it up.
    p = tmp_path / 'liar.zip'
    p.write_text('not really a zip')
    assert file_is_archive(_gfile(p)) is False


def test_files_are_archives_homogeneous(sample_zip):
    g = _gfile(sample_zip)
    assert files_are_archives([g, g]) is True


def test_files_are_archives_heterogeneous(sample_zip, sample_tar_gz):
    assert files_are_archives(
        [_gfile(sample_zip), _gfile(sample_tar_gz)]) is True


def test_files_are_archives_mixed(sample_zip, plain_text_file):
    assert files_are_archives(
        [_gfile(sample_zip), _gfile(plain_text_file)]) is False


def test_files_are_archives_empty():
    assert files_are_archives([]) is False


def test_extract_zip(sample_zip):
    cleanup_root, content_dir = extract_archive(_gfile(sample_zip))
    try:
        # The extracted directory's basename matches the archive's, so
        # DirDiff renders the archive name as the comparison root.
        assert os.path.basename(content_dir) == 'sample.zip'
        assert os.path.dirname(content_dir) == cleanup_root
        assert (Path(content_dir) / 'a.txt').read_text() == 'hello\n'
        assert (Path(content_dir) / 'sub' / 'b.txt').read_text() == 'world\n'
    finally:
        cleanup_extracted_dir(cleanup_root)
    assert not os.path.exists(cleanup_root)


def test_extract_tar_gz(sample_tar_gz):
    cleanup_root, content_dir = extract_archive(_gfile(sample_tar_gz))
    try:
        assert os.path.basename(content_dir) == 'sample.tar.gz'
        assert (Path(content_dir) / 'a.txt').read_text() == 'hello\n'
        assert (Path(content_dir) / 'sub' / 'b.txt').read_text() == 'world\n'
    finally:
        cleanup_extracted_dir(cleanup_root)


def test_extract_archive_rejects_non_local():
    # A pure-URI Gio.File has no local path; refuse extraction rather
    # than silently producing an unusable temp dir.
    gfile = Gio.File.new_for_uri('http://example.invalid/foo.zip')
    with pytest.raises(ValueError):
        extract_archive(gfile)


def test_extract_tar_skips_path_traversal(tmp_path):
    archive = tmp_path / 'evil.tar'
    with tarfile.open(archive, 'w') as tf:
        for name, data in (('inside.txt', b'safe\n'),
                           ('../escape.txt', b'pwned\n')):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, BytesIO(data))

    cleanup_root, content_dir = extract_archive(_gfile(archive))
    try:
        # The legit member is extracted and the malicious one never
        # touched the filesystem outside the extraction root.
        assert (Path(content_dir) / 'inside.txt').read_text() == 'safe\n'
        assert not (tmp_path / 'escape.txt').exists()
    finally:
        cleanup_extracted_dir(cleanup_root)
