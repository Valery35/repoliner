# -*- coding: utf-8 -*-
#
# Repoliner - репозитории модулей QGIS.
# © 2026 ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
"""Окно Repoliner: набор реестров plugins.xml и модули в них.

Расчёт и запись живут в core.py, окно только показывает дерево и
передаёт действия. Список реестров хранится в настройках QGIS, а каждый
реестр описан своим plugins.xml и больше нигде.

Архивы не копируются: адрес модуля в реестре ведёт на то место, где архив
лежит. Перенос архива ломает установку из реестра, поэтому у каждого
модуля показывается состояние архива.

Окно немодальное: реестр собирают, поглядывая в менеджер модулей QGIS.
"""

import os

try:
    from qgis.PyQt.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
        QPushButton, QLabel, QFileDialog, QMessageBox, QApplication,
        QHeaderView, QInputDialog,
    )
    from qgis.core import QgsSettings, Qgis, QgsMessageLog
    from . import qt_compat as qtc
    _QGIS = True
except Exception:                                   # nosec
    _QGIS = False

from . import core as pr
from .i18n import tr

SETTINGS_KEY = "Repoliner/repositories"
QGIS_REPOS = "app/plugin_repositories"

COLUMNS = ("Модуль", "Версия", "QGIS", "Архив", "Состояние")

STATUS_TEXT = {
    pr.ST_OK: "в порядке",
    pr.ST_MISSING: "архива по адресу нет",
    pr.ST_CHANGED: "архив не совпадает с реестром, перечитайте архивы",
    pr.ST_REMOTE: "адрес вне реестра, архив не проверяется",
}


def is_available():
    return _QGIS


def _enum(owner, scope, name):
    """Строгое имя перечисления (Qt6), иначе плоское (Qt5)."""
    holder = getattr(owner, scope, None)
    if holder is not None and hasattr(holder, name):
        return getattr(holder, name)
    return getattr(owner, name)


def stored_paths():
    """Пути к реестрам из настроек QGIS, по одному в строке."""
    raw = QgsSettings().value(SETTINGS_KEY, "")
    if isinstance(raw, (list, tuple)):
        raw = "\n".join(str(x) for x in raw)
    return [p for p in str(raw or "").splitlines() if p.strip()]


def store_paths(paths):
    QgsSettings().setValue(SETTINGS_KEY, "\n".join(paths))


def _bare(url):
    return (url or "").split("?")[0].rstrip("/")


def qgis_repositories():
    """Репозитории менеджера модулей QGIS: [(имя, адрес, включён)]."""
    s = QgsSettings()
    s.beginGroup(QGIS_REPOS)
    try:
        out = []
        for key in s.childGroups():
            enabled = str(s.value(key + "/enabled", True)).lower() \
                not in ("false", "0")
            out.append((key, str(s.value(key + "/url", "") or ""), enabled))
        return out
    finally:
        s.endGroup()


def connect_to_qgis(name, url):
    """Добавить реестр в менеджер модулей QGIS.

    Возвращает (имя, добавлен ли). Реестр с тем же адресом не дублируется.
    """
    repos = qgis_repositories()
    for key, u, _ in repos:
        if _bare(u) == _bare(url):
            return key, False
    names = set(k for k, _, _ in repos)
    base, n, key = name or "Repoliner", 2, name or "Repoliner"
    while key in names:
        key = "%s (%d)" % (base, n)
        n += 1
    s = QgsSettings()
    s.setValue("%s/%s/url" % (QGIS_REPOS, key), url)
    s.setValue("%s/%s/enabled" % (QGIS_REPOS, key), True)
    return key, True


def reload_plugin_manager():
    """Перечитать репозитории в менеджере модулей, как «Обновить все»."""
    try:
        from pyplugin_installer import instance
        instance().reloadAndExportData()
        return True
    except (ImportError, AttributeError, RuntimeError) as e:
        QgsMessageLog.logMessage(str(e), "Repoliner")
        return False


def foreign_versions(own_urls):
    """Модули, которые QGIS уже получил из других репозиториев.

    {имя модуля: [(репозиторий, версия)]}. Берётся из того, что менеджер
    модулей загрузил в этом сеансе, сеть не трогается. Пусто, если
    менеджер ещё не открывался.
    """
    own = set(_bare(u) for u in own_urls)
    try:
        from pyplugin_installer.installer_data import plugins, repositories
        repos = repositories.all()
        cache = plugins.repoCache
    except (ImportError, AttributeError):
        return {}
    best = {}
    for rname, items in cache.items():
        if _bare(repos.get(rname, {}).get("url", "")) in own:
            continue
        for p in items:
            key = (p.get("id"), rname)
            ver = p.get("version_available", "") or ""
            # каталог отдаёт стабильную и экспериментальную версии
            # отдельными записями, остаётся старшая
            if key not in best or pr.version_key(ver) > \
                    pr.version_key(best[key]):
                best[key] = ver
    out = {}
    for (pid, rname), ver in sorted(best.items()):
        out.setdefault(pid, []).append((rname, ver))
    return out


def show_view(iface):
    """Открывает окно. Повторный вызов поднимает уже открытое."""
    win = iface.mainWindow() if iface is not None else None
    existing = getattr(show_view, "_dlg", None)
    if existing is None:
        existing = RepoDialog(iface, win)
        show_view._dlg = existing

        def _forget():
            show_view._dlg = None

        existing.destroyed.connect(_forget)
    existing.show()
    existing.raise_()
    existing.activateWindow()
    return existing


class RepoDialog(QDialog):
    """Дерево «реестр - модули» и действия над ним."""

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle(tr("Repoliner - репозитории модулей"))
        self.setMinimumSize(820, 460)
        self.setModal(False)
        self.setWindowModality(qtc.NonModal)
        self.repos = []          # [(path, Repository или None, ошибка)]
        self._build()
        self._load_all()

    # ---- интерфейс ----

    def _button(self, row, text, slot, tip=""):
        b = QPushButton(text)
        if tip:
            b.setToolTip(tip)
        b.clicked.connect(slot)
        row.addWidget(b)
        return b

    def _build(self):
        root = QVBoxLayout(self)

        row1 = QHBoxLayout()
        self._button(row1, tr("Новый реестр…"), self.new_repo,
                     tr("Создать пустой plugins.xml и добавить его в список"))
        self._button(row1, tr("Открыть реестр…"), self.open_repo,
                     tr("Добавить в список реестр, созданный этим окном"))
        self._button(row1, tr("Убрать из списка"), self.forget_repo,
                     tr("Файл реестра на диске остаётся"))
        row1.addStretch(1)
        root.addLayout(row1)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(COLUMNS))
        self.tree.setHeaderLabels([tr(c) for c in COLUMNS])
        self.tree.setAlternatingRowColors(True)
        header = self.tree.header()
        header.setSectionResizeMode(
            _enum(QHeaderView, "ResizeMode", "ResizeToContents"))
        self.tree.currentItemChanged.connect(self._update_buttons)
        root.addWidget(self.tree, 1)

        row2 = QHBoxLayout()
        self.b_add = self._button(
            row2, tr("Добавить архивы…"), self.add_archives,
            tr("Модуль с той же папкой в архиве заменяется"))
        self.b_del = self._button(
            row2, tr("Удалить отмеченные"), self.remove_checked,
            tr("Из реестра, архивы на диске остаются"))
        self.b_refresh = self._button(
            row2, tr("Перечитать архивы"), self.refresh_repo,
            tr("Взять версии и описания из архивов заново"))
        row2.addStretch(1)
        self.b_save = self._button(row2, tr("Сохранить"), self.save_repo)
        self.b_copy = self._button(
            row2, tr("Копировать адрес"), self.copy_url,
            tr("Адрес для Модули - Управление - Настройки - Добавить"))
        self.b_connect = self._button(
            row2, tr("Подключить в QGIS"), self.connect_repo,
            tr("Добавить реестр в менеджер модулей QGIS"))
        self.b_base = self._button(
            row2, tr("Адрес сервера…"), self.set_base,
            tr("Для реестра, который раздаёт веб-сервер. Пусто - адреса "
               "файлов на диске"))
        close = QPushButton(tr("Закрыть"))
        close.clicked.connect(self.close)
        row2.addWidget(close)
        root.addLayout(row2)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

    # ---- список реестров ----

    def _load_all(self):
        self.repos = []
        for path in stored_paths():
            self.repos.append(self._read(path))
        self._fill()

    @staticmethod
    def _read(path):
        try:
            return [path, pr.load(path), ""]
        except (pr.RepoError, OSError) as e:
            return [path, None, str(e)]

    def _remember(self):
        store_paths([p for p, _, _ in self.repos])

    def _index_of(self, path):
        norm = os.path.normcase(os.path.abspath(path))
        for i, (p, _, _) in enumerate(self.repos):
            if os.path.normcase(os.path.abspath(p)) == norm:
                return i
        return -1

    def _append(self, entry):
        i = self._index_of(entry[0])
        if i >= 0:
            self.repos[i] = entry
        else:
            self.repos.append(entry)
            i = len(self.repos) - 1
        self._remember()
        self._fill(select=i)

    def new_repo(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Новый реестр"), "plugins.xml", "plugins.xml (*.xml)")
        if not path:
            return
        try:
            repo = pr.new(path)
        except (pr.RepoError, OSError) as e:
            self._say(tr("Реестр не создан: %s") % e)
            return
        self._append([path, repo, ""])
        self._say(tr("Создан пустой реестр %s") % path)

    def open_repo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Открыть реестр"), "", "plugins.xml (*.xml)")
        if not path:
            return
        entry = self._read(path)
        if entry[1] is None:
            QMessageBox.warning(self, tr("Репозитории модулей"), entry[2])
            return
        self._append(entry)
        self._say(tr("Реестр открыт, модулей %d") % len(entry[1].entries))

    def forget_repo(self):
        i = self._current_index()
        if i < 0:
            return
        path, repo, _ = self.repos[i]
        if repo is not None and repo.dirty and not self._confirm(
                tr("В реестре есть несохранённые изменения. "
                   "Убрать его из списка без сохранения?")):
            return
        del self.repos[i]
        self._remember()
        self._fill()
        self._say(tr("Реестр убран из списка, файл остался: %s") % path)

    # ---- модули ----

    def add_archives(self):
        i = self._current_index()
        repo = self._current_repo(i)
        if repo is None:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, tr("Архивы модулей"), "", tr("Архивы zip (*.zip)"))
        if not paths:
            return
        QApplication.setOverrideCursor(qtc.WaitCursor)
        try:
            added, replaced, errors = repo.add_archives(paths)
        finally:
            QApplication.restoreOverrideCursor()
        self._fill(select=i)
        parts = [tr("Добавлено модулей %d, заменено %d")
                 % (len(added), len(replaced))]
        if errors:
            parts.append(tr("Не прочитаны") + "\n" + "\n".join(errors))
        self._say(". ".join(parts))

    def remove_checked(self):
        i = self._current_index()
        repo = self._current_repo(i)
        if repo is None:
            return
        top = self.tree.topLevelItem(i)
        keys = []
        for k in range(top.childCount()):
            ch = top.child(k)
            if ch.checkState(0) == qtc.Checked:
                keys.append(ch.data(0, qtc.UserRole))
        if not keys:
            self._say(tr("Отметьте модули, которые надо удалить из реестра."))
            return
        for key in keys:
            repo.remove(key)
        self._fill(select=i)
        self._say(tr("Удалено модулей %d. Реестр не сохранён.") % len(keys))

    def refresh_repo(self):
        i = self._current_index()
        repo = self._current_repo(i)
        if repo is None:
            return
        updated, errors = repo.refresh()
        self._fill(select=i)
        parts = [tr("Обновлено модулей %d") % len(updated)]
        if errors:
            parts.append(tr("Не прочитаны") + "\n" + "\n".join(errors))
        self._say(". ".join(parts))

    def save_repo(self):
        i = self._current_index()
        repo = self._current_repo(i)
        if repo is None:
            return
        try:
            repo.save()
        except (pr.RepoError, OSError) as e:
            self._say(tr("Реестр не сохранён: %s") % e)
            return
        self._fill(select=i)
        self._say(tr("Сохранено: %s") % repo.path)

    def copy_url(self):
        repo = self._current_repo(self._current_index())
        if repo is None:
            return
        QApplication.clipboard().setText(repo.url)
        text = tr("Адрес скопирован: %s") % repo.url
        if repo.dirty:
            text += ". " + tr("Сохраните реестр, иначе QGIS прочитает "
                              "прежний файл.")
        self._say(text)

    def connect_repo(self):
        repo = self._current_repo(self._current_index())
        if repo is None:
            return
        if repo.dirty:
            self._say(tr("Сначала сохраните реестр."))
            return
        name = os.path.basename(repo.folder) or "Repoliner"
        key, added = connect_to_qgis("Repoliner - " + name, repo.url)
        if not added:
            self._say(tr("Реестр уже подключён в QGIS под именем «%s».")
                      % key)
            return
        reload_plugin_manager()
        self._fill(select=self._current_index())
        self._say(tr("Реестр подключён в QGIS под именем «%s».") % key)

    def set_base(self):
        i = self._current_index()
        repo = self._current_repo(i)
        if repo is None:
            return
        text, ok = QInputDialog.getText(
            self, tr("Адрес сервера"),
            tr("Адрес, по которому веб-сервер раздаёт папку реестра.\n"
               "Пусто - адреса файлов на диске (file:///)."),
            text=repo.base_url)
        if not ok:
            return
        try:
            repo.set_base_url(text)
        except pr.RepoError as e:
            self._say(tr("Адрес не изменён: %s") % e)
            return
        self._fill(select=i)
        self._say(tr("Адреса архивов переписаны. Реестр не сохранён."))

    # ---- дерево ----

    def _fill(self, select=None):
        self.tree.clear()
        qgis_ver = self._qgis_version()
        owners = {}
        own_urls = [r.url for _, r, _ in self.repos if r is not None]
        foreign = foreign_versions(own_urls)
        for p, repo, _ in self.repos:
            for e in (repo.entries if repo else []):
                owners.setdefault(e.key, []).append(p)
        for idx, (path, repo, err) in enumerate(self.repos):
            title = os.path.basename(os.path.dirname(path)) or path
            if repo is not None and repo.dirty:
                title += " *"
            top = QTreeWidgetItem([title, "", "", path, ""])
            if repo is not None and repo.base_url:
                top.setText(3, "%s  (%s)" % (path, repo.base_url))
            top.setData(0, qtc.UserRole, idx)
            top.setToolTip(3, path)
            if repo is None:
                top.setText(4, tr("не читается: %s") % err)
            else:
                top.setText(4, tr("модулей %d") % len(repo.entries))
                for e in sorted(repo.entries, key=lambda x: x.name.lower()):
                    top.addChild(self._plugin_item(
                        repo, e, qgis_ver, owners[e.key],
                        foreign.get(e.key, [])))
            self.tree.addTopLevelItem(top)
            top.setExpanded(True)
        if select is not None and 0 <= select < self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(select))
        self._update_buttons()

    def _plugin_item(self, repo, e, qgis_ver, owners, foreign):
        lo, hi = e.qgis_range
        arc = repo.local_path(e) or e.download_url
        notes = [tr(STATUS_TEXT[repo.status(e)])]
        if qgis_ver and not e.is_compatible(qgis_ver):
            notes.append(tr("QGIS %s модуль не покажет") % qgis_ver)
        if len(owners) > 1:
            notes.append(tr("имя модуля есть ещё в %d реестрах, QGIS "
                            "сольёт записи") % (len(owners) - 1))
        for rname, ver in foreign:
            if pr.version_key(ver) == pr.version_key(e.version):
                continue            # та же версия, подменять нечем
            notes.append(tr("есть в «%s» (%s), QGIS может показать ту "
                            "версию") % (rname, ver))
        if e.elements.get("experimental") == "True":
            notes.append(tr("экспериментальный"))
        item = QTreeWidgetItem([e.name, e.version, "%s - %s" % (lo, hi),
                                arc, ", ".join(notes)])
        item.setData(0, qtc.UserRole, e.key)
        item.setFlags(item.flags() | qtc.ItemIsUserCheckable)
        item.setCheckState(0, qtc.Unchecked)
        item.setToolTip(0, e.elements.get("description", ""))
        item.setToolTip(3, e.download_url)
        return item

    @staticmethod
    def _qgis_version():
        try:
            return Qgis.QGIS_VERSION.split("-")[0]
        except AttributeError:
            return ""

    def _current_index(self):
        item = self.tree.currentItem()
        if item is None:
            return -1
        while item.parent() is not None:
            item = item.parent()
        return self.tree.indexOfTopLevelItem(item)

    def _current_repo(self, i):
        if i < 0:
            self._say(tr("Выберите реестр в списке."))
            return None
        repo = self.repos[i][1]
        if repo is None:
            self._say(tr("Реестр не читается: %s") % self.repos[i][2])
        return repo

    def _update_buttons(self, *args):
        i = self._current_index()
        ok = i >= 0 and self.repos[i][1] is not None
        for b in (self.b_add, self.b_del, self.b_refresh, self.b_save,
                  self.b_copy, self.b_connect, self.b_base):
            b.setEnabled(ok)

    # ---- служебное ----

    def _say(self, text):
        self.status.setText(text)

    def _confirm(self, text):
        yes = _enum(QMessageBox, "StandardButton", "Yes")
        no = _enum(QMessageBox, "StandardButton", "No")
        return QMessageBox.question(
            self, tr("Репозитории модулей"), text, yes | no, no) == yes

    def closeEvent(self, event):
        dirty = [p for p, r, _ in self.repos if r is not None and r.dirty]
        if dirty and not self._confirm(
                tr("Несохранённые изменения в реестрах") + "\n"
                + "\n".join(dirty) + "\n" + tr("Закрыть без сохранения?")):
            event.ignore()
            return
        if dirty:
            self._load_all()       # несохранённое отбрасывается
        event.accept()
