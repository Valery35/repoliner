# -*- coding: utf-8 -*-
#
# Repoliner - QGIS plugin repositories.
# © 2026 Inform++ LLC / ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
#
# This is free software: you may redistribute it and/or modify it under
# the terms of the GNU General Public License (GNU GPL) published by the
# Free Software Foundation (FSF), either version 2 of the License or (at
# your option) any later version.
#
# The program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY, including without the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU GPL
# for details.
#
# The full licence text is in the LICENSE file (in English, it is the
# legally binding one).
"""Repoliner - QGIS plugin repositories. Module entry point."""


def classFactory(iface):
    from .plugin import RepolinerPlugin
    return RepolinerPlugin(iface)
