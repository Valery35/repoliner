# -*- coding: utf-8 -*-
#
# Repoliner - QGIS plugin repositories.
# © 2026 Inform++ LLC / ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
"""Qt5 and Qt6 compatibility.

QGIS 3 is built on Qt5, QGIS 4 on Qt6. In Qt6 the enumerations are
strict: `Qt.CursorShape.WaitCursor` is needed instead of
`Qt.WaitCursor`, and `Qt.ItemDataRole.UserRole` instead of
`Qt.UserRole`. The flat name is simply absent there, and a call to it
brings the window down with an AttributeError.

The constants are resolved here once, so that the rest of the code has
no branches by version.
"""

from qgis.PyQt.QtCore import Qt


def _c(scope, name):
    """The strict name (Qt6), otherwise the flat one (Qt5)."""
    holder = getattr(Qt, scope, None)
    if holder is not None and hasattr(holder, name):
        return getattr(holder, name)
    return getattr(Qt, name)


WaitCursor          = _c("CursorShape",    "WaitCursor")
UserRole            = _c("ItemDataRole",   "UserRole")
Checked             = _c("CheckState",     "Checked")
Unchecked           = _c("CheckState",     "Unchecked")
ItemIsUserCheckable = _c("ItemFlag",       "ItemIsUserCheckable")
NonModal            = _c("WindowModality", "NonModal")


def dbb(name):
    """QDialogButtonBox buttons: in Qt6 they are split between
    StandardButton and ButtonRole.

    dbb('Ok'), dbb('Cancel'), dbb('ActionRole'), dbb('RejectRole').
    """
    from qgis.PyQt.QtWidgets import QDialogButtonBox
    for scope in ("StandardButton", "ButtonRole"):
        holder = getattr(QDialogButtonBox, scope, None)
        if holder is not None and hasattr(holder, name):
            return getattr(holder, name)
    return getattr(QDialogButtonBox, name)
