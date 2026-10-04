# Third-party components

Linux builds include Python, PySide6/Qt, Shiboken, NumPy and Pillow. PyInstaller
creates the executable bundle; appimagetool creates the AppImage container.
Each project retains its own copyright and license. Installed license files
are copied into the executable's `licenses/` directory; dependency metadata
is retained in the bundle.

- Python: https://docs.python.org/3/license.html
- PySide6 / Shiboken: https://doc.qt.io/qtforpython-6/licenses.html
- Qt: https://www.qt.io/licensing/open-source-lgpl-obligations
- NumPy: https://numpy.org/doc/stable/license.html
- Pillow: https://pillow.readthedocs.io/en/stable/about.html#license
- PyInstaller: https://pyinstaller.org/en/stable/license.html
- AppImage tools: https://github.com/AppImage/appimagetool

Shared libraries remain separate files. AppImage contents can be extracted
using `--appimage-extract`; Debian installs into `/opt/pixel-nonograms`.
The project is licensed under GPL-3.0-or-later; see [LICENSE](LICENSE).
This project license does not replace third-party licenses.
