"""The scene templates in templates/: up to date with the generator, within Molion's limits."""

import json
import os
import sys

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build_templates  # noqa: E402

MAX_ITEMS = 200
MAX_BYTES = 2 * 1024 * 1024


def test_the_files_are_what_the_generator_writes():
    assert build_templates.main(['--check']) == 0


def test_the_manifest_names_every_template_and_no_other():
    manifest = json.load(open(os.path.join(ROOT, 'plugin.json'), encoding='utf-8'))
    named = {t['scene'] for t in manifest['contributes']['templates']}
    assert named == {f'templates/{name}' for name in build_templates.TEMPLATES}


def test_each_file_is_within_the_limits():
    for name in build_templates.TEMPLATES:
        path = os.path.join(ROOT, 'templates', name)
        assert os.path.getsize(path) <= MAX_BYTES
        items = json.load(open(path, encoding='utf-8'))['items']
        assert 0 < len(items) <= MAX_ITEMS
        assert {item['type'] for item in items} <= {'image', 'annotation', 'molecule'}
