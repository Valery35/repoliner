# -*- coding: utf-8 -*-
#
# Repoliner - QGIS plugin repositories.
# © 2026 Inform++ LLC / ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
#
"""A bilingual interface (RU/EN).

A simple dictionary layer: the source strings in the code are Russian,
and under an English QGIS locale they are substituted with English ones
by the TRANSLATIONS table. If there is no translation, the source
(Russian) string is returned - the plugin stays working. The module does
not import QGIS at the top level, so the translation table can be
checked with plain Python (see tests/test_i18n.py).

The language is determined from the QGIS settings once, lazily, on the
first call of tr(). For tests and for forced switching there is
set_language().
"""

_LANG = None  # 'ru' | 'en' (None = not determined yet)


def set_language(lang):
    """Force the language ('ru'/'en'/'en_US'/...). None - reset it."""
    global _LANG
    if lang is None:
        _LANG = None
        return
    code = str(lang).strip().lower().replace("-", "_").split("_")[0]
    _LANG = "ru" if code == "ru" else "en"


def language():
    """The current language ('ru'/'en'); initialises from QGIS if needed."""
    if _LANG is None:
        init_from_qgis()
    return _LANG or "en"


def init_from_qgis():
    """Determine the interface language from the QGIS settings.

    The default is 'en'.
    """
    loc = ""
    try:
        from qgis.core import QgsApplication
        loc = QgsApplication.instance().locale() or ""
    except Exception:
        loc = ""
    if not loc:
        try:
            from qgis.PyQt.QtCore import QSettings
            s = QSettings()
            override = s.value("locale/overrideFlag", False, type=bool)
            loc = s.value("locale/userLocale", "") if override else ""
        except Exception:
            loc = ""
    set_language(loc or "en")
    return _LANG


def tr(s):
    """Translate the string s into the active language.

    RU is the source, EN comes from the table.
    """
    if _LANG is None:
        init_from_qgis()
    if _LANG == "en":
        return TRANSLATIONS.get(s, s)
    return s


def missing_keys(keys):
    """Which of the given Russian strings have no English translation.

    Handy for a coverage test: keys is the set of strings actually
    wrapped in _tr()/tr() in the code (extracted by an AST walk)."""
    return [k for k in keys if k not in TRANSLATIONS]


# --- RU -> EN translation table -------------------------------------------
# The key is the Russian string exactly as in the code, the value is its
# English translation. The core (core.py) messages about unreadable
# archives and registries are not translated.

TRANSLATIONS = {
    'Репозитории модулей…': 'Plugin repositories…',
    'Собрать реестр модулей QGIS из готовых архивов': 'Build a QGIS plugin registry from ready-made archives',
    'Окно не создано: нет Qt или QGIS.': 'The window was not created: Qt or QGIS is missing.',
    'Модуль': 'Plugin',
    'Версия': 'Version',
    'Архив': 'Archive',
    'Состояние': 'State',
    'в порядке': 'in order',
    'архива по адресу нет': 'no archive at the address',
    'архив не совпадает с реестром, перечитайте архивы': 'the archive does not match the registry, reread the archives',
    'адрес вне реестра, архив не проверяется': 'address outside the registry, the archive is not checked',
    'Repoliner - репозитории модулей': 'Repoliner - plugin repositories',
    'Новый реестр…': 'New registry…',
    'Создать пустой plugins.xml и добавить его в список': 'Create an empty plugins.xml and add it to the list',
    'Открыть реестр…': 'Open registry…',
    'Добавить в список реестр, созданный этим окном': 'Add a registry created by this window to the list',
    'Убрать из списка': 'Remove from the list',
    'Файл реестра на диске остаётся': 'The registry file stays on disk',
    'Добавить архивы…': 'Add archives…',
    'Модуль с той же папкой в архиве заменяется': 'A plugin with the same folder in the archive is replaced',
    'Удалить отмеченные': 'Delete ticked',
    'Из реестра, архивы на диске остаются': 'From the registry, the archives stay on disk',
    'Перечитать архивы': 'Reread archives',
    'Взять версии и описания из архивов заново': 'Take versions and descriptions from the archives again',
    'Сохранить': 'Save',
    'Копировать адрес': 'Copy address',
    'Адрес для Модули - Управление - Настройки - Добавить': 'Address for Plugins - Manage - Settings - Add',
    'Закрыть': 'Close',
    'Новый реестр': 'New registry',
    'Открыть реестр': 'Open registry',
    'Архивы модулей': 'Plugin archives',
    'Архивы zip (*.zip)': 'Zip archives (*.zip)',
    'Адрес скопирован: %s': 'Address copied: %s',
    'Создан пустой реестр %s': 'Empty registry created: %s',
    'Репозитории модулей': 'Plugin repositories',
    'Реестр открыт, модулей %d': 'Registry opened, plugins: %d',
    'Реестр убран из списка, файл остался: %s': 'Registry removed from the list, the file stays: %s',
    'Добавлено модулей %d, заменено %d': 'Plugins added: %d, replaced: %d',
    'Отметьте модули, которые надо удалить из реестра.': 'Tick the plugins to delete from the registry.',
    'Удалено модулей %d. Реестр не сохранён.': 'Plugins deleted: %d. The registry is not saved.',
    'Обновлено модулей %d': 'Plugins updated: %d',
    'Сохранено: %s': 'Saved: %s',
    'Сохраните реестр, иначе QGIS прочитает прежний файл.': 'Save the registry, otherwise QGIS reads the previous file.',
    'экспериментальный': 'experimental',
    'Выберите реестр в списке.': 'Select a registry in the list.',
    'В реестре есть несохранённые изменения. Убрать его из списка без сохранения?': 'The registry has unsaved changes. Remove it from the list without saving?',
    'QGIS %s модуль не покажет': 'QGIS %s will not show the plugin',
    'имя модуля есть ещё в %d реестрах, QGIS сольёт записи': 'the plugin name is also in %d other registries, QGIS merges the entries',
    'Реестр не читается: %s': 'The registry cannot be read: %s',
    'Реестр не создан: %s': 'Registry not created: %s',
    'Не прочитаны': 'Not read',
    'Реестр не сохранён: %s': 'Registry not saved: %s',
    'не читается: %s': 'cannot be read: %s',
    'модулей %d': 'plugins: %d',
    'Закрыть без сохранения?': 'Close without saving?',
    'Несохранённые изменения в реестрах': 'Unsaved changes in the registries',
    'Подключить в QGIS': 'Connect in QGIS',
    'Добавить реестр в менеджер модулей QGIS': 'Add the registry to the QGIS plugin manager',
    'Адрес сервера…': 'Server address…',
    'Для реестра, который раздаёт веб-сервер. Пусто - адреса файлов на диске': 'For a registry served by a web server. Empty - addresses of files on disk',
    'Сначала сохраните реестр.': 'Save the registry first.',
    'Реестр уже подключён в QGIS под именем «%s».': 'The registry is already connected in QGIS as “%s”.',
    'Реестр подключён в QGIS под именем «%s».': 'The registry is connected in QGIS as “%s”.',
    'Адрес сервера': 'Server address',
    'Адрес, по которому веб-сервер раздаёт папку реестра.\nПусто - адреса файлов на диске (file:///).': 'The address at which a web server serves the registry folder.\nEmpty - addresses of files on disk (file:///).',
    'Адрес не изменён: %s': 'Address not changed: %s',
    'Адреса архивов переписаны. Реестр не сохранён.': 'Archive addresses rewritten. The registry is not saved.',
    'есть в «%s» (%s), QGIS может показать ту версию': 'also in “%s” (%s), QGIS may show that version',
}


def error_text(exc):
    """Text of a core error (core.RepoError) in the active language.

    The core raises English templates and keeps their values, so the
    message can be rendered in Russian without a second set of strings
    in the core.
    """
    template = getattr(exc, "template", None)
    if template is None:
        return str(exc)
    if _LANG is None:
        init_from_qgis()
    text = MESSAGES.get(template, template) if _LANG == "ru" else template
    # a nested error (the XML parser inside a registry error) is
    # rendered in the same language
    values = tuple(error_text(v) if hasattr(v, "template") else v
                   for v in getattr(exc, "values", ()))
    try:
        return text % values if values else text
    except (TypeError, ValueError):
        return str(exc)


def missing_messages(templates):
    """Core templates that have no Russian text."""
    return [t for t in templates if t not in MESSAGES]


# --- Core messages EN -> RU ----------------------------------------------
# The core (core.py) speaks English. These are the same messages in
# Russian, keyed by the template exactly as the core raises it.

MESSAGES = {
    'The server address must start with http:// or https://, got %s': 'Адрес сервера должен начинаться с http:// или https://, получено %s',
    'The server address contains a space: %s': 'В адресе сервера есть пробел: %s',
    'Archive not found: %s': 'Архив не найден: %s',
    'metadata.txt has no [general] section: %s': 'В metadata.txt нет раздела [general]: %s',
    'metadata.txt has no qgisMinimumVersion: %s': 'В metadata.txt нет qgisMinimumVersion: %s',
    'The registry file is larger than 5 MB': 'Файл реестра больше 5 МБ',
    'The root element is “%s” and plugins was expected': 'Корневой элемент «%s», а ожидался plugins',
    'The registry was not created by Repoliner. Only registries marked generator="%s" are opened': 'Реестр создан не модулем Repoliner. Открываются только реестры с меткой generator="%s"',
    'The registry file is larger than 5 MB: %s': 'Файл реестра больше 5 МБ: %s',
    'The registry file is not text: %s': 'Файл реестра не текстовый: %s',
    'The file cannot be read as a zip: %s (%s)': 'Файл не читается как zip: %s (%s)',
    'The archive holds no metadata.txt in a plugin folder: %s': 'В архиве нет metadata.txt в папке модуля: %s',
    'The archive holds several folders with metadata.txt: %s': 'В архиве несколько папок с metadata.txt: %s',
    'metadata.txt is larger than 1 MB: %s': 'metadata.txt больше 1 МБ: %s',
    'metadata.txt was not parsed: %s (%s)': 'metadata.txt не разобран: %s (%s)',
    'metadata.txt has no %s field: %s': 'В metadata.txt нет поля %s: %s',
    'The server address is set and the registry file is not': 'Адрес сервера задан, а файл реестра нет',
    'The archive lies outside the registry folder and is not reachable by the server address: %s': 'Архив лежит вне папки реестра и по адресу сервера недоступен: %s',
    'No registry file is set': 'Не задан файл реестра',
    'The registry file was not parsed: %s': 'Файл реестра не разобран: %s',
    'The registry file is broken: %s': 'Файл реестра испорчен: %s',
    'Plugin “%s” has neither file_name nor download_url': 'У модуля «%s» нет ни file_name, ни download_url',
    'The address of plugin “%s” is neither file:/// nor the server address of the registry: %s': 'Адрес модуля «%s» это не file:/// и не адрес сервера реестра: %s',

# --- Messages of the XML parser (xmlparse.py) ---------------------------
    'The file breaks off inside an XML comment': 'Файл оборван внутри комментария XML',
    'The file breaks off inside an XML declaration': 'Файл оборван внутри объявления XML',
    'The file breaks off inside CDATA': 'Файл оборван внутри CDATA',
    'The file declares XML entities. Such files are not read. Entity expansion is a known way to inflate parsing until the machine gives up': 'В файле объявлены сущности XML. Такие файлы не читаются, раскрытие сущностей это известный способ раздуть разбор до отказа машины',
    'The file breaks off inside an XML tag': 'Файл оборван внутри тега XML',
    'Extra closing XML tag: %s': 'Лишний закрывающий тег XML: %s',
    'An XML tag is closed under another name, opened %s, closed %s': 'Тег XML закрыт не тем именем, открыт %s, закрыт %s',
    'Empty XML tag name': 'Пустое имя тега XML',
    'The file holds more than one root element': 'В файле больше одного корневого элемента',
    'XML nesting is too deep': 'Слишком глубокая вложенность XML',
    'The XML file breaks off, tag %s is not closed': 'Файл XML оборван, тег %s не закрыт',
    'The file was not parsed as XML, it has no root element': 'Файл не разобран как XML, корневого элемента нет',
}
