# -*- coding: utf-8 -*-
#
# Repoliner - репозитории модулей QGIS.
# © 2026 ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
"""Реестр модулей QGIS (plugins.xml) из готовых zip-архивов.

Без QGIS и Qt: окно модуля только показывает то, что здесь посчитано.
Тест `tests/test_core.py`.

Один файл plugins.xml это один репозиторий: QGIS читает его по одному
адресу. Набор репозиториев держит окно, в настройках QGIS.

Как QGIS читает реестр (pyplugin_installer/installer_data.py, 3.40 и 4.x):
- модуль определяется именем до первой точки из file_name, а без него из
  download_url. Совпадение имён в двух репозиториях сливает записи в
  одну;
- после скачивания QGIS ищет в архиве папку с этим именем и копирует
  только её. Поэтому file_name пишется по папке модуля внутри архива, а
  не по имени файла. Сам файл может называться как угодно:
  download_url ведёт на него, и скачивается он по этому адресу;
- download_url берётся как есть и не разрешается относительно адреса
  plugins.xml. Поэтому адрес пишется полный, для файла на диске это
  file:///;
- к адресу реестра QGIS дописывает ?qgis=X.Y, для file:/// это не мешает
  (проверено на QGIS 4.0.3);
- модуль вне диапазона qgis_minimum_version - qgis_maximum_version в
  списке не показывается вовсе. Пустой максимум QGIS считает как
  «старшая цифра минимума».99.

Соответствие полей metadata.txt и plugins.xml (FIELD_MAP ниже):

    metadata.txt          plugins.xml
    name                  атрибут name
    version               атрибут version и элемент version
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
    -                     file_name = папка модуля в архиве + .zip
    -                     download_url = file:/// на архив
    -                     update_date = время изменения архива

Не переносятся: email (каталог его не публикует), changelog (в metadata
он длинный, QGIS показывает его из установленного модуля), icon (для
file:/// QGIS относительный путь значка не разрешает), category,
hasProcessingProvider.

Модули xml стандартной библиотеки не берутся: сканер каталога
plugins.qgis.org их блокирует. Разбор идёт своим разборщиком
(xmlparse.py), он отказывается читать файлы с объявлением сущностей.
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

# (поле metadata.txt, элемент plugins.xml, логический флаг)
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

# порядок элементов при записи, как в каталоге
ELEMENT_ORDER = ("description", "about", "version", "qgis_minimum_version",
                 "qgis_maximum_version", "homepage", "tracker", "repository",
                 "tags", "author_name", "file_name", "download_url",
                 "update_date", "experimental", "deprecated",
                 "plugin_dependencies", "server")

# состояния записи относительно архива на диске
ST_OK = "ok"
ST_MISSING = "missing"          # архива по адресу нет
ST_CHANGED = "changed"          # архив не совпадает с записью реестра
ST_REMOTE = "remote"            # адрес не file:///, архив не проверяется


class RepoError(Exception):
    """Архив или реестр не читается. Текст годится для показа."""


def _flag(value):
    return "True" if str(value).strip().lower() in ("true", "yes", "1") \
        else "False"


def plugin_key(file_name):
    """Имя модуля так, как его видит QGIS: имя архива до первой точки."""
    return os.path.basename(file_name).partition(".")[0]


def path_to_url(path):
    """Полный адрес file:/// для файла на диске, с кодированием пробелов.

    Путь сетевой папки \\\\server\\share\\x.zip даёт file://server/share/x.zip,
    путь с буквой диска C:\\x.zip даёт file:///C:/x.zip.
    """
    p = str(path).replace("\\", "/")
    if p.startswith("//"):
        # Qt считает file://localhost/ локальным диском и ищет /C$/…,
        # поэтому имя этой же машины заменяется адресом 127.0.0.1
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
    """Адрес сервера для реестра: пусто или http(s)://…/ с косой в конце."""
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://[^/\s]+", url, re.I):
        raise RepoError("Адрес сервера должен начинаться с http:// или "
                        "https://: %s" % url)
    if any(c.isspace() for c in url):
        raise RepoError("В адресе сервера есть пробел: %s" % url)
    return url.rstrip("/") + "/"


def url_to_path(url):
    """Путь на диске из file:///, иначе None."""
    parts = urlsplit(url or "")
    if parts.scheme.lower() != "file":
        return None
    p = unquote(parts.path)
    if re.match(r"^/[A-Za-z]:", p):
        p = p[1:]                    # /C:/... -> C:/...
    if parts.netloc and parts.netloc.lower() != "localhost":
        p = "//" + parts.netloc + p  # file://server/share/...
    return os.path.normpath(p)


# --- архив --------------------------------------------------------------

def read_archive(path):
    """Сведения из metadata.txt архива модуля.

    Возвращает словарь: key и folder (папка модуля в архиве), file_name
    (имя для реестра, по папке), archive (имя файла), fields (поля
    metadata.txt как есть). Отказ, если архив не zip, в нём нет metadata.txt в
    корневой папке модуля или нет name и version.
    """
    if not os.path.isfile(path):
        raise RepoError("Архив не найден: %s" % path)
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipfile, OSError) as e:
        raise RepoError("Файл не читается как zip: %s (%s)" % (path, e))
    with zf:
        names = [n for n in zf.namelist() if n.count("/") == 1
                 and n.split("/")[1].lower() == "metadata.txt"]
        if not names:
            raise RepoError(
                "В архиве нет metadata.txt в папке модуля: %s" % path)
        if len(names) > 1:
            raise RepoError(
                "В архиве несколько папок с metadata.txt: %s" % path)
        info = zf.getinfo(names[0])
        if info.file_size > MAX_METADATA_BYTES:
            raise RepoError("metadata.txt больше 1 МБ: %s" % path)
        raw = zf.read(names[0])
    text = raw.decode("utf-8-sig", errors="replace")
    parser = configparser.RawConfigParser(strict=False)
    try:
        parser.read_file(io.StringIO(text))
    except configparser.Error as e:
        raise RepoError("metadata.txt не разобран: %s (%s)" % (path, e))
    if not parser.has_section("general"):
        raise RepoError("В metadata.txt нет раздела [general]: %s" % path)
    fields = dict((k, v.strip()) for k, v in parser.items("general"))
    # RawConfigParser приводит ключи к нижнему регистру
    lower = dict((k.lower(), v) for k, v in fields.items())
    for need in ("name", "version"):
        if not lower.get(need):
            raise RepoError("В metadata.txt нет поля %s: %s" % (need, path))
    folder = names[0].split("/")[0]
    return {"key": folder,
            "folder": folder,
            "file_name": folder + ".zip",
            "archive": os.path.basename(path),
            "fields": lower}


def entry_from_archive(path, url=None):
    """Запись реестра из архива. url по умолчанию file:/// на архив."""
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
        raise RepoError("В metadata.txt нет qgisMinimumVersion: %s" % path)
    e.elements["file_name"] = arc["file_name"]
    e.elements["download_url"] = url or path_to_url(path)
    e.elements["update_date"] = time.strftime(
        "%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(path)))
    e.folder = arc["folder"]
    return e


# --- запись реестра -----------------------------------------------------

class PluginEntry(object):
    """Один pyqgis_plugin: имя, версия и элементы в виде строк."""

    def __init__(self, name, version, elements=None):
        self.name = name
        self.version = version
        self.elements = dict(elements or {})
        self.elements["version"] = version
        self.folder = None           # папка модуля в архиве, если читали

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
        """Покажет ли QGIS этой версии модуль в списке (как isCompatible)."""
        cur = _vtuple(qgis_version)[:2]
        lo, hi = self.qgis_range
        return _vtuple(lo)[:2] <= cur <= _vtuple(hi)[:2]

    def status(self, path=None):
        """Состояние относительно архива: ST_OK, ST_MISSING, ST_CHANGED,
        ST_REMOTE. path - архив на диске, если адрес не file:///."""
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
            return ST_CHANGED       # QGIS не найдёт папку модуля
        return ST_OK


def version_key(v):
    """Ключ сравнения версий: «1.10.0» старше «1.9.2»."""
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
    """Реестр одного репозитория: путь к plugins.xml и записи модулей."""

    def __init__(self, path=None, base_url=""):
        self.path = path
        self.base_url = base_url     # http(s)://…/, пусто - адреса file:///
        self.entries = []
        self.dirty = False

    # адреса
    @property
    def folder(self):
        return os.path.dirname(os.path.abspath(self.path)) if self.path \
            else ""

    def url_for(self, archive):
        """Адрес архива в реестре: file:/// или адрес сервера + путь от
        папки реестра."""
        if not self.base_url:
            return path_to_url(archive)
        if not self.path:
            raise RepoError("Адрес сервера задан, а файл реестра нет")
        rel = os.path.relpath(os.path.abspath(archive), self.folder)
        rel = rel.replace("\\", "/")
        if rel.startswith("../") or rel == ".." or os.path.isabs(rel):
            raise RepoError(
                "Архив лежит вне папки реестра и по адресу сервера "
                "недоступен: %s" % archive)
        return self.base_url + quote(rel, safe="/")

    def local_path(self, entry):
        """Архив на диске для записи: из file:/// или из адреса сервера."""
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
        """Сменить адрес сервера и переписать адреса всех архивов.

        Отказ без изменений, если хоть один архив недоступен по новому
        адресу."""
        url = check_base_url(url)
        old = self.base_url
        pairs = []
        for e in self.entries:
            p = self.local_path(e)
            if p is None:
                raise RepoError("У модуля «%s» адрес не file:/// и не адрес "
                                "сервера реестра: %s" % (e.name,
                                                         e.download_url))
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

    # поиск и правка
    def find(self, key):
        for e in self.entries:
            if e.key == key:
                return e
        return None

    def put(self, entry):
        """Добавить запись. Запись с тем же именем модуля заменяется.

        Возвращает прежнюю запись или None.
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
        """Добавить архивы. Возвращает (added, replaced, errors)."""
        added, replaced, errors = [], [], []
        for p in paths:
            try:
                e = entry_from_archive(p, url=self.url_for(p))
            except RepoError as exc:
                errors.append(str(exc))
                continue
            old = self.put(e)
            (replaced if old is not None else added).append(e)
        return added, replaced, errors

    def refresh(self):
        """Перечитать все архивы file:///. Возвращает (updated, errors)."""
        updated, errors = [], []
        for e in list(self.entries):
            p = self.local_path(e)
            if p is None:
                continue
            try:
                fresh = entry_from_archive(p, url=e.download_url)
            except RepoError as exc:
                errors.append(str(exc))
                continue
            if fresh.elements != e.elements or fresh.name != e.name:
                # имя модуля могло смениться (реестр 0.1.0 брал его из
                # имени файла), поэтому заменяется сама запись, а
                # совпадение по новому имени снимается
                self.entries[self.entries.index(e)] = fresh
                for other in [x for x in self.entries
                              if x is not fresh and x.key == fresh.key]:
                    self.entries.remove(other)
                self.dirty = True
                updated.append(fresh)
        return updated, errors

    # запись
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
            raise RepoError("Не задан файл реестра")
        tmp = path + ".tmp"
        with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.dumps())
        os.replace(tmp, path)
        self.path = path
        self.dirty = False
        return path

    @property
    def url(self):
        """Адрес реестра для «Модули - Настройки - Добавить»."""
        if not self.path:
            return ""
        if self.base_url:
            return self.base_url + quote(os.path.basename(self.path))
        return path_to_url(self.path)


def loads(text, own_only=True):
    """Реестр из текста plugins.xml.

    own_only: отказ, если на корне нет метки generator="Repoliner".
    """
    if len(text) > MAX_XML_BYTES:
        raise RepoError("Файл реестра больше 5 МБ")
    try:
        root = _parse_xml(text)
    except XmlError as e:
        raise RepoError("Файл реестра не разобран: %s" % e)
    if root.tag != "plugins":
        raise RepoError("Корневой элемент «%s», а ожидался plugins"
                        % root.tag)
    if own_only and root.get("generator") != GENERATOR:
        raise RepoError(
            "Реестр создан не модулем Repoliner. Открываются только "
            "реестры с меткой generator=\"%s\"" % GENERATOR)
    try:
        base = check_base_url(root.get("base_url", ""))
    except RepoError as e:
        raise RepoError("Файл реестра испорчен: %s" % e)
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
            raise RepoError("У модуля «%s» нет ни file_name, ни "
                            "download_url" % name)
        repo.put(e)
    repo.dirty = False
    return repo


def load(path, own_only=True):
    if os.path.getsize(path) > MAX_XML_BYTES:
        raise RepoError("Файл реестра больше 5 МБ: %s" % path)
    with io.open(path, encoding="utf-8-sig") as f:
        text = f.read()
    repo = loads(text, own_only=own_only)
    repo.path = path
    return repo


def new(path):
    """Пустой реестр, сразу записанный на диск."""
    repo = Repository(path)
    repo.save()
    return repo
