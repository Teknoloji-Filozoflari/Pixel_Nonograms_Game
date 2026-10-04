"""Build the shared private Python/Qt bundle for RPM and Snap."""

import importlib.metadata
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_resources(bundle: Path) -> None:
    package = bundle / '_internal/pixel_nonograms'
    for name in ('catalog_expansion.json', 'catalog_extended.json', 'translations.json'):
        if not (package / name).is_file():
            raise RuntimeError(f'Missing bundled resource: {name}')


def main() -> None:
    output = ROOT / 'build/bundle'
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
               '--name', 'pixel-nonograms', '--distpath', str(output),
               '--workpath', str(ROOT / 'build/bundle-work'),
               '--specpath', str(ROOT / 'build'), '--collect-all', 'pixel_nonograms',
               '--recursive-copy-metadata', 'pixel-nonograms']
    for name in ('libxcb-cursor.so.0', 'libxcb-icccm.so.4', 'libxcb-image.so.0',
                 'libxcb-keysyms.so.1', 'libxcb-render-util.so.0', 'libxcb-xinerama.so.0',
                 'libxkbcommon-x11.so.0'):
        library = next((path / name for path in (Path('/usr/lib/x86_64-linux-gnu'),
                       Path('/usr/lib64'), Path('/lib64')) if (path / name).exists()), None)
        if library is None:
            raise RuntimeError(f'Missing build dependency: {name}')
        command += ['--add-binary', f'{library}:.']
    subprocess.run(command + [str(ROOT / 'packaging/linux/launcher.py')], check=True, cwd=ROOT)
    frozen = output / 'pixel-nonograms'
    validate_resources(frozen)
    shutil.copy2(ROOT / 'THIRD_PARTY_NOTICES.md', frozen / 'THIRD_PARTY_NOTICES.md')
    licenses = frozen / 'licenses'
    licenses.mkdir(exist_ok=True)
    for package in ('PySide6-Essentials', 'shiboken6', 'numpy', 'Pillow', 'pyinstaller'):
        distribution = importlib.metadata.distribution(package)
        for item in distribution.files or ():
            if any(word in str(item).lower() for word in ('license', 'copying', 'copyright')):
                source = Path(distribution.locate_file(item))
                if source.is_file():
                    target = licenses / package / str(item)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    python_license = Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt'
    if python_license.exists():
        shutil.copy2(python_license, licenses / 'Python-LICENSE.txt')
    subprocess.run([str(frozen / 'pixel-nonograms'), '--smoke-test'], check=True, timeout=120,
                   env=dict(os.environ, QT_QPA_PLATFORM='offscreen'))
    print(f'Verified bundle: {frozen}')


if __name__ == '__main__':
    main()
