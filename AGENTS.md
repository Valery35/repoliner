# AGENTS.md - the working context of Repoliner

This file is read first at the start of any new chat. The only source
of truth is this repository, not the correspondence. If something has
changed in the code or in the process, the edit goes here.

## What this is

The QGIS plugin Repoliner. It builds a repository of QGIS plugins
(`plugins.xml`) from ready zip archives of plugins and keeps a set of
such repositories. Developed by ООО «Информ++», Perm. Claude writes
the code, Valery sets the tasks, checks on live data and makes the
decisions.

The plugin was separated from Isoliner (September 2026). The task came
out of the Isoliner nightly channel (`nightly/plugins.xml` in the
Isoliner repository), but nothing from this plugin goes into Isoliner,
and there is no dependency on it.

Compatibility QGIS 3.16 - 4.99, Qt5 and Qt6. Pure Python, without
third-party libraries. The version and the changelog are in
`repoliner/metadata.txt`.

## Valery's decisions (September 2026)

- **The repository is English** (0.1.5). Comments, docstrings, documents
  and the messages of the core and of the XML parser are written in
  English. Russian stays in two places - `README_ru.md` and the strings
  of the user interface, which are the keys of the `tr()` dictionary in
  `i18n.py`. The core raises an English template and keeps its values,
  and `i18n.error_text()` renders it in the language of QGIS from the
  `MESSAGES` table. A new core message without a Russian text is caught
  by `tests/test_i18n.py`.
- **Repository** `https://github.com/Valery35/repoliner`, `homepage`
  and `tracker` (`/issues`) lead there as well. The first upload to the
  catalog is 0.1.4, without the "experimental" flag. On 17.09.2026 the
  code was published on GitHub, with a release tagged 0.1.4 and an
  archive there too. On 18.09.2026 the catalog approved version 0.1.6,
  plugin_id 6346, the page is
  `https://plugins.qgis.org/plugins/repoliner/`. The catalog renames
  the archive to `repoliner.0.1.6.zip`, so the plugin name there is
  `repoliner` and it merges with an entry of the same name in an own
  registry. Version 0.1.7 has not been uploaded yet.
- **A window on a panel**, not a Processing tool. A tree "registry -
  plugins" with check marks.
- **The list of registries is kept in the QGIS settings**, key
  `Repoliner/repositories`, paths one per line. The registry itself is
  described by its own `plugins.xml` and nowhere else.
- **Archives are not copied.** Archives are prepared in advance,
  `download_url` leads to the place of the archive (`file:///`). Moving
  an archive breaks the installation, so the window shows the state of
  the archive for every plugin.
- **The user chooses the archive, with any file name.** Repoliner does
  not reject the archive, and it takes the plugin name in the registry
  from the folder inside the archive (0.1.1).
- **The registry is connected in QGIS by a button** (0.1.2). It writes
  `app/plugin_repositories/<name>/url` and `enabled`, then calls
  `pyplugin_installer.instance().reloadAndExportData()`. The reason - in
  a live run a folder path was pasted into the address field, and QGIS
  answered "Unknown protocol "c"". The window does not disable the
  official repository, that is the decision of the machine
  administrator.
- **The server address** (0.1.2) is kept as the attribute `base_url` on
  the root of `plugins.xml`, QGIS does not read it. The archive address
  is the server address plus the path from the registry folder. An
  archive outside the registry folder is not accepted when an address is
  set, and a change of the address is rolled back as a whole.
- **The registry page** (0.1.7) is a plain `index.html` written next to
  `plugins.xml` on every save. A stylesheet for the XML itself
  (`xml-stylesheet` with XSLT, as the official catalog does) was
  considered and dropped: Chrome removes XSLT on 17.11.2026, Firefox and
  WebKit announced the same, and a local `file:///` registry does not get
  its stylesheet applied anyway.
- **Only own registries are opened**, with the mark
  `<plugins generator="Repoliner">`. A foreign file, including the
  official catalog, is not read. The core has `own_only=False`, from the
  window it is not called.

## How QGIS reads a registry (verified against the 3.40 and master sources)

`python/pyplugin_installer/installer_data.py`, `xmlDownloaded`.

- The plugin is determined by the **name up to the first dot** from
  `file_name`, and without it from `download_url`.
- After the download the installer
  (`qgsplugininstallerinstallingdialog.py`, `requestFinished`) copies
  from the archive **only the folder with this name**. If there is no
  such folder - "Could not store plugin to the plugin directory".
  Therefore `file_name` is written as "the plugin folder in the
  archive".zip, and `download_url` leads to a file with any name. Caught
  on 0.1.0 by a live run - `topoliner_upload.zip` with the folder
  `topoliner` did not install. The consequence for Isoliner - a nightly
  build with the folder `grid_isolines` is inevitably called
  `grid_isolines` in the registry and merges with the catalog.
- A coincidence of names in two repositories merges the entries into
  one. The window warns about a coincidence between own registries.
- `download_url` is taken **as is** and is **not resolved** relative to
  the registry address (that is done only for `icon` and only for http).
  Hence the full addresses.
- A Windows network folder - `\\server\folder\x.zip` is written as
  `file://server/folder/x.zip`. Verified on QGIS 4.0.3 through the
  administrative share `\\127.0.0.1\C$` - the registry and the archive
  are read. Qt considers `file://localhost/...` a local drive and does
  not open it, so `localhost` is replaced with `127.0.0.1`.
- A registry in a network folder works on a customer network. In
  September 2026 Valery put the plugin archives on a company share,
  built the registry there and connected it on a machine without
  internet - the plugins install and the page opens. The address in the
  QGIS settings is `file://<server>/<share>/.../plugins.xml`, with the
  server name. On such machines the official repository is better
  turned off: it is unreachable, so the manager reports an error at
  every start, and while it is reachable it overrides plugins of the
  same name from the own registry.
- http was verified on QGIS 4.0.3 with a temporary server on 127.0.0.1 -
  a registry with `?qgis=4.0` and archives of 1.2 and 5.6 MB are
  downloaded, a missing archive gives ContentNotFoundError. A full
  installation from an http registry on a live machine was not run.
- Plugins from other repositories the window takes from what the plugin
  manager has already loaded (`installer_data.plugins.repoCache`), it
  does not touch the network. Before the first opening of the manager
  there are no warnings.
- QGIS appends `?qgis=X.Y` to the registry address. For `file:///` this
  does not interfere - verified on QGIS 4.0.3, as was the download of a
  zip over `file:///` with a space in the path.
- A plugin outside the range `qgis_minimum_version` -
  `qgis_maximum_version` is not shown in the list at all. An empty
  maximum is counted as "the major digit of the minimum".99. The window
  writes "QGIS X will not show the plugin".

The table matching the fields of `metadata.txt` and `plugins.xml` is in
the header of `repoliner/core.py`, together with the list of fields that
are not carried over.

## Map of the modules (repoliner/)

| File | Role |
|---|---|
| `__init__.py` | classFactory |
| `plugin.py` | the menu item "Plugins - Repoliner" and the button on the panel |
| `core.py` | the core without QGIS and Qt - reading archives, writing and reading `plugins.xml`, the state of the archive, compatibility. Test `tests/test_core.py` |
| `xmlparse.py` | own XML parser, carried over from Isoliner (`landxml.py`). Refusal on a declaration of entities |
| `view.py` | the window, the tree and the actions. Contains no calculation logic |
| `i18n.py` | RU/EN dictionary, `tr()`, and `error_text()` for the English messages of the core and of the XML parser |
| `qt_compat.py` | Qt5/Qt6 constants |
| `tests/` | pytest, does not go into the upload archive |

Outside the package: `scripts/build_zip.py` (the build),
`tools/smoke_view.py` (a run of the window on PyQt6/PyQt5 with a stub
qgis, in a container without QGIS), `tools/audit_archive.py` (a check of
any plugin archive before the upload: metadata, the QGIS range, garbage,
the prohibitions of the catalog scanner, the places for Qt6). The report
on the Информ++ plugins from 17.09.2026 is
`docs/audit_2026-09-17.md`.

## What must not be done

- **The `xml` modules are not used.** The scanner of the
  plugins.qgis.org catalog blocks `xml.etree.ElementTree`, `minidom`,
  `pyexpat`, and `defusedxml` is not in the QGIS distribution. It was
  caught twice in Isoliner. Parsing only through `xmlparse.parse`. The
  guard is `tests/test_scanner_rules.py`.
- **`tests/` is not put into the upload archive**, `.pytest_cache` and
  `__pycache__` are not put anywhere. The secret scanner once blocked a
  version of Isoliner because of `.pytest_cache/CACHEDIR.TAG`. The build
  is only `python scripts/build_zip.py`.
- A bare `except Exception: pass|continue` is not written - the bandit
  scanner (B110/B112) blocks the upload. The check is `bandit -r
  repoliner -x repoliner/tests`.
- In `metadata.txt` there is no single `%`. The guard is
  `tests/test_metadata.py`.

## The build and the delivery

- `python scripts/build_zip.py` gives `dist/repoliner.zip` (the working
  one, with the tests) and `dist/repoliner_upload.zip` (for the catalog,
  without the tests) and prints the version from each archive.
- In the course of the work only `repoliner.zip` goes into the chat. The
  commit, the push, the archive for the catalog and the release notes
  are done once, when Valery says "release".
- **Only the last digit moves the version.** The middle one is raised by
  Valery. Every delivered build gets its own number, two different
  archives under one number are not allowed. On a bump the entry goes
  into the changelog of `metadata.txt` as the first line (the guard is
  `test_version_is_first_in_changelog`).
- Acceptance on the unpacked archive - `ast.parse` of every module,
  `configparser` with interpolation on `metadata.txt`, a full run of
  `python -m pytest -q -p no:cacheprovider repoliner/tests`,
  `QT_QPA_PLATFORM=offscreen python tools/smoke_view.py` and `... en`.

## The verifiable goal

A task is not set until a readiness criterion is named that can be
checked by a run. For new behavior the command and the expected result
are named first, then the code is written. For a defect there is first a
test that reproduces it and fails. "It should work" does not count as a
result. If a run is not possible (there is no QGIS in the container),
this is said out loud.

The live check of 0.1.0 (at Valery's) - build a registry from two
archives, "Copy address", paste it into "Plugins - Manage and Install
Plugins - Settings - Add", see both plugins in the list and install one.

## Requirements for texts

The set of rules from the AGENTS.md of Isoliner applies, and it governs
the Russian publishable texts. In short:

- a dash only as ` - `, there is no long dash, there is no semicolon, a
  colon only before a list, in ratios, addresses and names
- the sentences are short and complete, a paragraph opens with the
  thesis
- there is no colloquial vocabulary, the stop words are guarded by
  `tests/test_stopwords.py`
- «количество» where items are counted
- a statement without comparison and without evaluation
- the release notes are written for the user - first what he will see,
  then in one phrase why. There are no names of functions and files in
  them
- the voice of the company is «мы», in business documents for the
  customer there is no first person

## Open questions

- A coincidence of a plugin name with the official catalog. QGIS merges
  the entries, and the repository that loaded last wins. In a live run
  Isoliner 5.13.14 and Isoliner3D 1.3.1 from the own registry were
  overridden by 5.13.4 and 1.2.0 from the catalog. Since 0.1.2 the
  window writes about this. It can be removed only by disabling the
  official repository on the machine.
- The `generator` mark on the registry of the Isoliner nightly builds.
  The script `make_nightly.py` does not set it, so Repoliner will not
  open that registry. It is solved in Isoliner, if it is needed.
- What has to be served by a web server is a separate registry folder,
  and not the whole `Dropbox\ИИ` - there are files there that must not
  go out into the network.
