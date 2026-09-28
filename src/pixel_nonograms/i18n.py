"""Runtime UI translations; identifiers and saved puzzle content stay language-neutral."""
import json
import re
from pathlib import Path
from string import Formatter

LANGUAGES = {"tr": "Türkçe", "az": "Azərbaycanca", "es": "Español",
             "ru": "Русский", "en": "English"}
_language = "tr"
_sources = {}
_catalog = json.loads((Path(__file__).parent / "translations.json").read_text(encoding="utf-8"))
_patterns = []
for _source, _values in _catalog.items():
    if "{" in _source:
        _parts = list(Formatter().parse(_source))
        _regex = "".join(re.escape(literal) + ("(.+?)" if field is not None else "")
                         for literal, field, _, _ in _parts)
        _patterns.append((re.compile("^" + _regex + "$", re.DOTALL), _values))


def language():
    return _language


def tr(text):
    """Translate a displayed string, including formatted messages and nested labels."""
    if not isinstance(text, str) or not text:
        return text
    source = _sources.get(text, text)
    if _language == "tr":
        return source
    index = ("az", "es", "ru", "en").index(_language)
    values = _catalog.get(source)
    if values:
        result = values[index]
    else:
        result = source
        for pattern, translations in _patterns:
            match = pattern.fullmatch(source)
            if match:
                result = translations[index].format(*(tr(value) for value in match.groups()))
                break
        else:
            # Composite status lines retain punctuation while translating their labels.
            for separator in ("\n", "   ·   ", " · ", " → ", ", ", ": "):
                if separator in source:
                    result = separator.join(tr(part) for part in source.split(separator))
                    break
    if result != source:
        _sources[result] = source
    return result


def set_language(code):
    global _language
    _language = code if code in LANGUAGES else "tr"


def translate_widgets(root):
    """Update visible controls in place, preserving game moves, editor data and focus."""
    from PySide6.QtCore import QObject
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QAbstractButton, QComboBox, QLabel, QLineEdit, QWidget

    for item in [root, *root.findChildren(QObject)]:
        refresh = getattr(item, "refresh_translation", None)
        if refresh is not None:
            refresh()
        if isinstance(item, QWidget):
            for getter, setter in (("toolTip", "setToolTip"),
                                   ("accessibleName", "setAccessibleName"),
                                   ("windowTitle", "setWindowTitle")):
                getattr(item, setter)(tr(getattr(item, getter)()))
        if isinstance(item, (QLabel, QAbstractButton, QAction)):
            item.setText(tr(item.text()))
        if isinstance(item, QAction):
            item.setToolTip(tr(item.toolTip()))
        if isinstance(item, QLineEdit):
            item.setPlaceholderText(tr(item.placeholderText()))
        if isinstance(item, QComboBox):
            blocked = item.blockSignals(True)
            if item.property("language_picker"):
                item.setCurrentIndex(item.findData(_language))
            else:
                for index in range(item.count()):
                    item.setItemText(index, tr(item.itemText(index)))
            item.blockSignals(blocked)
