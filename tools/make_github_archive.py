"""Export project files without local saves, environments or reference material."""
import hashlib
import json
import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ('src', 'tests', 'tools', 'packaging', 'snap', '.github', 'docs')
FILES = ('pyproject.toml', 'README.md', 'README_LINUX.md', 'THIRD_PARTY_NOTICES.md',
         'GELISTIRME_DEVIR.md', 'flake.nix', 'flake.lock', 'default.nix', 'MANIFEST.in', 'Oyunu_Baslat.bat', 'Oyunu_Baslat_Linux.sh',
         '.gitignore', '.gitattributes', '.dockerignore')
ALLOWED = {'.py', '.json', '.md', '.toml', '.bat', '.sh', '.yml', '.yaml',
           '.png', '.svg', '.desktop', '.txt', '.nix', '.lock', '.spec'}


def project_files(root=ROOT):
    paths = [root / name for name in FILES]
    for directory in DIRECTORIES:
        for path in (root / directory).rglob('*'):
            if (path.is_file() and '__pycache__' not in path.parts
                    and not any(p.endswith('.egg-info') for p in path.parts)
                    and (path.suffix in ALLOWED or path.name in ('Dockerfile', 'pixel-nonograms'))):
                paths.append(path)
    return sorted(set(paths))


def main():
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    output = ROOT / 'dist' / f'Pixel_Nonograms_GitHub_{version}.zip'
    output.parent.mkdir(exist_ok=True)
    manifest = {}
    prefix = 'Pixel_Nonograms_Game/'
    with ZipFile(output, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for path in project_files():
            name = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            info = ZipInfo(prefix + name)
            info.create_system = 3
            info.external_attr = ((0o100755 if path.suffix == '.sh' else 0o100644) << 16)
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, data)
            manifest[name] = hashlib.sha256(data).hexdigest()
        archive.writestr(prefix + 'SOURCE_MANIFEST.json', json.dumps(manifest, indent=2)+'\n')
    with ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Archive integrity failed')
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n', encoding='utf-8')
    print(f'{output}\n{len(manifest)} files; {output.stat().st_size:,} bytes\nSHA256 {digest}')


if __name__ == '__main__':
    main()
