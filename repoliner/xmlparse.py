# -*- coding: utf-8 -*-
#
# Repoliner - QGIS plugin repositories.
# © 2026 Inform++ LLC / ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
"""XML parsing done by our own means.

The xml modules of the standard library are not taken into the plugin.
The scanner of the plugins.qgis.org repository blocks them, because the
standard parser gives in to bloated entities and external references,
and defusedxml is not part of the QGIS distribution.

The parser is deliberately limited. It expands only the five built-in
entities and numeric references, and a declaration of custom entities is
rejected with a refusal. The namespace prefix of a tag name is stripped.

The code is carried over from the Isoliner plugin (landxml.py) with no
change of behaviour. The guard of these bans is
tests/test_scanner_rules.py.
"""


class XmlError(Exception):
    """Same shape as core.RepoError: the message is a template plus its
    values, so i18n can show it in another language."""

    def __init__(self, template, *values):
        self.template = template
        self.values = values
        Exception.__init__(self, template % values if values else template)


    """The text was not parsed as XML."""


_ENT = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}
_MAX_DEPTH = 100


class _El(object):
    """A tree element: name, attributes, text, children."""

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
            # a foreign entity is not expanded: nothing to expand it
            # with and no reason to
            out.append(s[j:k + 1])
        i = k + 1
    return "".join(out)


def _attrs(chunk):
    """Attributes from the tail of an opening tag."""
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
    """A tree from text. Refusal on entity declarations and on a break."""
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
                raise XmlError("The file breaks off inside an XML comment")
            i += 3
            continue
        if text.startswith("<?", lt):
            i = text.find("?>", lt)
            if i < 0:
                raise XmlError("The file breaks off inside an XML declaration")
            i += 2
            continue
        if text.startswith("<![CDATA[", lt):
            end = text.find("]]>", lt)
            if end < 0:
                raise XmlError("The file breaks off inside CDATA")
            if stack:
                stack[-1].text += text[lt + 9:end]
            i = end + 3
            continue
        if text.startswith("<!", lt):
            head = text[lt:lt + 200].upper()
            if "ENTITY" in head or "DOCTYPE" in head:
                raise XmlError(
                    "The file declares XML entities. Such files are not "
                    "read. Entity expansion is a known way to inflate "
                    "parsing until the machine gives up")
            i = text.find(">", lt)
            if i < 0:
                raise XmlError("The file breaks off inside an XML declaration")
            i += 1
            continue
        gt = text.find(">", lt)
        if gt < 0:
            raise XmlError("The file breaks off inside an XML tag")
        body = text[lt + 1:gt]
        if body.startswith("/"):
            name = body[1:].strip().split(":")[-1]
            if not stack:
                raise XmlError("Extra closing XML tag: %s", name)
            el = stack.pop()
            if el.tag != name:
                raise XmlError("An XML tag is closed under another name, "
                               "opened %s, closed %s", el.tag, name)
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
            raise XmlError("Empty XML tag name")
        el = _El(name, _attrs(body[sp:]))
        if stack:
            stack[-1].children.append(el)
        elif root is None:
            root = el
        else:
            raise XmlError("The file holds more than one root element")
        if not selfclose:
            stack.append(el)
            if len(stack) > _MAX_DEPTH:
                raise XmlError("XML nesting is too deep")
        i = gt + 1
    if stack:
        raise XmlError("The XML file breaks off, tag %s is not closed",
                       stack[-1].tag)
    if root is None:
        raise XmlError("The file was not parsed as XML, it has no root "
                       "element")
    return root
