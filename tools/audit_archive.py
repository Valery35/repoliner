# -*- coding: utf-8 -*-
"""Проверка архива модуля QGIS перед выкладкой в реестр или в каталог.

    python tools/audit_archive.py архив.zip [архив.zip ...]

Смотрит то, что уже блокировало или ломало выкладку модулей Информ++:
поля metadata.txt, диапазон версий QGIS, мусор в архиве, конструкции,
которые блокирует сканер каталога, и места, которые не переживут Qt6
(QGIS 4). Находки Qt6 эвристические: это список мест для просмотра, а не
приговор.
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
     r"|\bpyexpat\b", "модули xml (сканер каталога)"),
    (r"(?<![\w.])eval\s*\(", "eval"),
    (r"(?<![\w.])exec\s*\(", "exec"),
    (r"\bpickle\.loads?\s*\(", "pickle"),
    (r"shell\s*=\s*True", "shell=True"),
    (r"except(\s+Exception)?\s*:[ \t]*\n\s*(pass|continue)\b",
     "голый except с pass/continue (bandit B110/B112)"),
)
QT6 = (
    (r"\.exec_\s*\(", "exec_() - в Qt6 только exec()"),
    (r"QVariant\s*\(\s*\)|QVariant\.(Null|Invalid)\b",
     "пустой QVariant - в Qt6 нужен NULL из qgis.core"),
    (r"\bfrom\s+PyQt5\b|\bimport\s+PyQt5\b",
     "прямой импорт PyQt5 - нужен qgis.PyQt"),
    (r"from\s+qgis\.PyQt\.QtWidgets\s+import\s+[^\n]*\bQAction\b",
     "QAction из QtWidgets - в Qt6 он в QtGui"),
    (r"\bQt\.(AlignLeft|AlignRight|AlignCenter|AlignTop|AlignBottom|"
     r"UserRole|DisplayRole|Checked|Unchecked|WaitCursor|ItemIsEnabled|"
     r"ItemIsSelectable|ItemIsEditable|ItemIsUserCheckable|Horizontal|"
     r"Vertical|NonModal|ApplicationModal|DashLine|SolidLine|NoPen|"
     r"NoBrush|KeepAspectRatio|SmoothTransformation|RightDockWidgetArea|"
     r"LeftDockWidgetArea|CustomContextMenu|Key_\w+|ControlModifier|"
     r"ShiftModifier|LeftButton|RightButton)\b",
     "плоское перечисление Qt - в Qt6 нужно полное имя"),
    (r"\bQ(MessageBox|DialogButtonBox|FileDialog|HeaderView|"
     r"AbstractItemView|SizePolicy|Frame)\.(Yes|No|Ok|Cancel|Save|"
     r"Discard|Close|Stretch|ResizeToContents|Interactive|"
     r"SelectRows|SingleSelection|ExtendedSelection|NoEditTriggers|"
     r"Expanding|Preferred|Fixed|Minimum|HLine|VLine|Sunken|"
     r"AcceptRole|RejectRole|ActionRole|Warning|Information|Question|"
     r"Critical)\b",
     "плоское перечисление виджета - в Qt6 нужно полное имя"),
    (r"QRegExp\b", "QRegExp - в Qt6 нет, нужен QRegularExpression"),
    (r"\bQDesktopWidget\b", "QDesktopWidget - в Qt6 нет"),
)


def _code(src):
    """Текст без строк и комментариев, номера строк сохраняются.

    Возвращает (код, множество строк с меткой nosec)."""
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
    rep["info"].append("папки в корне: %s, файлов %d" % (roots, len(names)))
    if len(roots) != 1:
        rep["errors"].append("в корне архива должна быть одна папка модуля")
    root = roots[0] if roots else ""
    base = path.replace("\\", "/").rsplit("/", 1)[-1].partition(".")[0]
    if base != root:
        rep["warnings"].append(
            "имя файла «%s» не совпадает с папкой «%s». Установка из ZIP и "
            "Repoliner 0.1.1+ это переносят, реестр старого образца нет"
            % (base, root))
    meta = root + "/metadata.txt"
    if meta not in names:
        rep["errors"].append("нет %s" % meta)
        return rep
    text = z.read(meta).decode("utf-8-sig", "replace")
    cp = configparser.ConfigParser(
        interpolation=configparser.BasicInterpolation())
    cp.optionxform = str
    try:
        cp.read_string(text)
        g = dict(cp.items("general"))
    except (configparser.Error, ValueError) as e:
        rep["errors"].append("metadata.txt не читается строгим разбором "
                             "каталога: %s" % str(e).splitlines()[0])
        raw = configparser.RawConfigParser()
        raw.optionxform = str
        raw.read_string(text)
        g = dict(raw.items("general"))
    for k in REQUIRED:
        if not g.get(k, "").strip():
            rep["errors"].append("в metadata.txt нет обязательного поля %s"
                                 % k)
    for k in RECOMMENDED:
        if not g.get(k, "").strip():
            rep["warnings"].append("в metadata.txt нет поля %s" % k)
    rep["info"].append("версия %s, QGIS %s - %s, experimental=%s" % (
        g.get("version"), g.get("qgisMinimumVersion"),
        g.get("qgisMaximumVersion", "(не задан)"), g.get("experimental")))
    qmax = g.get("qgisMaximumVersion", "").strip()
    qmin = g.get("qgisMinimumVersion", "").strip()
    top = qmax or (qmin[:1] + ".99")
    if top and int(top.split(".")[0] or 0) < 4:
        rep["errors"].append("верхняя граница QGIS %s: в QGIS 4 модуль не "
                             "виден ни в каталоге, ни в реестре" % top)
    if g.get("experimental", "").strip().lower() == "true":
        rep["warnings"].append("experimental=True: модуль виден только при "
                               "галке экспериментальных модулей")
    for k in ("repository", "tracker", "homepage"):
        v = g.get(k, "")
        if v and "github.com" not in v and k != "homepage":
            rep["warnings"].append("%s=%s - каталог ждёт адрес кода и "
                                   "трекера" % (k, v))
    if "changelog" not in g:
        rep["warnings"].append("нет changelog в metadata.txt")
    icon = g.get("icon", "").strip()
    if icon and root + "/" + icon not in names:
        rep["errors"].append("значок %s не найден в архиве" % icon)
    if root + "/LICENSE" not in names and not any(
            n.lower().startswith((root + "/license").lower())
            for n in names):
        rep["warnings"].append("нет файла LICENSE (каталог требует)")
    junk = sorted({n for n in names for p in JUNK if re.search(p, n)})
    if junk:
        rep["errors"].append("мусор в архиве (%d): %s" % (
            len(junk), ", ".join(junk[:5]) + (" …" if len(junk) > 5 else "")))
    tests = [n for n in names if re.match(r"[^/]+/tests?/", n)]
    if tests:
        rep["warnings"].append("папка tests в архиве (%d файлов): в "
                               "выгрузку для каталога не кладётся"
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
                rep["errors"].append("%s: %s, строки %s" % (
                    n, why, ls[:6]))
        for pat, why in QT6:
            if "QAction" in why and qaction_fallback:
                continue
            ls = _lines(code, pat)
            if ls:
                rep["qt6"].append("%s: %s, мест %d (строки %s)" % (
                    n, why, len(ls), ls[:6]))
    return rep


def main(paths):
    for p in paths:
        r = audit(p)
        print("=" * 70)
        print(r["path"])
        for key, title in (("info", "сведения"), ("errors", "ошибки"),
                           ("warnings", "замечания"),
                           ("qt6", "Qt6, посмотреть")):
            if r[key]:
                print("  %s:" % title)
                for x in r[key]:
                    print("    - " + x)


if __name__ == "__main__":
    main(sys.argv[1:])
