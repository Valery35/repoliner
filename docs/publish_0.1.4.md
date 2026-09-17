# Выкладка Repoliner 0.1.4

Порядок: GitHub, затем каталог plugins.qgis.org, затем анонс. Анонс
пишется после того, как версия прошла модерацию каталога.

## 1. GitHub

1. На github.com создать пустой репозиторий `Valery35/repoliner`,
   публичный, без README, лицензии и .gitignore. В папке модуля они уже
   есть, а с ними на GitHub первый пуш откажет из-за расхождения истории.
2. Папка `Dropbox\ИИ\Repoliner` уже является репозиторием git с одним
   коммитом и адресом `origin` = `https://github.com/Valery35/repoliner.git`.
   - GitHub Desktop: File - Add local repository - папка
     `Dropbox\ИИ\Repoliner` - Push origin.
   - Или в консоли из этой папки: `git push -u origin main`.
3. Проверить на странице репозитория: README виден, папка `repoliner/`
   на месте, архивов `dist/` нет.
4. Releases - Draft a new release: тег `v0.1.4`, название
   `Repoliner 0.1.4`, текст из раздела 4 ниже, приложить
   `repoliner.zip`.

## 2. Каталог plugins.qgis.org

1. Войти учётной записью OSGeo, Upload a plugin.
2. Загрузить **`repoliner_upload.zip`**, а не `repoliner.zip`. В нём
   нет тестов, сканер каталога на них ругается.
3. После загрузки версия ждёт модератора. Модерация идёт по будням.
4. Если модератор вернёт замечание, номер 0.1.4 уже занят. Исправление
   идёт как 0.1.5.

Что проверено до загрузки:
- `metadata.txt` читается строгим разбором каталога, обязательные поля
  на месте, `qgisMaximumVersion=4.99` (этого достаточно для списка
  QGIS 4 Ready),
- в архиве нет тестов, кэша и служебных файлов, есть LICENSE,
- bandit и проверка архива (`tools/audit_archive.py`) ошибок не дают,
- имя `repoliner` в каталоге не занято (по списку, который получил
  QGIS 4.0.3 17.09.2026).

## 3. После публикации

1. В менеджере модулей QGIS найти Repoliner в официальном репозитории.
   Установленная из архива 0.1.4 должна показываться как установленная,
   а не как обновление.
2. Дописать в AGENTS.md дату публикации.

## 4. Текст к выпуску

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

**Repoliner 0.1.4** - first release in the QGIS plugin catalogue.

Repoliner builds your own QGIS plugin repository from ready-made
plugin archives. Select zip archives, and the plugin writes
`plugins.xml`, from which QGIS installs and updates plugins through the
regular plugin manager: on company machines, from a shared network
folder or from your own web server.

**Connect in QGIS** adds the repository to the plugin manager. The
archive file may have any name, the plugin still installs.
QGIS 3.16 - 4.99.
