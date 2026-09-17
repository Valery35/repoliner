# -*- coding: utf-8 -*-
#
# Repoliner - репозитории модулей QGIS.
# © 2026 ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
#
"""Реестр модулей QGIS из zip-архивов, без QGIS.

Проверяется то, от чего зависит, увидит ли QGIS модуль вообще:
- адрес архива полный, file:///, пробелы закодированы. Относительный
  адрес QGIS не разрешает;
- имя модуля в реестре (file_name) берётся по папке внутри архива, а
  не по имени файла. QGIS после скачивания ищет в архиве папку с этим
  именем, и на topoliner_upload.zip с папкой topoliner установка
  обрывалась. Архив с той же папкой заменяет запись, а не дублирует её;
- записанный реестр читается обратно без потерь;
- чужой реестр и файл с объявлением сущностей не читаются.

Запуск:  python repoliner/tests/test_core.py
"""
import os
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from repoliner import core as pr  # noqa: E402

META = u"""[general]
name={name}
qgisMinimumVersion={qmin}
qgisMaximumVersion=4.99
description=Модуль {name} & проверка <тегов>
about=Первая строка.
    Вторая строка.
version={version}
author=ООО «Информ++»
email=secret@example.com
homepage=https://example.com/{folder}
tracker=https://example.com/{folder}/issues
repository=https://example.com/{folder}
tags=a,b
experimental={exp}
deprecated=False
changelog=100%% новое
icon=icon.png
"""


def make_zip(where, file_name, folder, name, version, qmin="3.16",
             exp="False"):
    path = os.path.join(where, file_name)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(folder + "/metadata.txt", META.format(
            name=name, version=version, qmin=qmin, exp=exp,
            folder=folder).encode("utf-8"))
        z.writestr(folder + "/__init__.py", "")
    return path


class _Tmp(object):
    def __enter__(self):
        self.d = tempfile.mkdtemp(prefix="repoliner repo ")
        return self.d

    def __exit__(self, *a):
        shutil.rmtree(self.d, ignore_errors=True)


def _two(d):
    arc = os.path.join(d, "архивы")
    os.makedirs(arc)
    a = make_zip(arc, "alpha.zip", "alpha", "Alpha", "1.0.0")
    b = make_zip(arc, "beta.zip", "beta_plugin", "Beta", "2.1.0",
                 exp="True")
    return a, b


def test_two_archives_make_two_entries():
    with _Tmp() as d:
        a, b = _two(d)
        repo = pr.Repository(os.path.join(d, "repo", "plugins.xml"))
        added, replaced, errors = repo.add_archives([a, b])
        assert (len(added), len(replaced), errors) == (2, 0, [])
        text = repo.dumps()
        assert text.count("<pyqgis_plugin ") == 2
        assert '<plugins generator="Repoliner">' in text
        assert '<pyqgis_plugin name="Alpha" version="1.0.0">' in text
        assert "<file_name>beta_plugin.zip</file_name>" in text
        assert "/beta.zip</download_url>" in text
        assert "<experimental>True</experimental>" in text
        assert "<author_name>ООО «Информ++»</author_name>" in text
        assert "<qgis_minimum_version>3.16</qgis_minimum_version>" in text
        # не переносятся
        for absent in ("secret@example.com", "changelog", "<icon>",
                       "<email>"):
            assert absent not in text, absent
        # экранирование
        assert "&amp; проверка &lt;тегов&gt;" in text


def test_download_url_is_absolute_file_url():
    with _Tmp() as d:
        a, _ = _two(d)
        e = pr.entry_from_archive(a)
        url = e.download_url
        assert url.startswith("file:///"), url
        assert " " not in url, url               # пробел в пути закодирован
        assert url.endswith("/alpha.zip"), url
        assert os.path.samefile(e.archive_path, a)


def test_url_roundtrip_windows_and_unc():
    assert pr.url_to_path("file:///C:/Dev/a%20b/x.zip").replace(
        "\\", "/") == "C:/Dev/a b/x.zip"
    assert pr.url_to_path("https://h/x.zip") is None
    p = pr.url_to_path("file://server/share/x.zip").replace("\\", "/")
    assert p == "//server/share/x.zip", p


def test_saved_registry_reads_back():
    with _Tmp() as d:
        a, b = _two(d)
        path = os.path.join(d, "plugins.xml")
        repo = pr.Repository(path)
        repo.add_archives([a, b])
        repo.save()
        back = pr.load(path)
        assert [e.key for e in back.entries] == ["alpha", "beta_plugin"]
        for e in repo.entries:
            f = back.find(e.key)
            assert (f.name, f.version) == (e.name, e.version)
            assert f.elements == e.elements, e.key
        assert back.find("alpha").status() == pr.ST_OK
        assert back.dumps() == repo.dumps()


def test_same_archive_name_replaces_entry():
    with _Tmp() as d:
        a, b = _two(d)
        repo = pr.Repository()
        repo.add_archives([a, b])
        other = os.path.join(d, "новая")
        os.makedirs(other)
        a2 = make_zip(other, "alpha.zip", "alpha", "Alpha", "1.0.1")
        added, replaced, _ = repo.add_archives([a2])
        assert (len(added), len(replaced)) == (0, 1)
        assert len(repo.entries) == 2
        assert repo.find("alpha").version == "1.0.1"


def test_file_name_follows_folder_not_archive_name():
    """Файл выбирает пользователь, имя модуля даёт папка внутри."""
    with _Tmp() as d:
        p = make_zip(d, "topoliner_upload.zip", "topoliner", "Topoliner",
                     "0.12.7")
        e = pr.entry_from_archive(p)
        assert e.file_name == "topoliner.zip"
        assert e.key == "topoliner"
        assert e.download_url.endswith("/topoliner_upload.zip")
        assert e.status() == pr.ST_OK
        # тот же модуль под другим именем файла заменяет запись
        repo = pr.Repository()
        repo.add_archives([p, make_zip(d, "topoliner.zip", "topoliner",
                                       "Topoliner", "0.12.8")])
        assert len(repo.entries) == 1
        assert repo.find("topoliner").version == "0.12.8"


def test_old_registry_with_file_name_by_archive_is_flagged():
    """Реестр 0.1.0 писал file_name по имени файла, QGIS такой не ставит."""
    with _Tmp() as d:
        p = make_zip(d, "topoliner_upload.zip", "topoliner", "Topoliner",
                     "0.12.7")
        e = pr.entry_from_archive(p)
        e.elements["file_name"] = "topoliner_upload.zip"
        repo = pr.Repository()
        repo.put(e)
        assert repo.find("topoliner_upload").status() == pr.ST_CHANGED
        updated, errors = repo.refresh()
        assert len(updated) == 1 and not errors
        assert [x.key for x in repo.entries] == ["topoliner"]
        assert repo.find("topoliner").status() == pr.ST_OK


def test_key_is_name_before_first_dot():
    assert pr.plugin_key("grid_isolines.5.13.zip") == "grid_isolines"
    assert pr.plugin_key("C:/x/grid_isolines_nightly.zip") == \
        "grid_isolines_nightly"


def test_status_follows_archive():
    with _Tmp() as d:
        a, b = _two(d)
        repo = pr.Repository()
        repo.add_archives([a, b])
        make_zip(os.path.dirname(a), "alpha.zip", "alpha", "Alpha", "1.1.0")
        os.remove(b)
        assert repo.find("alpha").status() == pr.ST_CHANGED
        assert repo.find("beta_plugin").status() == pr.ST_MISSING
        updated, errors = repo.refresh()
        assert [e.version for e in updated] == ["1.1.0"]
        assert len(errors) == 1
        assert repo.find("alpha").status() == pr.ST_OK
        remote = pr.PluginEntry("R", "1", {
            "download_url": "https://h/r.zip"})
        assert remote.status() == pr.ST_REMOTE
        assert remote.key == "r"


def test_version_key_orders_numerically():
    assert pr.version_key("5.13.14") > pr.version_key("5.13.4")
    assert pr.version_key("2.27.4") < pr.version_key("5.13.4")
    assert pr.version_key("0.12.7") == pr.version_key("0.12.7")


def test_compatibility_matches_qgis_rule():
    e = pr.PluginEntry("X", "1", {"qgis_minimum_version": "3.16",
                                  "qgis_maximum_version": "4.99"})
    assert e.is_compatible("3.40.5") and e.is_compatible("4.0.3")
    e = pr.PluginEntry("X", "1", {"qgis_minimum_version": "3.28"})
    assert e.qgis_range == ("3.28", "3.99")
    assert e.is_compatible("3.40") and not e.is_compatible("4.0.3")
    assert not e.is_compatible("3.22")


def test_foreign_registry_reads_only_on_request():
    text = ('<?xml version="1.0"?>\n<plugins>\n'
            '  <pyqgis_plugin name="Night" version="4.13.0">\n'
            '    <file_name>grid_isolines_nightly.zip</file_name>\n'
            '    <download_url>https://h/grid_isolines_nightly.zip'
            '</download_url>\n'
            '    <experimental>True</experimental>\n'
            '  </pyqgis_plugin>\n</plugins>\n')
    try:
        pr.loads(text)
    except pr.RepoError as e:
        assert "generator" in str(e)
    else:
        raise AssertionError("реестр без метки прочитан как свой")
    repo = pr.loads(text, own_only=False)
    e = repo.find("grid_isolines_nightly")
    assert e is not None and e.elements["experimental"] == "True"
    assert e.status() == pr.ST_REMOTE


def test_foreign_and_hostile_files_refused():
    cases = (
        '<?xml version="1.0"?><plugins></plugins>',
        '<?xml version="1.0"?><!DOCTYPE plugins [<!ENTITY a "aaaa">]>'
        '<plugins generator="Repoliner">&a;</plugins>',
        '<?xml version="1.0"?><other generator="Repoliner"/>',
        '<plugins generator="Repoliner"><pyqgis_plugin name="x">',
        '<plugins generator="Repoliner"><pyqgis_plugin name="x" '
        'version="1"/></plugins>',
    )
    for text in cases:
        try:
            pr.loads(text)
        except pr.RepoError:
            continue
        raise AssertionError("прочитано: %s" % text)
    try:
        pr.loads("<plugins generator='Repoliner'>" + " " * pr.MAX_XML_BYTES
                 + "</plugins>")
    except pr.RepoError as e:
        assert "5 МБ" in str(e)
    else:
        raise AssertionError("предел размера не сработал")


def test_bad_archives_reported_not_raised():
    with _Tmp() as d:
        junk = os.path.join(d, "junk.zip")
        with open(junk, "wb") as f:
            f.write(b"not a zip")
        empty = os.path.join(d, "empty.zip")
        with zipfile.ZipFile(empty, "w") as z:
            z.writestr("readme.txt", "x")
        nover = os.path.join(d, "nover.zip")
        with zipfile.ZipFile(nover, "w") as z:
            z.writestr("nover/metadata.txt", "[general]\nname=N\n")
        repo = pr.Repository()
        added, _, errors = repo.add_archives(
            [junk, empty, nover, os.path.join(d, "нет.zip")])
        assert added == [] and len(errors) == 4
        assert repo.entries == [] and not repo.dirty


def test_new_registry_is_empty_and_own():
    with _Tmp() as d:
        path = os.path.join(d, "plugins.xml")
        pr.new(path)
        repo = pr.load(path)
        assert repo.entries == [] and repo.url.startswith("file:///")


def test_unc_and_drive_paths_make_standard_urls():
    assert pr.path_to_url("\\\\srv\\share\\Мод ули\\a.zip") == \
        "file://srv/share/%D0%9C%D0%BE%D0%B4%20%D1%83%D0%BB%D0%B8/a.zip"
    # проверено на QGIS 4.0.3: file://localhost/C%24/… не открывается,
    # file://127.0.0.1/C%24/… открывается
    assert pr.path_to_url("\\\\localhost\\C$\\x.zip") == \
        "file://127.0.0.1/C%24/x.zip"
    assert pr.path_to_url("C:\\Dev\\a b\\x.zip") == \
        "file:///C:/Dev/a%20b/x.zip"
    for u in ("file://srv/share/%D0%9C%D0%BE%D0%B4%20%D1%83%D0%BB%D0%B8/"
              "a.zip", "file:///C:/Dev/a%20b/x.zip"):
        back = pr.url_to_path(u).replace("\\", "/")
        assert pr.path_to_url(back) == u, (u, back)


def _served_repo(d):
    """Реестр в папке d с архивами в подпапке «модули», адрес сервера."""
    arc = os.path.join(d, "модули")
    os.makedirs(arc)
    a = make_zip(arc, "alpha.zip", "alpha", "Alpha", "1.0.0")
    b = make_zip(arc, "beta upload.zip", "beta", "Beta", "2.0.0")
    repo = pr.Repository(os.path.join(d, "plugins.xml"))
    repo.add_archives([a, b])
    return repo, a, b


def test_base_url_rewrites_addresses_and_back():
    with _Tmp() as d:
        repo, a, b = _served_repo(d)
        assert repo.find("beta").download_url.startswith("file:///")
        repo.set_base_url("http://srv:8080/plugins")
        urls = sorted(e.download_url for e in repo.entries)
        assert urls == [
            "http://srv:8080/plugins/%D0%BC%D0%BE%D0%B4%D1%83%D0%BB%D0%B8/"
            "alpha.zip",
            "http://srv:8080/plugins/%D0%BC%D0%BE%D0%B4%D1%83%D0%BB%D0%B8/"
            "beta%20upload.zip"], urls
        assert repo.url == "http://srv:8080/plugins/plugins.xml"
        for e in repo.entries:
            assert repo.status(e) == pr.ST_OK, e.key
            assert e.status() == pr.ST_REMOTE    # без реестра не проверить
        repo.save()
        back = pr.load(repo.path)
        assert back.base_url == "http://srv:8080/plugins/"
        assert back.dumps() == repo.dumps()
        assert [back.status(e) for e in back.entries] == [pr.ST_OK] * 2
        # новый архив сразу получает адрес сервера
        c = make_zip(os.path.join(d, "модули"), "gamma.zip", "gamma", "G",
                     "1")
        back.add_archives([c])
        assert back.find("gamma").download_url.startswith("http://srv:8080/")
        back.set_base_url("")
        assert all(e.download_url.startswith("file:///")
                   for e in back.entries)
        assert back.url.startswith("file:///")


def test_base_url_refuses_archive_outside_folder():
    with _Tmp() as d:
        outside = make_zip(d, "out.zip", "out", "Out", "1")
        sub = os.path.join(d, "реестр")
        os.makedirs(sub)
        repo = pr.Repository(os.path.join(sub, "plugins.xml"))
        repo.add_archives([outside])
        before = repo.dumps()
        try:
            repo.set_base_url("https://srv/p/")
        except pr.RepoError as e:
            assert "вне папки" in str(e)
        else:
            raise AssertionError("архив вне папки принят")
        assert repo.dumps() == before and repo.base_url == ""
        repo.set_base_url("")
        added, _, errors = pr.Repository(repo.path, "https://srv/p/") \
            .add_archives([outside])
        assert not added and "вне папки" in errors[0]
        for bad in ("ftp://x/", "srv/p", "http://a b/"):
            try:
                pr.check_base_url(bad)
            except pr.RepoError:
                continue
            raise AssertionError(bad)


def test_served_registry_downloads_over_http():
    """Настоящий веб-сервер: реестр и архивы скачиваются по записанным
    адресам, архив читается."""
    import threading
    import urllib.request
    from functools import partial
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    with _Tmp() as d:
        srv = HTTPServer(("127.0.0.1", 0), partial(Quiet, directory=d))
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            repo, a, b = _served_repo(d)
            repo.set_base_url("http://127.0.0.1:%d/" % srv.server_port)
            repo.save()
            text = urllib.request.urlopen(
                repo.url + "?qgis=4.0", timeout=10).read().decode("utf-8")
            got = pr.loads(text)
            for e in got.entries:
                data = urllib.request.urlopen(e.download_url,
                                              timeout=10).read()
                path = os.path.join(d, "down_" + e.file_name)
                with open(path, "wb") as f:
                    f.write(data)
                assert pr.read_archive(path)["folder"] == e.key
        finally:
            srv.shutdown()
            srv.server_close()


def _run():
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    bad = 0
    for name, fn in fns:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            bad += 1
            print("FAIL %s: %r" % (name, exc))
    print("%d тестов, ошибок %d" % (len(fns), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(_run())
