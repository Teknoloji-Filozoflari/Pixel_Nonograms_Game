"""Package a verified Nonogram bundle for Fedora 43."""

import shutil
import subprocess
import tarfile
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory

from build_bundle import ROOT, validate_resources


def main() -> None:
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    bundle = ROOT / 'build/bundle/pixel-nonograms'
    validate_resources(bundle)
    with TemporaryDirectory(prefix='nonogram-rpm-') as temporary:
        top = Path(temporary)
        for name in ('BUILD', 'BUILDROOT', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS'):
            (top / name).mkdir()
        stage = top / 'payload'
        shutil.copytree(bundle, stage / 'usr/lib/pixel-nonograms')
        files = {
            'LICENSE': 'usr/share/doc/pixel-nonograms/LICENSE',
            'packaging/rpm/pixel-nonograms': 'usr/bin/pixel-nonograms',
            'packaging/linux/pixel-nonograms.desktop':
                'usr/share/applications/pixel-nonograms.desktop',
            'packaging/linux/pixel-nonograms.png':
                'usr/share/icons/hicolor/256x256/apps/pixel-nonograms.png',
            'THIRD_PARTY_NOTICES.md': 'usr/share/doc/pixel-nonograms/THIRD_PARTY_NOTICES.md',
        }
        for source, target in files.items():
            destination = stage / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / source, destination)
        with tarfile.open(top / 'SOURCES/payload.tar.gz', 'w:gz') as archive:
            archive.add(stage / 'usr', arcname='usr')
        subprocess.run(['rpmbuild', '-bb', '--define', f'_topdir {top}', '--define',
                        f'app_version {version}', str(ROOT / 'packaging/rpm/pixel-nonograms.spec')],
                       check=True)
        output = ROOT / 'dist'
        output.mkdir(exist_ok=True)
        for package in (top / 'RPMS').rglob('*.rpm'):
            shutil.copy2(package, output / package.name)
            print(output / package.name)


if __name__ == '__main__':
    main()
