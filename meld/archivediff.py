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

"""Transparent archive comparison support.

When all sides of a comparison are archive files, callers can extract
each side to a temporary directory and redirect to a folder comparison
instead of doing a binary file diff. Detection and extraction are
intentionally restricted to the Python standard library (``zipfile`` and
``tarfile``) so that no new runtime dependency is introduced.
"""

import logging
import os
import shutil
import tarfile
import tempfile
import zipfile
from typing import Optional, Sequence, Tuple

from gi.repository import Gio

log = logging.getLogger(__name__)


# Compound extensions are listed before single ones so that ``.tar.gz``
# matches before ``.gz`` would.
_ARCHIVE_EXTENSIONS = (
    '.tar.gz', '.tgz',
    '.tar.bz2', '.tbz', '.tbz2',
    '.tar.xz', '.txz',
    '.tar',
    '.zip',
)


def _local_path(gfile: Optional[Gio.File]) -> Optional[str]:
    if gfile is None:
        return None
    return gfile.get_path()


def _has_archive_extension(path: str) -> bool:
    lowered = path.lower()
    return any(lowered.endswith(ext) for ext in _ARCHIVE_EXTENSIONS)


def file_is_archive(gfile: Optional[Gio.File]) -> bool:
    """Return True if *gfile* refers to a supported archive file.

    The check combines a filename-extension test with a magic-byte
    probe via :func:`zipfile.is_zipfile` / :func:`tarfile.is_tarfile`.
    Non-local URIs and unreadable paths are treated as non-archives.
    """
    path = _local_path(gfile)
    if not path or not os.path.isfile(path):
        return False
    if not _has_archive_extension(path):
        return False
    try:
        return zipfile.is_zipfile(path) or tarfile.is_tarfile(path)
    except (OSError, tarfile.TarError):
        return False


def files_are_archives(gfiles: Sequence[Optional[Gio.File]]) -> bool:
    """Return True iff every entry in *gfiles* is an archive file."""
    if not gfiles:
        return False
    return all(file_is_archive(f) for f in gfiles)


def _safe_extract_tar(tar: tarfile.TarFile, dest: str) -> None:
    """Extract *tar* into *dest*, skipping entries that escape *dest*.

    On Python 3.12+ the built-in :func:`tarfile.data_filter` is used to
    vet each member (per PEP 706); members it rejects are skipped with
    a warning rather than aborting the whole extraction. On older
    interpreters an equivalent path-traversal check is applied manually
    and device nodes are dropped.
    """
    data_filter = getattr(tarfile, 'data_filter', None)
    if data_filter is not None:
        def safe_filter(member, path):
            try:
                return data_filter(member, path)
            except tarfile.FilterError as err:
                log.warning(
                    "Refusing to extract %r: %s", member.name, err)
                return None
        tar.extractall(dest, filter=safe_filter)
        return

    # Pre-3.12 fallback: vet each member manually.
    dest_real = os.path.realpath(dest)
    safe_members = []
    for member in tar.getmembers():
        target = os.path.realpath(os.path.join(dest, member.name))
        if target != dest_real and not target.startswith(
                dest_real + os.sep):
            log.warning(
                "Refusing to extract %r: escapes destination", member.name)
            continue
        if member.isdev():
            continue
        safe_members.append(member)
    tar.extractall(dest, members=safe_members)


def extract_archive(gfile: Gio.File) -> Tuple[str, str]:
    """Extract *gfile* into a fresh temporary directory.

    Returns a ``(cleanup_root, content_dir)`` pair.

    * ``cleanup_root`` is the temporary directory that owns everything
      we created; it must be passed to :func:`cleanup_extracted_dir`
      when the comparison closes (typically via the tab's ``close``
      signal).
    * ``content_dir`` is the directory whose contents are the extracted
      archive. Its basename matches the archive's basename, so a
      :class:`~meld.dirdiff.DirDiff` rooted there displays the original
      archive name rather than the random temp prefix.
    """
    path = _local_path(gfile)
    if not path:
        raise ValueError("Cannot extract a non-local archive")

    cleanup_root = tempfile.mkdtemp(prefix='meld-archive-')
    content_dir = os.path.join(cleanup_root, os.path.basename(path))
    try:
        os.mkdir(content_dir)
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as zf:
                zf.extractall(content_dir)
        elif tarfile.is_tarfile(path):
            with tarfile.open(path) as tf:
                _safe_extract_tar(tf, content_dir)
        else:
            raise ValueError(f"Unsupported archive: {path!r}")
    except Exception:
        cleanup_extracted_dir(cleanup_root)
        raise
    return cleanup_root, content_dir


def cleanup_extracted_dir(path: str) -> None:
    """Remove a directory previously created by :func:`extract_archive`."""
    if not path:
        return
    try:
        shutil.rmtree(path)
    except OSError:
        log.exception("Failed to clean up extracted archive at %r", path)
