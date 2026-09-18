# Repoliner - QGIS plugin repositories

[Русская версия](README_ru.md)

We build software for the geological and surveying services of potash
mines. Repoliner builds a QGIS plugin repository from ready-made plugin
zip archives.

## What it does

- You select plugin archives. The name, version, description and the
  range of QGIS versions are taken from `metadata.txt` of each archive.
- Each plugin is written to `plugins.xml` in the QGIS plugin repository
  format. The archive address points to where the archive lies
  (`file:///`), the archives are not copied.
- The window keeps several repositories, each with its own set of
  plugins. For every plugin it shows whether the archive is in place and
  whether its version matches the registry, and whether QGIS of the
  running version will list the plugin at all.
- **Connect in QGIS** adds the registry to the QGIS plugin manager, and
  the plugins of the registry are installed from there. **Copy address**
  gives the same address for another machine.
- A registry can lie on a disk, in a shared Windows folder
  (`\\server\share`) or be served by a web server (**Server address**).
- If QGIS received a plugin with the same name from another repository,
  such as the official catalogue, the window shows that repository and
  its version.

The archive file may have any name. The plugin name in the registry is
taken from the plugin folder inside the archive, because QGIS installs
only the folder with that name.

Open the window from **Plugins - Repoliner - Plugin repositories…** or
from the Repoliner toolbar.

Compatible with QGIS 3.16 - 4.99. The interface is in English and
Russian.

## Changes

- **0.1.7** - a page `index.html` is written next to `plugins.xml`, so the registry can be viewed in a browser.

- **0.1.6** - a file that is not text, picked as a registry, gives a message instead of an error window.
- **0.1.5** - the repository is in English, the messages of the core follow the language of the QGIS interface.

- **0.1.4** - first release in the QGIS plugin catalogue, the
  experimental flag is removed.
- **0.1.3** - the warning about a plugin from another repository has no
  repeats and is not shown for the same version.
- **0.1.2** - one-button connection of a registry to QGIS, web server
  address, shared Windows folders, warning about plugins from other
  repositories.
- **0.1.1** - plugins from archives with any file name install from the
  registry.
- **0.1.0** - first version.

Developed by Inform++ LLC (www.informpp.ru). License GPL-2.0-or-later.
