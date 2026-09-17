# -*- coding: utf-8 -*-
"""Run the dialog without QGIS: PyQt6 plus fake qgis.core, qgis.PyQt.

Checks that the dialog builds on Qt6 and that the actions run to the
end: new repository, two archives, save, read back, remove checked,
close. The file choosers are replaced with stubs.

    QT_QPA_PLATFORM=offscreen python tools/smoke_view.py
"""
import os
import sys
import tempfile
import types
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402

qgis = types.ModuleType("qgis")
pyqt = types.ModuleType("qgis.PyQt")
pyqt.QtCore, pyqt.QtGui, pyqt.QtWidgets = QtCore, QtGui, QtWidgets
core = types.ModuleType("qgis.core")
_store = {}


class QgsSettings(object):
    def __init__(self):
        self._g = ""

    def _k(self, key):
        return self._g + key

    def value(self, key, default=None):
        return _store.get(self._k(key), default)

    def setValue(self, key, value):
        _store[self._k(key)] = value

    def beginGroup(self, g):
        self._g = g + "/"

    def endGroup(self):
        self._g = ""

    def childGroups(self):
        out = []
        for k in _store:
            if k.startswith(self._g):
                head = k[len(self._g):].split("/")
                if len(head) > 1 and head[0] not in out:
                    out.append(head[0])
        return out


class Qgis(object):
    QGIS_VERSION = "4.0.3-Norrköping"


core.QgsSettings, core.Qgis = QgsSettings, Qgis
core.QgsMessageLog = type("L", (), {"logMessage": staticmethod(print)})
sys.modules.update({"qgis": qgis, "qgis.PyQt": pyqt, "qgis.core": core,
                    "qgis.PyQt.QtCore": QtCore, "qgis.PyQt.QtGui": QtGui,
                    "qgis.PyQt.QtWidgets": QtWidgets})

from repoliner import view, i18n  # noqa: E402

i18n.set_language(sys.argv[1] if len(sys.argv) > 1 else "ru")
app = QtWidgets.QApplication([])
d = tempfile.mkdtemp(prefix="smoke ")
arcs = []
for name, ver in (("alpha", "1.0.0"), ("beta", "2.0.0")):
    p = os.path.join(d, name + ".zip")
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(name + "/metadata.txt",
                   "[general]\nname=%s\nversion=%s\nqgisMinimumVersion=3.16"
                   "\ndescription=d\n" % (name.title(), ver))
    arcs.append(p)
xml = os.path.join(d, "repo", "plugins.xml")
os.makedirs(os.path.dirname(xml))

FD = QtWidgets.QFileDialog
FD.getSaveFileName = staticmethod(lambda *a, **k: (xml, ""))
FD.getOpenFileNames = staticmethod(lambda *a, **k: (arcs, ""))
FD.getOpenFileName = staticmethod(lambda *a, **k: (xml, ""))
QtWidgets.QMessageBox.question = staticmethod(
    lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Yes)

dlg = view.RepoDialog(None)
dlg.show()
dlg.new_repo()
dlg.add_archives()
top = dlg.tree.topLevelItem(0)
assert top.childCount() == 2, top.childCount()
assert top.text(0).endswith("*")
print("status:", dlg.status.text())
print("row:", [top.child(0).text(c) for c in range(5)])
dlg.save_repo()
dlg.copy_url()
assert QtWidgets.QApplication.clipboard().text().startswith("file:///")
assert view.stored_paths() == [xml]
top = dlg.tree.topLevelItem(0)
top.child(0).setCheckState(0, QtCore.Qt.CheckState.Checked)
dlg.tree.setCurrentItem(top.child(1))
dlg.remove_checked()
assert dlg.tree.topLevelItem(0).childCount() == 1
dlg.refresh_repo()
dlg.close()                     # unsaved changes are dropped
dlg2 = view.RepoDialog(None)
assert dlg2.tree.topLevelItem(0).childCount() == 2
dlg2.tree.setCurrentItem(dlg2.tree.topLevelItem(0))
dlg2.forget_repo()
assert view.stored_paths() == []
dlg2.open_repo()
assert dlg2.tree.topLevelItemCount() == 1
os.remove(arcs[1])
dlg2._fill(select=0)
print("no archive:", dlg2.tree.topLevelItem(0).child(1).text(4))

# connect in QGIS: once, a repeat does not add a duplicate
_store["app/plugin_repositories/Официальный/url"] = \
    "https://plugins.qgis.org/plugins/plugins.xml"
dlg2.tree.setCurrentItem(dlg2.tree.topLevelItem(0))
dlg2.connect_repo()
print("connect:", dlg2.status.text())
dlg2.connect_repo()
print("repeat:", dlg2.status.text())
names = view.qgis_repositories()
assert len(names) == 2, names
assert any(u.startswith("file:///") for _, u, _ in names), names

# server address: archives inside the repository folder
import shutil  # noqa: E402
inside = os.path.join(os.path.dirname(xml), "alpha.zip")
shutil.copy(arcs[0], inside)
FD.getOpenFileNames = staticmethod(lambda *a, **k: ([inside], ""))
dlg3 = view.RepoDialog(None)
dlg3.tree.setCurrentItem(dlg3.tree.topLevelItem(0))
repo = dlg3.repos[0][1]
repo.entries = []
dlg3.add_archives()
QtWidgets.QInputDialog.getText = staticmethod(
    lambda *a, **k: ("http://srv/plugins", True))
dlg3.set_base()
print("server:", dlg3.status.text())
top = dlg3.tree.topLevelItem(0)
print("row:", top.text(3), "|", top.child(0).text(4))
assert repo.url == "http://srv/plugins/plugins.xml", repo.url
QtWidgets.QInputDialog.getText = staticmethod(
    lambda *a, **k: ("ftp://x", True))
dlg3.set_base()
print("rejected:", dlg3.status.text())
assert repo.base_url == "http://srv/plugins/"
# plugins from other repositories: duplicates and the same version
pi = types.ModuleType("pyplugin_installer")
pid = types.ModuleType("pyplugin_installer.installer_data")


class _Repos(object):
    def all(self):
        return {"Кат": {"url": "https://plugins.qgis.org/plugins.xml"}}


class _Plugins(object):
    repoCache = {"Кат": [
        {"id": "alpha", "version_available": "0.9.0"},
        {"id": "alpha", "version_available": "0.10.0"},
        {"id": "beta", "version_available": "2.0.0"}]}


pid.repositories, pid.plugins = _Repos(), _Plugins()
sys.modules["pyplugin_installer"] = pi
sys.modules["pyplugin_installer.installer_data"] = pid
fv = view.foreign_versions([])
assert fv == {"alpha": [("Кат", "0.10.0")], "beta": [("Кат", "2.0.0")]}, fv
d4 = tempfile.mkdtemp(prefix="smoke4 ")
x4 = os.path.join(d4, "plugins.xml")
FD.getSaveFileName = staticmethod(lambda *a, **k: (x4, ""))
FD.getOpenFileNames = staticmethod(lambda *a, **k: (arcs[:1], ""))
dlg4 = view.RepoDialog(None)
dlg4.new_repo()
dlg4.add_archives()
row = dlg4.tree.topLevelItem(dlg4.tree.topLevelItemCount() - 1).child(0)
print("foreign:", row.text(4))
assert row.text(4).count("0.10.0") == 1 and "0.9.0" not in row.text(4)
print("OK")
