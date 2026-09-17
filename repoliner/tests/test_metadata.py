# -*- coding: utf-8 -*-
#
# Repoliner - QGIS plugin repositories.
# © 2026 Inform++ LLC / ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
#
"""metadata.txt is read as strictly as the catalog reads it.

The plugins.qgis.org catalog parses the file with configparser with
interpolation, so a single percent sign breaks the upload.
"""
import configparser
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, os.path.dirname(PKG))

from repoliner import core  # noqa: E402

REQUIRED = ("name", "qgisMinimumVersion", "description", "about",
            "version", "author", "email", "repository")


def test_metadata_reads_with_strict_parser():
    cp = configparser.ConfigParser(
        interpolation=configparser.BasicInterpolation())
    cp.read(os.path.join(PKG, "metadata.txt"), encoding="utf-8")
    for key in REQUIRED:
        assert cp.get("general", key).strip(), key
    for key in cp.options("general"):
        cp.get("general", key)          # interpolation on every field


def test_version_is_first_in_changelog():
    cp = configparser.RawConfigParser()
    cp.read(os.path.join(PKG, "metadata.txt"), encoding="utf-8")
    version = cp.get("general", "version").strip()
    first = cp.get("general", "changelog").strip().splitlines()[0].strip()
    assert first == version, (first, version)


def test_own_archive_gives_valid_entry(tmp_path=None):
    """The plugin's own archive turns into a registry entry."""
    import tempfile
    import zipfile
    d = tempfile.mkdtemp()
    path = os.path.join(d, "repoliner.zip")
    with zipfile.ZipFile(path, "w") as z:
        z.write(os.path.join(PKG, "metadata.txt"), "repoliner/metadata.txt")
    e = core.entry_from_archive(path)
    assert e.key == "repoliner"
    assert e.qgis_range == ("3.16", "4.99")
    assert e.is_compatible("3.40.0") and e.is_compatible("4.0.3")
