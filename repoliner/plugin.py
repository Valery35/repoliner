# -*- coding: utf-8 -*-
#
# Repoliner - репозитории модулей QGIS.
# © 2026 ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
"""Класс модуля: пункт меню «Модули - Repoliner» и кнопка на панели.

Совместимо с QGIS 3.16 - 4.x (Qt5 и Qt6).
"""
import os

from qgis.core import QgsMessageLog

MENU = "Repoliner"


def _log(msg):
    QgsMessageLog.logMessage(msg, MENU)


class RepolinerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self.toolbar = None

    def initGui(self):
        from qgis.PyQt.QtGui import QIcon
        try:
            from qgis.PyQt.QtGui import QAction        # Qt6 (QGIS 4)
        except ImportError:
            from qgis.PyQt.QtWidgets import QAction    # Qt5 (QGIS 3)
        from .i18n import tr, init_from_qgis
        from . import view
        init_from_qgis()
        if not view.is_available():
            _log(tr("Окно не создано: нет Qt или QGIS."))
            return
        win = self.iface.mainWindow()
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.svg"))
        action = QAction(icon, tr("Репозитории модулей…"), win)
        action.setToolTip(tr("Собрать реестр модулей QGIS из готовых архивов"))
        action.triggered.connect(lambda: view.show_view(self.iface))
        self.iface.addPluginToMenu(MENU, action)
        self.toolbar = self.iface.addToolBar(MENU)
        self.toolbar.setObjectName("RepolinerToolbar")
        self.toolbar.addAction(action)
        self.actions.append(action)

    def unload(self):
        for a in self.actions:
            self.iface.removePluginMenu(MENU, a)
        self.actions = []
        if self.toolbar is not None:
            self.toolbar.deleteLater()
            self.toolbar = None
        from . import view
        dlg = getattr(view.show_view, "_dlg", None)
        if dlg is not None:
            dlg.close()
            dlg.deleteLater()
            view.show_view._dlg = None
