"""Build native amd64 .deb, AppImage and a single release archive on Debian 12."""
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
TOOL_URL = ('https://github.com/AppImage/appimagetool/releases/download/1.9.1/'
            'appimagetool-x86_64.AppImage')
TOOL_SHA256 = 'ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0'
DEPENDENCIES = ('libc6 (>= 2.36), libstdc++6 (>= 12), libgcc-s1, libegl1, libgl1, '
                'libopengl0, libdbus-1-3, libfontconfig1, libfreetype6, '
                'libglib2.0-0 | libglib2.0-0t64, libgssapi-krb5-2, '
                'libxkbcommon0, libxkbcommon-x11-0, '
                'libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, '
                'libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxcb-xfixes0, '
                'fonts-dejavu-core')


def run(*args, cwd=ROOT, env=None):
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True, timeout=900)


def write(path, text, executable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')
    path.chmod(0o755 if executable else 0o644)


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    if sys.platform != 'linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise SystemExit('Linux amd64 gerekir. README_LINUX.md içindeki Docker/GitHub yolunu kullanın.')
    output = Path(os.environ.get('OUTPUT_DIR', ROOT / 'dist/linux')).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pixel-linux-build-') as temporary:
        work = Path(temporary)
        bundle_root = work / 'frozen'
        command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
                   '--name', 'pixel-nonograms', '--distpath', str(bundle_root),
                   '--workpath', str(work / 'pyinstaller'), '--specpath', str(work),
                   '--collect-all', 'pixel_nonograms', '--recursive-copy-metadata', 'pixel-nonograms']
        # Common Qt xcb helpers are not present on every AppImage host desktop.
        for name in ('libxcb-cursor.so.0', 'libxcb-icccm.so.4', 'libxcb-image.so.0',
                     'libxcb-keysyms.so.1', 'libxcb-render-util.so.0', 'libxcb-xinerama.so.0',
                     'libxkbcommon-x11.so.0'):
            library = Path('/usr/lib/x86_64-linux-gnu') / name
            if not library.exists():
                raise RuntimeError(f'Missing build dependency: {name}')
            command += ['--add-binary', f'{library}:.']
        run(*command, ROOT / 'packaging/linux/launcher.py')
        frozen = bundle_root / 'pixel-nonograms'
        smoke_env = dict(os.environ, QT_QPA_PLATFORM='xcb')
        run('xvfb-run', '-a', frozen / 'pixel-nonograms', '--smoke-test', env=smoke_env)

        notice = frozen / 'THIRD_PARTY_NOTICES.md'
        shutil.copy2(ROOT / 'LICENSE', frozen / 'LICENSE')
        shutil.copy2(ROOT / 'THIRD_PARTY_NOTICES.md', notice)
        # Preserve bundled dependency licenses, including Qt/Python, beside the executable.
        import importlib.metadata
        import sysconfig
        licenses = frozen / 'licenses'
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

        appdir = work / 'PixelNonograms.AppDir'
        shutil.copytree(frozen, appdir / 'usr/lib/pixel-nonograms', symlinks=True)
        write(appdir / 'AppRun', '#!/bin/sh\nset -eu\n'
              'HERE=$(dirname -- "$0")\n'
              'HERE=$(CDPATH= cd "$HERE" && pwd)\n'
              'export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"\n'
              'exec "$HERE/usr/lib/pixel-nonograms/pixel-nonograms" "$@"\n', True)
        desktop = ROOT / 'packaging/linux/pixel-nonograms.desktop'
        shutil.copy2(desktop, appdir / desktop.name)
        shutil.copy2(ROOT / 'packaging/linux/pixel-nonograms.png', appdir / 'pixel-nonograms.png')
        (appdir / '.DirIcon').symlink_to('pixel-nonograms.png')
        run('desktop-file-validate', appdir / desktop.name)
        tool = work / 'appimagetool.AppImage'
        urllib.request.urlretrieve(TOOL_URL, tool)
        if checksum(tool) != TOOL_SHA256:
            raise RuntimeError('appimagetool SHA256 verification failed')
        tool.chmod(0o755)
        appimage = output / f'Pixel_Nonograms-{VERSION}-x86_64.AppImage'
        run(tool, appdir, appimage,
            env=dict(os.environ, ARCH='x86_64', APPIMAGE_EXTRACT_AND_RUN='1'))
        # Check the real AppImage payload without requiring FUSE in a container.
        extracted = work / 'appimage-test'
        extracted.mkdir()
        run(appimage, '--appimage-extract', cwd=extracted)
        run('xvfb-run', '-a', extracted / 'squashfs-root/AppRun', '--smoke-test', env=smoke_env)

        debroot = work / 'debian'
        shutil.copytree(frozen, debroot / 'opt/pixel-nonograms', symlinks=True)
        write(debroot / 'usr/bin/pixel-nonograms', '#!/bin/sh\n'
              'export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"\n'
              'exec /opt/pixel-nonograms/pixel-nonograms "$@"\n', True)
        applications = debroot / 'usr/share/applications'
        applications.mkdir(parents=True)
        shutil.copy2(desktop, applications / desktop.name)
        icons = debroot / 'usr/share/icons/hicolor/256x256/apps'
        icons.mkdir(parents=True)
        shutil.copy2(ROOT / 'packaging/linux/pixel-nonograms.png', icons / 'pixel-nonograms.png')
        installed_kib = sum(p.stat().st_size for p in debroot.rglob('*') if p.is_file()) // 1024
        write(debroot / 'DEBIAN/control',
              f'Package: pixel-nonograms\nVersion: {VERSION}\nArchitecture: amd64\n'
              'Maintainer: Pixel Nonograms Packaging <noreply@users.noreply.github.com>\n'
              f'Section: games\nPriority: optional\nInstalled-Size: {installed_kib}\n'
              f'Depends: {DEPENDENCIES}\n'
              'Description: Offline picture logic game with 1000 puzzles\n'
              ' Monochrome and color nonograms, five languages and fullscreen painting.\n')
        deb = output / f'pixel-nonograms_{VERSION}_amd64.deb'
        run('dpkg-deb', '--root-owner-group', '--build', debroot, deb)
        run('dpkg-deb', '--info', deb)
        shutil.copy2(ROOT / 'README_LINUX.md', output / 'README_LINUX.md')
        shutil.copy2(ROOT / 'LICENSE', output / 'LICENSE')
        shutil.copy2(ROOT / 'THIRD_PARTY_NOTICES.md', output / 'THIRD_PARTY_NOTICES.md')
        files = [appimage, deb, output / 'LICENSE', output / 'README_LINUX.md', output / 'THIRD_PARTY_NOTICES.md']
        manifest = output / 'SHA256SUMS.txt'
        write(manifest, ''.join(f'{checksum(p)}  {p.name}\n' for p in files))
        archive = output / f'Pixel_Nonograms-{VERSION}-Linux-x86_64.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            for path in files + [manifest]:
                tar.add(path, arcname=f'Pixel_Nonograms-Linux/{path.name}')
        print(f'READY: {archive}', flush=True)


if __name__ == '__main__':
    main()
