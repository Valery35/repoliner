# -*- coding: utf-8 -*-
#
# Repoliner - QGIS plugin repositories.
# © 2026 Inform++ LLC / ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
#
"""Stop words of published texts.

The rule is adopted for everything that goes outside: tool help texts,
the description and the changelog in metadata.txt, styles, templates.
The check in tests/test_i18n.py looked only at the package modules and
lived under ``if __name__ == "__main__"``, so pytest did not collect it
at all, and the changelog did not get into it by the set of files
either. That is how «врёт» ended up in entry 4.85.0 and «честно» in
4.86.0.

The package tests are not included here: those are working texts for
insiders, and the rule is about published ones. The dash is looked for
only in Russian text next to Cyrillic, so as not to touch tables and
markup.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)

# Word: why it is banned
STOP_WORDS = {
    r"честн[а-яё]+": "«честный» - затычка вместо сути, писать «корректнее»",
    r"врёт|врут|врал[а-яё]*": "«врёт» - о программе так не пишем",
    r"наблюдённ[а-яё]+": "принято «наблюдаемые»",
    r"членени[а-яё]*": "принято «участки», «разбивка на участки»",
    r"\bлаг(а|у|ом|е|и|ов|ам|ами|ах)?\b": "«лаг» - писать «расстояние» (между точками пары) "
                                          "или «шаг» (параметр инструмента)",
    r"\bсофт[а-яё]*": "«софт» - писать «программа», «пакет»",
    r"\bкучк[а-яё]*": "«кучка» - разговорное, писать «группа», «набор»",
    r"\bскучн[а-яё]*": "«скучный» - оценка вместо сути",
    r"главн[а-яё]* грабл[а-яё]*": "«главные грабли» - писать «главная ошибка»",
}

# An em dash between Cyrillic words. In code the dash also occurs as a
# filler character, so we look exactly at prose.
DASH = re.compile(r"[А-Яа-яЁё][^\n]{0,40}—|—[^\n]{0,40}[А-Яа-яЁё]")


def _published_files():
    """Files that reach the user. Tests are excluded deliberately."""
    out = []
    for name in sorted(os.listdir(PKG)):
        if name.endswith(".py") or name == "metadata.txt":
            out.append(os.path.join(PKG, name))
    styles = os.path.join(PKG, "styles")
    if os.path.isdir(styles):
        for name in sorted(os.listdir(styles)):
            if name.endswith(".qml"):
                out.append(os.path.join(styles, name))
    return out


def _hits(pattern, text):
    """List of (line number, line) for every match."""
    found = []
    for m in re.finditer(pattern, text):
        line = text.count("\n", 0, m.start()) + 1
        found.append((line, text.splitlines()[line - 1].strip()[:90]))
    return found


def test_no_stop_words_in_published_texts():
    bad = []
    for path in _published_files():
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
        for pattern, why in STOP_WORDS.items():
            for line, ctx in _hits(pattern, text):
                bad.append("%s:%d [%s] %s" % (os.path.basename(path),
                                              line, why, ctx))
    assert not bad, "стоп-слова в публикуемых текстах:\n" + "\n".join(bad)


def test_no_em_dash_in_russian_prose():
    bad = []
    for path in _published_files():
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
        for line, ctx in _hits(DASH, text):
            bad.append("%s:%d %s" % (os.path.basename(path), line, ctx))
    assert not bad, "тире в русской прозе, заменить на ' - ':\n" + "\n".join(bad)


def test_metadata_changelog_is_covered():
    """A guard for the guard itself: the changelog must fall under the
    check.

    The error was not in the rule but in the coverage. If metadata.txt
    one day drops out of the list of files, the tests above will fall
    silent and notice nothing.
    """
    names = [os.path.basename(p) for p in _published_files()]
    assert "metadata.txt" in names, "metadata.txt выпал из проверки"
    with open(os.path.join(PKG, "metadata.txt"), encoding="utf-8") as fh:
        assert "changelog=" in fh.read(), "changelog не найден в metadata.txt"
