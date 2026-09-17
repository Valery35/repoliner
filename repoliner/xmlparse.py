# -*- coding: utf-8 -*-
#
# Repoliner - репозитории модулей QGIS.
# © 2026 ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
"""Разбор XML своими силами.

Модули xml из стандартной библиотеки в модуль не берутся. Сканер каталога
plugins.qgis.org блокирует их, потому что штатный разборщик поддаётся
раздутым сущностям и внешним ссылкам, а defusedxml в поставке QGIS нет.

Разборщик намеренно ограничен. Он раскрывает только пять встроенных
сущностей и числовые ссылки, а объявление своих сущностей отвергает
отказом. Приставка пространства имён у имени тега снимается.

Код перенесён из модуля Isoliner (landxml.py) без изменения поведения.
Сторож запретов - tests/test_scanner_rules.py.
"""


class XmlError(Exception):
    """Текст не разобран как XML."""


_ENT = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}
_MAX_DEPTH = 100


class _El(object):
    """Элемент дерева: имя, атрибуты, текст, дети."""

    __slots__ = ("tag", "attrib", "text", "children")

    def __init__(self, tag, attrib):
        self.tag = tag
        self.attrib = attrib
        self.text = ""
        self.children = []

    def __iter__(self):
        return iter(self.children)

    def get(self, key, default=None):
        return self.attrib.get(key, default)


def _unescape(s):
    if "&" not in s:
        return s
    out, i = [], 0
    while True:
        j = s.find("&", i)
        if j < 0:
            out.append(s[i:])
            break
        out.append(s[i:j])
        k = s.find(";", j + 1, j + 12)
        if k < 0:
            out.append("&")
            i = j + 1
            continue
        name = s[j + 1:k]
        if name in _ENT:
            out.append(_ENT[name])
        elif name.startswith("#"):
            try:
                code = (int(name[2:], 16) if name[1:2].lower() == "x"
                        else int(name[1:]))
                out.append(chr(code))
            except (ValueError, OverflowError):
                out.append(s[j:k + 1])
        else:
            # чужая сущность не раскрывается: раскрывать нечем и незачем
            out.append(s[j:k + 1])
        i = k + 1
    return "".join(out)


def _attrs(chunk):
    """Атрибуты из хвоста открывающего тега."""
    out, i, n = {}, 0, len(chunk)
    while i < n:
        while i < n and chunk[i] in " \t\r\n":
            i += 1
        j = i
        while j < n and chunk[j] not in " \t\r\n=/>":
            j += 1
        if j == i:
            break
        name = chunk[i:j]
        i = j
        while i < n and chunk[i] in " \t\r\n":
            i += 1
        if i >= n or chunk[i] != "=":
            out[name] = ""
            continue
        i += 1
        while i < n and chunk[i] in " \t\r\n":
            i += 1
        if i < n and chunk[i] in "\"'":
            q = chunk[i]
            k = chunk.find(q, i + 1)
            if k < 0:
                break
            out[name] = _unescape(chunk[i + 1:k])
            i = k + 1
        else:
            k = i
            while k < n and chunk[k] not in " \t\r\n/>":
                k += 1
            out[name] = _unescape(chunk[i:k])
            i = k
    return out


def parse(text):
    """Дерево из текста. Отказ при объявлении сущностей и при обрыве."""
    root, stack, i, n = None, [], 0, len(text)
    while True:
        lt = text.find("<", i)
        if lt < 0:
            break
        if stack and lt > i:
            stack[-1].text += _unescape(text[i:lt])
        if text.startswith("<!--", lt):
            i = text.find("-->", lt)
            if i < 0:
                raise XmlError("Файл оборван внутри комментария XML")
            i += 3
            continue
        if text.startswith("<?", lt):
            i = text.find("?>", lt)
            if i < 0:
                raise XmlError("Файл оборван внутри объявления XML")
            i += 2
            continue
        if text.startswith("<![CDATA[", lt):
            end = text.find("]]>", lt)
            if end < 0:
                raise XmlError("Файл оборван внутри CDATA")
            if stack:
                stack[-1].text += text[lt + 9:end]
            i = end + 3
            continue
        if text.startswith("<!", lt):
            head = text[lt:lt + 200].upper()
            if "ENTITY" in head or "DOCTYPE" in head:
                raise XmlError(
                    "В файле объявлены сущности XML. Такие файлы не "
                    "читаются: раскрытие сущностей это известный способ "
                    "раздуть разбор до отказа машины")
            i = text.find(">", lt)
            if i < 0:
                raise XmlError("Файл оборван внутри объявления XML")
            i += 1
            continue
        gt = text.find(">", lt)
        if gt < 0:
            raise XmlError("Файл оборван внутри тега XML")
        body = text[lt + 1:gt]
        if body.startswith("/"):
            name = body[1:].strip().split(":")[-1]
            if not stack:
                raise XmlError("Лишний закрывающий тег XML: %s" % name)
            el = stack.pop()
            if el.tag != name:
                raise XmlError(
                    "Тег XML закрыт не тем именем: открыт %s, закрыт %s"
                    % (el.tag, name))
            i = gt + 1
            continue
        selfclose = body.endswith("/")
        if selfclose:
            body = body[:-1]
        sp = 0
        while sp < len(body) and body[sp] not in " \t\r\n":
            sp += 1
        name = body[:sp].strip().split(":")[-1]
        if not name:
            raise XmlError("Пустое имя тега XML")
        el = _El(name, _attrs(body[sp:]))
        if stack:
            stack[-1].children.append(el)
        elif root is None:
            root = el
        else:
            raise XmlError("В файле больше одного корневого элемента")
        if not selfclose:
            stack.append(el)
            if len(stack) > _MAX_DEPTH:
                raise XmlError("Слишком глубокая вложенность XML")
        i = gt + 1
    if stack:
        raise XmlError(
            "Файл XML оборван: тег %s не закрыт" % stack[-1].tag)
    if root is None:
        raise XmlError("Файл не разобран как XML: корневого элемента нет")
    return root
