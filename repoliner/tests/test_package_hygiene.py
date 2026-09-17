# -*- coding: utf-8 -*-
#
# Repoliner - QGIS plugin repositories.
# © 2026 Inform++ LLC / ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Package hygiene. The plugins.qgis.org catalog runs the archive
# through a secret scanner, and service junk is caught as a finding: in
# July 2026 `.pytest_cache/CACHEDIR.TAG` was flagged as "Potential Hex
# High Entropy String" and blocked the release. There is no secret
# there, but dealing with the block costs more than not putting junk
# into the archive.
#     python repoliner/tests/test_package_hygiene.py
import os
import sys

PKG = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   ".."))

# Folders and files that must not be in the working tree at all.
# __pycache__ and .pyc are not included here: Python itself creates
# them on any test run, catching them with a test makes no sense. They
# are removed from the archive at packing time by explicit exclusions
# (see the release rules in AGENTS.md).
BANNED_DIRS = (".pytest_cache", ".ipynb_checkpoints", ".mypy_cache",
               ".ruff_cache", ".tox", ".idea", ".vscode")
BANNED_SUFFIX = (".orig", ".rej", ".bak", ".swp")
BANNED_NAMES = (".DS_Store", "Thumbs.db")


def _walk():
    for root, dirs, files in os.walk(PKG):
        rel = os.path.relpath(root, PKG)
        yield rel, dirs, files


def test_no_junk_directories():
    bad = []
    for rel, dirs, _files in _walk():
        for d in dirs:
            if d in BANNED_DIRS:
                bad.append(os.path.join(rel, d))
    assert not bad, "служебные папки в поставке: %s" % ", ".join(sorted(bad))


def test_no_junk_files():
    bad = []
    for rel, _dirs, files in _walk():
        for f in files:
            if f in BANNED_NAMES or f.endswith(BANNED_SUFFIX):
                bad.append(os.path.join(rel, f))
    assert not bad, "мусор в поставке: %s" % ", ".join(sorted(bad))


def test_expected_layout():
    """The backbone of the package is in place: without it the archive
    is built wrong."""
    for name in ("metadata.txt", "__init__.py", "plugin.py", "core.py",
                 "xmlparse.py", "view.py", "i18n.py", "qt_compat.py",
                 "icon.svg", "LICENSE"):
        assert os.path.exists(os.path.join(PKG, name)), name


def _run():
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    bad = 0
    for name, fn in fns:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            bad += 1
            print("FAIL %s: %s" % (name, exc))
    print("%d tests, %d failed" % (len(fns), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(_run())

