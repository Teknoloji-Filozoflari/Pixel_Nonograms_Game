import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('build_bundle', ROOT / 'tools/build_bundle.py')
build_bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_bundle)
RESOURCES = ('catalog_expansion.json', 'catalog_extended.json', 'translations.json')


@pytest.mark.parametrize('missing', RESOURCES)
def test_bundle_rejects_missing_catalog_or_translations(tmp_path, missing):
    package = tmp_path / '_internal/pixel_nonograms'
    package.mkdir(parents=True)
    for name in RESOURCES:
        if name != missing:
            (package / name).write_text('{}')
    with pytest.raises(RuntimeError, match=missing):
        build_bundle.validate_resources(tmp_path)


def test_bundle_accepts_all_required_resources(tmp_path):
    package = tmp_path / '_internal/pixel_nonograms'
    package.mkdir(parents=True)
    for name in RESOURCES:
        (package / name).write_text('{}')
    build_bundle.validate_resources(tmp_path)
