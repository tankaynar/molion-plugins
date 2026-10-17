import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from nmr.structure import read            # noqa: E402
from nmr.table import ShiftTable          # noqa: E402

FIXTURES = os.path.join(ROOT, 'tests', 'fixtures', 'structures.json')


@pytest.fixture(scope='session')
def table():
    return ShiftTable.load(os.path.join(ROOT, 'data', 'shifts.bin.gz'))


@pytest.fixture(scope='session')
def raw():
    with open(FIXTURES, encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture
def molecule(raw):
    """molecule('ethyl acetate') → Structure, as Molion would send it."""
    return lambda name: read(raw[name])
