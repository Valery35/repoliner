# -*- coding: utf-8 -*-
"""Check a QGIS plugin archive before publishing it to a repository.

    python tools/audit_archive.py archive.zip [archive.zip ...]

It looks at what has already blocked or broken Inform++ plugin
releases: metadata.txt fields, the QGIS version range, junk inside the
archive, constructs the plugin repository scanner blocks, and places
that will not survive Qt6 (QGIS 4). The Qt6 findings are heuristic:
they are a list of places to review, not a verdict.
"""
import configparser
import io
import re
import tokenize
import sys
import zipfile

REQUIRED = ("name", "qgisMinimumVersion", "description", "about",
            "version", "author", "email", "repository")
RECOMMENDED = ("tracker", "homepage", "tags", "icon", "qgisMaximumVersion")
JUNK = (r"(^|/)__pycache__/", r"\.py[co]$", r"(^|/)\.pytest_cache/",
        r"(^|/)\.git/", r"(^|/)\.DS_Store$", r"(^|/)Thumbs\.db$",
        r"\.(orig|bak|swp|tmp)$", r"(^|/)\.idea/", r"(^|/)\.vscode/")
SCANNER = (
    (r"\bimport\s+xml\b|\bfrom\s+xml[\s.]|\bElementTree\b|\bminidom\b"
     r"|\bpyexpat\b", "xml modules (repository scanner blocks them)"),
    (r"(?<![\w.])eval\s*\(", "eval"),
    (r"(?<![\w.])exec\s*\(", "exec"),
    (r"\bpickle\.loads?\s*\(", "pickle"),
    (r"shell\s*=\s*True", "shell=True"),
    (r"except(\s+Exception)?\s*:[ \t]*\n\s*(pass|continue)\b",
     "bare except with pass/continue (bandit B110/B112)"),
)
QT6 = (
    (r"\.exec_\s*\(", "exec_() - Qt6 has exec() only"),
    (r"QVariant\s*\(\s*\)|QVariant\.(Null|Invalid)\b",
     "empty QVariant - Qt6 needs NULL from qgis.core"),
    (r"\bfrom\s+PyQt5\b|\bimport\s+PyQt5\b",
     "direct PyQt5 import - use qgis.PyQt"),
    (r"from\s+qgis\.PyQt\.QtWidgets\s+import\s+[^\n]*\bQAction\b",
     "QAction from QtWidgets - in Qt6 it lives in QtGui"),
    (r"\bQt\.(AlignLeft|AlignRight|AlignCenter|AlignTop|AlignBottom|"
     r"UserRole|DisplayRole|Checked|Unchecked|WaitCursor|ItemIsEnabled|"
     r"ItemIsSelectable|ItemIsEditable|ItemIsUserCheckable|Horizontal|"
     r"Vertical|NonModal|ApplicationModal|DashLine|SolidLine|NoPen|"
     r"NoBrush|KeepAspectRatio|SmoothTransformation|RightDockWidgetArea|"
     r"LeftDockWidgetArea|CustomContextMenu|Key_\w+|ControlModifier|"
     r"ShiftModifier|LeftButton|RightButton)\b",
     "flat Qt enum - Qt6 needs the full name"),
    (r"\bQ(MessageBox|DialogButtonBox|FileDialog|HeaderView|"
     r"AbstractItemView|SizePolicy|Frame)\.(Yes|No|Ok|Cancel|Save|"
     r"Discard|Close|Stretch|ResizeToContents|Interactive|"
     r"SelectRows|SingleSelection|ExtendedSelection|NoEditTriggers|"
     r"Expanding|Preferred|Fixed|Minimum|HLine|VLine|Sunken|"
     r"AcceptRole|RejectRole|ActionRole|Warning|Information|Question|"
     r"Critical)\b",
     "flat widget enum - Qt6 needs the full name"),
    (r"QRegExp\b", "QRegExp - gone in Qt6, use QRegularExpression"),
    (r"\bQDesktopWidget\b", "QDesktopWidget - gone in Qt6"),
)


def _code(src):
    """Text without literals and comments, line numbers are kept.

    Returns (code, set of line numbers marked with nosec)."""
    lines = src.splitlines(True)
    out = [list(l) for l in lines]
    nosec = set()
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return src, nosec
    for t in toks:
        if t.type not in (tokenize.STRING, tokenize.COMMENT):
            continue
        if t.type == tokenize.COMMENT and "nosec" in t.string:
            nosec.add(t.start[0])
        (r0, c0), (r1, c1) = t.start, t.end
        for r in range(r0, r1 + 1):
            row = out[r - 1]
            a = c0 if r == r0 else 0
            b = c1 if r == r1 else len(row)
            for i in range(a, min(b, len(row))):
                if row[i] != "\n":
                    row[i] = " "
    return "".join("".join(r) for r in out), nosec


def _lines(text, pattern, nosec=()):
    out = []
    for m in re.finditer(pattern, text):
        line = text.count("\n", 0, m.start()) + 1
        last = text.count("\n", 0, m.end()) + 1
        if not any(k in nosec for k in range(line, last + 1)):
            out.append(line)
    return out


def audit(path):
    rep = {"path": path, "errors": [], "warnings": [], "qt6": [],
           "info": []}
    z = zipfile.ZipFile(path)
    names = z.namelist()
    roots = sorted({n.split("/")[0] for n in names if "/" in n})
    rep["info"].append("root folders: %s, files %d" % (roots, len(names)))
    if len(roots) != 1:
        rep["errors"].append("the archive root must hold one plugin folder")
    root = roots[0] if roots else ""
    base = path.replace("\\", "/").rsplit("/", 1)[-1].partition(".")[0]
    if base != root:
        rep["warnings"].append(
            "file name \"%s\" does not match the folder \"%s\". Install "
            "from ZIP and Repoliner 0.1.1+ tolerate this, an old style "
            "repository does not" % (base, root))
    meta = root + "/metadata.txt"
    if meta not in names:
        rep["errors"].append("%s is missing" % meta)
        return rep
    text = z.read(meta).decode("utf-8-sig", "replace")
    cp = configparser.ConfigParser(
        interpolation=configparser.BasicInterpolation())
    cp.optionxform = str
    try:
        cp.read_string(text)
        g = dict(cp.items("general"))
    except (configparser.Error, ValueError) as e:
        rep["errors"].append("metadata.txt fails the strict parsing the "
                             "repository does: %s" % str(e).splitlines()[0])
        raw = configparser.RawConfigParser()
        raw.optionxform = str
        raw.read_string(text)
        g = dict(raw.items("general"))
    for k in REQUIRED:
        if not g.get(k, "").strip():
            rep["errors"].append("metadata.txt has no required field %s"
                                 % k)
    for k in RECOMMENDED:
        if not g.get(k, "").strip():
            rep["warnings"].append("metadata.txt has no field %s" % k)
    rep["info"].append("version %s, QGIS %s - %s, experimental=%s" % (
        g.get("version"), g.get("qgisMinimumVersion"),
        g.get("qgisMaximumVersion", "(not set)"), g.get("experimental")))
    qmax = g.get("qgisMaximumVersion", "").strip()
    qmin = g.get("qgisMinimumVersion", "").strip()
    top = qmax or (qmin[:1] + ".99")
    if top and int(top.split(".")[0] or 0) < 4:
        rep["errors"].append("QGIS upper bound %s: in QGIS 4 the plugin is "
                             "hidden, both in the repository and locally"
                             % top)
    if g.get("experimental", "").strip().lower() == "true":
        rep["warnings"].append("experimental=True: the plugin shows up only "
                               "with experimental plugins enabled")
    for k in ("repository", "tracker", "homepage"):
        v = g.get(k, "")
        if v and "github.com" not in v and k != "homepage":
            rep["warnings"].append("%s=%s - the repository expects the code "
                                   "and tracker address" % (k, v))
    if "changelog" not in g:
        rep["warnings"].append("no changelog in metadata.txt")
    icon = g.get("icon", "").strip()
    if icon and root + "/" + icon not in names:
        rep["errors"].append("icon %s is not in the archive" % icon)
    if root + "/LICENSE" not in names and not any(
            n.lower().startswith((root + "/license").lower())
            for n in names):
        rep["warnings"].append("no LICENSE file (the repository needs one)")
    junk = sorted({n for n in names for p in JUNK if re.search(p, n)})
    if junk:
        rep["errors"].append("junk in the archive (%d): %s" % (
            len(junk), ", ".join(junk[:5]) + (" …" if len(junk) > 5 else "")))
    tests = [n for n in names if re.match(r"[^/]+/tests?/", n)]
    if tests:
        rep["warnings"].append("tests folder in the archive (%d files): it "
                               "does not belong in the upload build"
                               % len(tests))
    for n in names:
        if not n.endswith(".py") or "/tests/" in n or "/test/" in n:
            continue
        src = z.read(n).decode("utf-8", "replace")
        code, nosec = _code(src)
        qaction_fallback = "QtGui import QAction" in src
        for pat, why in SCANNER:
            ls = _lines(code, pat, nosec)
            if ls:
                rep["errors"].append("%s: %s, lines %s" % (
                    n, why, ls[:6]))
        for pat, why in QT6:
            if "QAction" in why and qaction_fallback:
                continue
            ls = _lines(code, pat)
            if ls:
                rep["qt6"].append("%s: %s, places %d (lines %s)" % (
                    n, why, len(ls), ls[:6]))
    return rep


def main(paths):
    for p in paths:
        r = audit(p)
        print("=" * 70)
        print(r["path"])
        for key, title in (("info", "info"), ("errors", "errors"),
                           ("warnings", "warnings"),
                           ("qt6", "Qt6, review")):
            if r[key]:
                print("  %s:" % title)
                for x in r[key]:
                    print("    - " + x)


if __name__ == "__main__":
    main(sys.argv[1:])
