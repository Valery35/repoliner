# -*- coding: utf-8 -*-
#
# Repoliner - репозитории модулей QGIS.
# © 2026 ООО «Информ++» (www.informpp.ru).
# SPDX-License-Identifier: GPL-2.0-or-later
#
"""Двуязычие интерфейса (RU/EN).

Простой словарный слой: исходные строки в коде - русские, при английской
локали QGIS они подменяются на английские по таблице TRANSLATIONS. Если
перевода нет, возвращается исходная (русская) строка - модуль остаётся
рабочим. Модуль не импортирует QGIS на верхнем уровне, поэтому таблицу
переводов можно проверять обычным Python (см. tests/test_i18n.py).

Язык определяется по настройкам QGIS один раз, лениво, при первом вызове tr().
Для тестов и принудительного переключения есть set_language().
"""

_LANG = None  # 'ru' | 'en' (None = ещё не определён)


def set_language(lang):
    """Принудительно задать язык ('ru'/'en'/'en_US'/...). None - сбросить."""
    global _LANG
    if lang is None:
        _LANG = None
        return
    code = str(lang).strip().lower().replace("-", "_").split("_")[0]
    _LANG = "ru" if code == "ru" else "en"


def language():
    """Текущий язык ('ru'/'en'); инициализирует по QGIS при необходимости."""
    if _LANG is None:
        init_from_qgis()
    return _LANG or "en"


def init_from_qgis():
    """Определить язык интерфейса по настройкам QGIS. По умолчанию 'en'."""
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
    """Перевести строку s на активный язык. RU - исходник, EN - по таблице."""
    if _LANG is None:
        init_from_qgis()
    if _LANG == "en":
        return TRANSLATIONS.get(s, s)
    return s


def missing_keys(keys):
    """Какие из переданных русских строк не имеют английского перевода.

    Удобно для теста покрытия: keys - множество строк, реально обёрнутых в
    _tr()/tr() в коде (извлекается AST-обходом)."""
    return [k for k in keys if k not in TRANSLATIONS]


# --- Таблица переводов RU -> EN -------------------------------------------
# Ключ - русская строка ровно как в коде, значение - английский перевод.
# Сообщения ядра (core.py) о нечитаемых архивах и реестрах не переводятся.

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
