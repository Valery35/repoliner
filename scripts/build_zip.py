# -*- coding: utf-8 -*-
"""Сборка архивов Repoliner.

Запуск из корня репозитория:

    python scripts/build_zip.py

Кладёт в dist/ два архива с корневой папкой repoliner:
- repoliner.zip - рабочий, с tests/;
- repoliner_upload.zip - для plugins.qgis.org, без tests/.
Кэш Python, .pytest_cache и служебные файлы в архив не идут: сканер
каталога однажды заблокировал версию из-за .pytest_cache/CACHEDIR.TAG.
В конце печатается версия, прочитанная из каждого собранного архива.
"""
import configparser
import io
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "repoliner")
DIST = os.path.join(ROOT, "dist")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", ".idea", ".vscode"}
SKIP_SUFFIX = (".pyc", ".pyo", ".orig", ".bak", ".tmp")
SKIP_NAMES = {".DS_Store", "Thumbs.db"}


def _files(with_tests):
    for root, dirs, files in os.walk(PKG):
        rel = os.path.relpath(root, ROOT).replace("\\", "/")
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS
                         and (with_tests or not (rel == "repoliner"
                                                 and d == "tests")))
        for f in sorted(files):
            if f in SKIP_NAMES or f.endswith(SKIP_SUFFIX):
                continue
            yield os.path.join(root, f), rel + "/" + f


def build(name, with_tests):
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, name)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for src, arc in _files(with_tests):
            z.write(src, arc)
    return out


def version_in(path):
    with zipfile.ZipFile(path) as z:
        text = z.read("repoliner/metadata.txt").decode("utf-8")
        n = len(z.namelist())
        tests = any(x.startswith("repoliner/tests/") for x in z.namelist())
    cp = configparser.ConfigParser()
    cp.read_file(io.StringIO(text))
    return cp.get("general", "version"), n, tests


def main():
    for name, with_tests in (("repoliner.zip", True),
                             ("repoliner_upload.zip", False)):
        out = build(name, with_tests)
        v, n, t = version_in(out)
        print("%-22s версия %s, файлов %d, tests/ %s"
              % (name, v, n, "есть" if t else "нет"))


if __name__ == "__main__":
    main()
