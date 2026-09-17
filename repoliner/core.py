# -*- coding: utf-8 -*-
#
# Repoliner - repositories of QGIS plugins.
# © 2026 Inform++ LLC / ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
"""Registry of QGIS plugins (plugins.xml) from ready-made zip archives.

Without QGIS and Qt: the plugin window only shows what is computed
here. Test `tests/test_core.py`.

One plugins.xml file is one repository: QGIS reads it from a single
address. The set of repositories is held by the window, in the QGIS
settings.

How QGIS reads the registry (pyplugin_installer/installer_data.py, 3.40
and 4.x):
- the plugin is identified by the name up to the first dot from
  file_name, and without it from download_url. Matching names in two
  repositories merge the records into one;
- after the download QGIS looks in the archive for a folder with this
  name and copies only it. That is why file_name is written after the
  plugin folder inside the archive, and not after the file name. The
  file itself may be named in any way: download_url leads to it, and it
  is downloaded from that address;
- download_url is taken as is and is not resolved relative to the
  address of plugins.xml. That is why the address is written in full,
  for a file on disk this is file:///;
- QGIS appends ?qgis=X.Y to the registry address, for file:/// this
  does not get in the way (checked on QGIS 4.0.3);
- a plugin outside the qgis_minimum_version - qgis_maximum_version
  range is not shown in the list at all. An empty maximum is treated by
  QGIS as "the leading digit of the minimum".99.

Correspondence of the metadata.txt and plugins.xml fields (FIELD_MAP
below):

    metadata.txt          plugins.xml
    name                  name attribute
    version               version attribute and version element
    description           description
    about                 about
    qgisMinimumVersion    qgis_minimum_version
    qgisMaximumVersion    qgis_maximum_version
    homepage              homepage
    tracker               tracker
    repository            repository
    tags                  tags
    author                author_name
    experimental          experimental (True/False)
    deprecated            deprecated (True/False)
    plugin_dependencies   plugin_dependencies
    server                server (True/False)
    -                     file_name = plugin folder in archive + .zip
    -                     download_url = file:/// to the archive
    -                     update_date = modification time of the archive

Not carried over: email (the catalog does not publish it), changelog
(in metadata it is long, QGIS shows it from the installed plugin), icon
(for file:/// QGIS does not resolve the relative path of the icon),
category, hasProcessingProvider.

The xml modules of the standard library are not used: the scanner of
the plugins.qgis.org catalog blocks them. Parsing is done by our own
parser (xmlparse.py), it refuses to read files with entity
declarations.
"""

import configparser
import io
import os
import re
import time
import zipfile

from urllib.parse import quote, unquote, urlsplit

from .xmlparse import XmlError, parse as _parse_xml

GENERATOR = "Repoliner"
MAX_XML_BYTES = 5 * 1024 * 1024
MAX_METADATA_BYTES = 1024 * 1024

# (metadata.txt field, plugins.xml element, boolean flag)
FIELD_MAP = (
    ("description", "description", False),
    ("about", "about", False),
    ("qgisMinimumVersion", "qgis_minimum_version", False),
    ("qgisMaximumVersion", "qgis_maximum_version", False),
    ("homepage", "homepage", False),
    ("tracker", "tracker", False),
    ("repository", "repository", False),
    ("tags", "tags", False),
    ("author", "author_name", False),
    ("experimental", "experimental", True),
    ("deprecated", "deprecated", True),
    ("plugin_dependencies", "plugin_dependencies", False),
    ("server", "server", True),
)

# order of the elements when writing, as in the catalog
ELEMENT_ORDER = ("description", "about", "version", "qgis_minimum_version",
                 "qgis_maximum_version", "homepage", "tracker", "repository",
                 "tags", "author_name", "file_name", "download_url",
                 "update_date", "experimental", "deprecated",
                 "plugin_dependencies", "server")

# states of the record relative to the archive on disk
ST_OK = "ok"
ST_MISSING = "missing"          # no archive at the address
ST_CHANGED = "changed"          # archive does not match the registry record
ST_REMOTE = "remote"            # address is not file:///, archive unchecked


class RepoError(Exception):
    """An archive or a registry cannot be read. The text is meant to be
    shown to the user.

    The message is kept as a template plus its values, so the same
    message can be rendered in another language, see i18n.error_text.
    """

    def __init__(self, template, *values):
        self.template = template
        self.values = values
        Exception.__init__(self, template % values if values else template)


def _flag(value):
    return "True" if str(value).strip().lower() in ("true", "yes", "1") \
        else "False"


def plugin_key(file_name):
    """Plugin name as QGIS sees it: archive name up to the first dot."""
    return os.path.basename(file_name).partition(".")[0]


def path_to_url(path):
    """Full file:/// address for a file on disk, with spaces encoded.

    The network folder path \\\\server\\share\\x.zip gives
    file://server/share/x.zip, the path with a drive letter C:\\x.zip
    gives file:///C:/x.zip.
    """
    p = str(path).replace("\\", "/")
    if p.startswith("//"):
        # Qt treats file://localhost/ as a local disk and looks for
        # /C$/…, so the name of this same machine is replaced by the
        # address 127.0.0.1
        if p[2:].lower().startswith("localhost/"):
            p = "//127.0.0.1/" + p[len("//localhost/"):]
        return "file:" + quote(p, safe="/:")
    if re.match(r"^[A-Za-z]:/", p):
        return "file:///" + quote(p, safe="/:")
    p = os.path.abspath(p).replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p                  # C:/... -> /C:/...
    return "file://" + quote(p, safe="/:")


def check_base_url(url):
    """Server address for the registry: empty or http(s)://…/ with a
    trailing slash."""
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://[^/\s]+", url, re.I):
        raise RepoError("The server address must start with http:// or "
                        "https://, got %s", url)
    if any(c.isspace() for c in url):
        raise RepoError("The server address contains a space: %s", url)
    return url.rstrip("/") + "/"


def url_to_path(url):
    """Path on disk from file:///, otherwise None."""
    parts = urlsplit(url or "")
    if parts.scheme.lower() != "file":
        return None
    p = unquote(parts.path)
    if re.match(r"^/[A-Za-z]:", p):
        p = p[1:]                    # /C:/... -> C:/...
    if parts.netloc and parts.netloc.lower() != "localhost":
        p = "//" + parts.netloc + p  # file://server/share/...
    return os.path.normpath(p)


# --- archive ------------------------------------------------------------

def read_archive(path):
    """Information from the metadata.txt of a plugin archive.

    Returns a dictionary: key and folder (the plugin folder in the
    archive), file_name (the name for the registry, after the folder),
    archive (the file name), fields (the metadata.txt fields as is).
    Refuses if the archive is not a zip, if it holds no metadata.txt in
    the root plugin folder or if there is no name and version.
    """
    if not os.path.isfile(path):
        raise RepoError("Archive not found: %s", path)
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipfile, OSError) as e:
        raise RepoError("The file cannot be read as a zip: %s (%s)", path, e)
    with zf:
        names = [n for n in zf.namelist() if n.count("/") == 1
                 and n.split("/")[1].lower() == "metadata.txt"]
        if not names:
            raise RepoError("The archive holds no metadata.txt in a plugin "
                            "folder: %s", path)
        if len(names) > 1:
            raise RepoError("The archive holds several folders with "
                            "metadata.txt: %s", path)
        info = zf.getinfo(names[0])
        if info.file_size > MAX_METADATA_BYTES:
            raise RepoError("metadata.txt is larger than 1 MB: %s", path)
        raw = zf.read(names[0])
    text = raw.decode("utf-8-sig", errors="replace")
    parser = configparser.RawConfigParser(strict=False)
    try:
        parser.read_file(io.StringIO(text))
    except configparser.Error as e:
        raise RepoError("metadata.txt was not parsed: %s (%s)", path, e)
    if not parser.has_section("general"):
        raise RepoError("metadata.txt has no [general] section: %s", path)
    fields = dict((k, v.strip()) for k, v in parser.items("general"))
    # RawConfigParser lowercases the keys
    lower = dict((k.lower(), v) for k, v in fields.items())
    for need in ("name", "version"):
        if not lower.get(need):
            raise RepoError("metadata.txt has no %s field: %s", need, path)
    folder = names[0].split("/")[0]
    return {"key": folder,
            "folder": folder,
            "file_name": folder + ".zip",
            "archive": os.path.basename(path),
            "fields": lower}


def entry_from_archive(path, url=None):
    """Registry record from an archive. url is by default file:/// to
    the archive."""
    arc = read_archive(path)
    f = arc["fields"]
    e = PluginEntry(f["name"], f["version"])
    for meta, elem, is_flag in FIELD_MAP:
        v = f.get(meta.lower(), "")
        if is_flag:
            e.elements[elem] = _flag(v)
        elif v:
            e.elements[elem] = " ".join(v.split()) \
                if elem != "about" else v
    if not e.elements.get("qgis_minimum_version"):
        raise RepoError("metadata.txt has no qgisMinimumVersion: %s", path)
    e.elements["file_name"] = arc["file_name"]
    e.elements["download_url"] = url or path_to_url(path)
    e.elements["update_date"] = time.strftime(
        "%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(path)))
    e.folder = arc["folder"]
    return e


# --- registry record ----------------------------------------------------

class PluginEntry(object):
    """One pyqgis_plugin: name, version and elements as strings."""

    def __init__(self, name, version, elements=None):
        self.name = name
        self.version = version
        self.elements = dict(elements or {})
        self.elements["version"] = version
        self.folder = None           # plugin folder in archive, if read

    @property
    def file_name(self):
        return self.elements.get("file_name") or os.path.basename(
            (self.download_url or "").split("?")[0])

    @property
    def key(self):
        return plugin_key(self.file_name)

    @property
    def download_url(self):
        return self.elements.get("download_url", "")

    @property
    def archive_path(self):
        return url_to_path(self.download_url)

    @property
    def qgis_range(self):
        lo = self.elements.get("qgis_minimum_version", "") or "2"
        hi = self.elements.get("qgis_maximum_version", "") or (lo[0] + ".99")
        return lo, hi

    def is_compatible(self, qgis_version):
        """Whether QGIS of this version shows the plugin in the list
        (like isCompatible)."""
        cur = _vtuple(qgis_version)[:2]
        lo, hi = self.qgis_range
        return _vtuple(lo)[:2] <= cur <= _vtuple(hi)[:2]

    def status(self, path=None):
        """State relative to the archive: ST_OK, ST_MISSING, ST_CHANGED,
        ST_REMOTE. path - the archive on disk, if the address is not
        file:///."""
        p = path or self.archive_path
        if p is None:
            return ST_REMOTE
        if not os.path.isfile(p):
            return ST_MISSING
        try:
            arc = read_archive(p)
        except RepoError:
            return ST_CHANGED
        if arc["fields"].get("version") != self.version:
            return ST_CHANGED
        if arc["key"] != self.key:
            return ST_CHANGED       # QGIS will not find the plugin folder
        return ST_OK


def version_key(v):
    """Version comparison key: "1.10.0" is newer than "1.9.2"."""
    return _vtuple(v)


def _vtuple(v):
    out = []
    for part in str(v).split("."):
        m = re.match(r"\d+", part.strip())
        out.append(int(m.group(0)) if m else 0)
    while len(out) < 3:
        out.append(0)
    return tuple(out)


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


class Repository(object):
    """Registry of one repository: path to plugins.xml and the plugin
    records."""

    def __init__(self, path=None, base_url=""):
        self.path = path
        self.base_url = base_url     # http(s)://…/, empty - file:/// urls
        self.entries = []
        self.dirty = False

    # addresses
    @property
    def folder(self):
        return os.path.dirname(os.path.abspath(self.path)) if self.path \
            else ""

    def url_for(self, archive):
        """Address of the archive in the registry: file:/// or the
        server address + the path from the registry folder."""
        if not self.base_url:
            return path_to_url(archive)
        if not self.path:
            raise RepoError("The server address is set and the registry "
                            "file is not")
        rel = os.path.relpath(os.path.abspath(archive), self.folder)
        rel = rel.replace("\\", "/")
        if rel.startswith("../") or rel == ".." or os.path.isabs(rel):
            raise RepoError("The archive lies outside the registry folder "
                            "and is not reachable by the server address: %s",
                            archive)
        return self.base_url + quote(rel, safe="/")

    def local_path(self, entry):
        """Archive on disk for a record: from file:/// or from the
        server address."""
        p = entry.archive_path
        if p is not None:
            return p
        url = entry.download_url
        if self.base_url and self.path and url.startswith(self.base_url):
            rel = unquote(url[len(self.base_url):].split("?")[0])
            return os.path.normpath(os.path.join(self.folder, rel))
        return None

    def status(self, entry):
        return entry.status(self.local_path(entry))

    def set_base_url(self, url):
        """Change the server address and rewrite the addresses of all
        archives.

        Refuses without changes if at least one archive is not
        reachable by the new address."""
        url = check_base_url(url)
        old = self.base_url
        pairs = []
        for e in self.entries:
            p = self.local_path(e)
            if p is None:
                raise RepoError("The address of plugin “%s” is neither "
                                "file:/// nor the server address of the "
                                "registry: %s", e.name, e.download_url)
            pairs.append((e, p))
        self.base_url = url
        try:
            new = [(e, self.url_for(p)) for e, p in pairs]
        except RepoError:
            self.base_url = old
            raise
        for e, u in new:
            e.elements["download_url"] = u
        if url != old:
            self.dirty = True

    # search and editing
    def find(self, key):
        for e in self.entries:
            if e.key == key:
                return e
        return None

    def put(self, entry):
        """Add a record. A record with the same plugin name is
        replaced.

        Returns the previous record or None.
        """
        old = self.find(entry.key)
        if old is not None:
            self.entries[self.entries.index(old)] = entry
        else:
            self.entries.append(entry)
        self.dirty = True
        return old

    def remove(self, key):
        e = self.find(key)
        if e is not None:
            self.entries.remove(e)
            self.dirty = True
        return e

    def add_archives(self, paths):
        """Add archives. Returns (added, replaced, errors).

        errors - a list of RepoError, so that the caller shows them in
        its own language."""
        added, replaced, errors = [], [], []
        for p in paths:
            try:
                e = entry_from_archive(p, url=self.url_for(p))
            except RepoError as exc:
                errors.append(exc)
                continue
            old = self.put(e)
            (replaced if old is not None else added).append(e)
        return added, replaced, errors

    def refresh(self):
        """Reread all file:/// archives. Returns (updated, errors)."""
        updated, errors = [], []
        for e in list(self.entries):
            p = self.local_path(e)
            if p is None:
                continue
            try:
                fresh = entry_from_archive(p, url=e.download_url)
            except RepoError as exc:
                errors.append(exc)
                continue
            if fresh.elements != e.elements or fresh.name != e.name:
                # the plugin name could have changed (registry 0.1.0
                # took it from the file name), so the record itself is
                # replaced, and a match by the new name is removed
                self.entries[self.entries.index(e)] = fresh
                for other in [x for x in self.entries
                              if x is not fresh and x.key == fresh.key]:
                    self.entries.remove(other)
                self.dirty = True
                updated.append(fresh)
        return updated, errors

    # writing
    def dumps(self):
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<plugins generator="%s"%s>' % (
                     GENERATOR, ' base_url="%s"' % _esc(self.base_url)
                     if self.base_url else "")]
        for e in sorted(self.entries, key=lambda x: x.name.lower()):
            lines.append('  <pyqgis_plugin name="%s" version="%s">'
                         % (_esc(e.name), _esc(e.version)))
            known = [k for k in ELEMENT_ORDER if k in e.elements]
            extra = sorted(k for k in e.elements if k not in ELEMENT_ORDER)
            for k in known + extra:
                lines.append("    <%s>%s</%s>" % (k, _esc(e.elements[k]), k))
            lines.append("  </pyqgis_plugin>")
        lines.append("</plugins>")
        return "\n".join(lines) + "\n"

    def save(self, path=None):
        path = path or self.path
        if not path:
            raise RepoError("No registry file is set")
        tmp = path + ".tmp"
        with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.dumps())
        os.replace(tmp, path)
        self.path = path
        self.dirty = False
        return path

    @property
    def url(self):
        """Registry address for "Plugins - Settings - Add"."""
        if not self.path:
            return ""
        if self.base_url:
            return self.base_url + quote(os.path.basename(self.path))
        return path_to_url(self.path)


def loads(text, own_only=True):
    """Registry from the text of plugins.xml.

    own_only: refuses if the root has no generator="Repoliner" mark.
    """
    if len(text) > MAX_XML_BYTES:
        raise RepoError("The registry file is larger than 5 MB")
    try:
        root = _parse_xml(text)
    except XmlError as e:
        raise RepoError("The registry file was not parsed: %s", e)
    if root.tag != "plugins":
        raise RepoError("The root element is “%s” and plugins was expected",
                        root.tag)
    if own_only and root.get("generator") != GENERATOR:
        raise RepoError("The registry was not created by Repoliner. Only "
                        "registries marked generator=\"%s\" are opened",
                        GENERATOR)
    try:
        base = check_base_url(root.get("base_url", ""))
    except RepoError as e:
        raise RepoError("The registry file is broken: %s", e)
    repo = Repository(base_url=base)
    for node in root:
        if node.tag != "pyqgis_plugin":
            continue
        elements = {}
        for ch in node:
            elements[ch.tag] = ch.text.strip()
        name = node.get("name", "")
        version = node.get("version", "") or elements.get("version", "")
        e = PluginEntry(name, version, elements)
        if not e.file_name:
            raise RepoError("Plugin “%s” has neither file_name nor "
                            "download_url", name)
        repo.put(e)
    repo.dirty = False
    return repo


def load(path, own_only=True):
    if os.path.getsize(path) > MAX_XML_BYTES:
        raise RepoError("The registry file is larger than 5 MB: %s", path)
    try:
        with io.open(path, encoding="utf-8-sig") as f:
            text = f.read()
    except (UnicodeDecodeError, ValueError):
        # a zip or another binary file picked in the file dialog
        raise RepoError("The registry file is not text: %s", path)
    repo = loads(text, own_only=own_only)
    repo.path = path
    return repo


def new(path):
    """Empty registry, written to disk right away."""
    repo = Repository(path)
    repo.save()
    return repo
