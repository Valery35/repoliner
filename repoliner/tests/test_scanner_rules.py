# -*- coding: utf-8 -*-
#
# Repoliner - QGIS plugin repositories.
# © 2026 Inform++ LLC / ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Regression against findings of the plugins.qgis.org catalog security
# scanner.
#
# The catalog runs the uploaded release through the scanner and blocks
# findings. Caught in July 2026:
#   - `.pytest_cache/CACHEDIR.TAG` taken for a high entropy string
#     (closed in tests/test_package_hygiene.py);
#   - `xml.etree.ElementTree` when reading a Leapfrog palette: the
#     standard parser is vulnerable to blown up entities and external
#     references, and defusedxml cannot be pulled into the plugin, it
#     is not in the QGIS distribution.
#
# This test keeps the sources away from constructs that the scanner
# considers dangerous. It is cheaper to catch it here than to learn it
# from a block after the upload.
#     python repoliner/tests/test_scanner_rules.py
import os
import re
import sys

PKG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# (pattern, what to use instead) - only what the catalog has already
# caught or catches by the documented scanner rules
BANNED = (
    (r"\bimport\s+xml\b", "свой разбор без модулей xml"),
    (r"\bfrom\s+xml[\s.]", "свой разбор без модулей xml"),
    (r"\bElementTree\b", "свой разбор без модулей xml"),
    (r"\bminidom\b", "свой разбор без модулей xml"),
    (r"\bpyexpat\b", "свой разбор без модулей xml"),
    # a dot before the name means an object method: dlg.exec() is a Qt
    # dialog, not the built-in exec, and there is nothing to ban there
    (r"(?<![\w.])eval\s*\(", "разбор без eval"),
    (r"(?<![\w.])exec\s*\(", "выполнение без exec"),
    (r"\bpickle\.loads?\s*\(", "формат без pickle"),
    (r"shell\s*=\s*True", "запуск без оболочки"),
)


def _sources():
    for name in sorted(os.listdir(PKG)):
        if name.endswith(".py"):
            with open(os.path.join(PKG, name), encoding="utf-8") as f:
                yield name, f.read()


def _code_only(text):
    """Without comment lines: there the constructs are mentioned on
    purpose, to explain the ban."""
    return "\n".join(ln for ln in text.splitlines()
                     if not ln.lstrip().startswith("#"))


def test_no_unsafe_constructs():
    bad = []
    for name, text in _sources():
        code = _code_only(text)
        for pattern, hint in BANNED:
            for m in re.finditer(pattern, code):
                line = code[:m.start()].count("\n") + 1
                bad.append("%s:%d %s -> %s"
                           % (name, line, m.group(0).strip(), hint))
    assert not bad, "сканер каталога это заблокирует:\n  " + "\n  ".join(bad)


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
