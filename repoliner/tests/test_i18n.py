# -*- coding: utf-8 -*-
#
# Repoliner - QGIS plugin repositories.
# © 2026 Inform++ LLC / ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
#
"""Bilingual window without QGIS.

Every Russian string in plugin.py and view.py, apart from docstrings,
must have an English translation. All literals are checked, not only
tr() calls: column and state labels are translated through their name,
and parsing the calls does not see them.

Run:  python repoliner/tests/test_i18n.py
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
        assert lits, "no strings found in %s" % name
        missing += ["%s: %s" % (name, s) for s in lits
                    if not i18n.TRANSLATIONS.get(s)]
    assert not missing, "no translation:\n" + "\n".join(missing)


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
    assert not extra, "translations with no string in the code: %s" % extra


def _templates(module, exc_name):
    """Message templates raised by a module."""
    src = open(os.path.join(PKG, module), encoding="utf-8").read()
    out = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) \
                and getattr(node.func, "id", "") == exc_name \
                and node.args and isinstance(node.args[0], ast.Constant):
            out.append(node.args[0].value)
    return out


def _core_templates():
    """Error texts that the core raises as RepoError."""
    src = open(os.path.join(PKG, "core.py"), encoding="utf-8").read()
    out = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) \
                and getattr(node.func, "id", "") == "RepoError" \
                and node.args and isinstance(node.args[0], ast.Constant):
            out.append(node.args[0].value)
    return out


def test_core_messages_have_russian():
    """The core speaks English, the Russian text comes from the table.

    Without this guard a new core message would silently stay
    untranslated: it is still shown, only not in the right language.
    """
    templates = _core_templates() + _templates("xmlparse.py", "XmlError")
    assert len(templates) > 25, len(templates)
    assert not i18n.missing_messages(templates)
    for t in templates:
        ru = i18n.MESSAGES[t]
        assert re.findall(r"%[sd]", t) == re.findall(r"%[sd]", ru), t
        assert CYR.search(ru), t


def test_error_text_follows_language():
    class _E(Exception):
        template = "Archive not found: %s"
        values = ("x.zip",)

    i18n.set_language("ru")
    assert i18n.error_text(_E()) == "Архив не найден: x.zip"
    i18n.set_language("en")
    assert i18n.error_text(_E()) == "Archive not found: x.zip"
    assert i18n.error_text(ValueError("plain")) == "plain"


def test_nested_parser_error_is_translated():
    """A parser error ends up inside a registry error.

    Without translating the nested message the Russian text came out
    half English.
    """
    from repoliner import core
    i18n.set_language("ru")
    try:
        core.loads('<plugins generator="Repoliner"><a>')
    except core.RepoError as e:
        text = i18n.error_text(e)
    assert text.startswith("Файл реестра не разобран"), text
    assert "не закрыт" in text, text


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
    print("%d tests, %d failed" % (len(fns), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(_run())
