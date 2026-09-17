# Publishing Repoliner 0.1.4

Order: GitHub, then the plugins.qgis.org catalog, then the
announcement. The announcement is written after the version has passed
catalog moderation.

## 1. GitHub

The folder `Dropbox\ИИ\Repoliner` is ready for publishing, but it is
not a git repository yet. Git is not installed on this machine, so use
GitHub Desktop.

1. GitHub Desktop: File - Add local repository - the folder
   `Dropbox\ИИ\Repoliner`. The program will say that this is not a
   repository and will offer **create a repository** - accept. Name it
   `repoliner`, do not add README, .gitignore or a license: they are
   already in the folder.
2. Check the list of changes on the left: the archives `repoliner.zip`
   and `repoliner_upload.zip` are not there, `.gitignore` excludes
   them.
3. Summary `Repoliner 0.1.4`, Commit to main.
4. **Publish repository**: name `repoliner`, owner `Valery35`, clear
   the Keep this code private checkbox.
5. Check `https://github.com/Valery35/repoliner`: the README is
   visible, the folder `repoliner/` is in place.
6. On GitHub: Releases - Draft a new release, tag `v0.1.4`, title
   `Repoliner 0.1.4`, text from section 4 below, attach
   `repoliner.zip`.

## 2. The plugins.qgis.org catalog

1. Sign in with the OSGeo account, Upload a plugin.
2. Upload **`repoliner_upload.zip`**, not `repoliner.zip`. It has no
   tests, the catalog scanner complains about them.
3. After the upload the version waits for a moderator. Moderation runs
   on weekdays.
4. If the moderator returns a remark, the number 0.1.4 is already
   taken. The fix goes out as 0.1.5.

What was checked before the upload:
- `metadata.txt` is read by the strict parser of the catalog, the
  required fields are in place, `qgisMaximumVersion=4.99` (this is
  enough for the QGIS 4 Ready list),
- the archive has no tests, no cache and no service files, LICENSE is
  present,
- bandit and the archive check (`tools/audit_archive.py`) report no
  errors,
- the name `repoliner` is not taken in the catalog (by the list that
  QGIS 4.0.3 received on 17.09.2026).

## 3. After publication

1. In the QGIS plugin manager find Repoliner in the official
   repository. The 0.1.4 installed from the archive must be shown as
   installed, not as an update.
2. Add the publication date to AGENTS.md.

## 4. Release text

### Russian

**Repoliner 0.1.4** - первая версия в каталоге модулей QGIS.

Repoliner собирает собственный репозиторий модулей QGIS из готовых
архивов. Выбираются zip-архивы, и модуль записывает `plugins.xml`, из
которого QGIS ставит и обновляет модули через обычный менеджер модулей.
Это нужно там, где модули ставятся не из интернета, например на машинах
предприятия, из общей сетевой папки или со своего веб-сервера.

Что видно в окне:
- несколько репозиториев, у каждого свой набор модулей,
- у каждого модуля - на месте ли архив, совпадает ли версия и покажет
  ли его QGIS этой версии,
- если модуль с тем же именем пришёл из официального каталога, какая
  там версия.

Кнопка **Подключить в QGIS** добавляет репозиторий в менеджер модулей.
Архив может называться как угодно, модуль всё равно установится.

Установка: Модули - Управление и установка модулей - найти Repoliner.
QGIS 3.16 - 4.99.

### English

**Repoliner 0.1.4** - first release in the QGIS plugin catalogue.

Repoliner builds your own QGIS plugin repository from ready-made
plugin archives. Select zip archives, and the plugin writes
`plugins.xml`, from which QGIS installs and updates plugins through the
regular plugin manager: on company machines, from a shared network
folder or from your own web server.

**Connect in QGIS** adds the repository to the plugin manager. The
archive file may have any name, the plugin still installs.
QGIS 3.16 - 4.99.
