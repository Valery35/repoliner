# -*- coding: utf-8 -*-
#
# Repoliner - репозитории модулей QGIS.
# © 2026 ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
#
"""Двуязычие окна без QGIS.

Каждая русская строка в plugin.py и view.py, кроме строк документации,
обязана иметь английский перевод. Проверяются все литералы, а не только
вызовы tr(): подписи столбцов и состояний переводятся через имя, и разбор
вызовов их не видит.

Запуск:  python repoliner/tests/test_i18n.py
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)
import i18n  # noqa: E402

UI_FILES = ("plugin.py", "view.py")
CYR = re.compile(u"[А-Яа-яЁё]")


def _literals(name):
    tree = ast.parse(open(os.path.join(PKG, name), encoding="utf-8").read())
    docs = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) \
                and n.body and isinstance(n.body[0], ast.Expr) \
                and isinstance(n.body[0].value, ast.Constant):
            docs.add(id(n.body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs and CYR.search(n.value)]


def test_every_ui_string_translated():
    missing = []
    for name in UI_FILES:
        lits = _literals(name)
        assert lits, "в %s не найдено ни одной строки" % name
        missing += ["%s: %s" % (name, s) for s in lits
                    if not i18n.TRANSLATIONS.get(s)]
    assert not missing, "нет перевода:\n" + "\n".join(missing)


def test_placeholders_match():
    bad = [k for k, v in i18n.TRANSLATIONS.items()
           if re.findall(r"%[sd]", k) != re.findall(r"%[sd]", v)]
    assert not bad, bad


def test_switch():
    i18n.set_language("en_US")
    assert i18n.tr("Сохранить") == "Save"
    assert i18n.tr("строка без перевода") == "строка без перевода"
    i18n.set_language("ru")
    assert i18n.tr("Сохранить") == "Сохранить"


def test_no_translations_without_use():
    used = set()
    for name in UI_FILES:
        used.update(_literals(name))
    extra = sorted(set(i18n.TRANSLATIONS) - used)
    assert not extra, "переводы без строки в коде: %s" % extra


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
    print("%d тестов, ошибок %d" % (len(fns), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(_run())
