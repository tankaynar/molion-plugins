"""Recorded PubChem answers: nothing in these tests reaches the network."""

import io
import json
import os
import sys
import threading
import urllib.error

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FIXTURES = os.path.join(ROOT, 'tests', 'fixtures')


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as f:
        return f.read()


def props(cid, title, smiles='C', formula='CH4'):
    return {'CID': cid, 'Title': title, 'MolecularFormula': formula, 'MolecularWeight': '16.04',
            'SMILES': smiles, 'IUPACName': title.lower(), 'InChI': 'InChI=1S/CH4/h1H4'}


class FakePubChem:
    """Answers by URL fragment; anything unscripted is a 404, as PubChem answers it."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []
        self._lock = threading.Lock()

    def __call__(self, url, timeout):
        with self._lock:
            self.calls.append(url)
        for fragment, body in self.routes.items():
            if fragment in url:
                if isinstance(body, BaseException):
                    raise body
                return body.encode() if isinstance(body, str) else json.dumps(body).encode()
        raise urllib.error.HTTPError(url, 404, 'Not Found', {}, io.BytesIO(b''))


def offline(url, timeout):
    raise urllib.error.URLError('no network in tests')


# PubChem's autocomplete puts the exact name tenth, behind more popular compounds.
HEME_SUGGESTIONS = ['Hemellitic acid', 'Hemellitol', 'Hemel', 'Hemetoidin', 'Heme d(1)',
                    'Hemerocallone', 'Hemerven', 'DIMETHYL PROPIONATE ESTER HEME',
                    'Heme Oxygenase-1-IN-1', 'heme']

HEMIN_SMILES = 'CC1=C(C2=CC3=C(C(=C([N-]3)C)C)C)C.[Fe+2]'


@pytest.fixture
def heme_pubchem():
    return FakePubChem({
        '/autocomplete/compound/heme/': {'dictionary_terms': {'compound': HEME_SUGGESTIONS}},
        '/compound/name/heme/cids': {'IdentifierList': {'CID': [26945, 4973, 444098, 444097, 162640511]}},
        '/compound/name/Hemellitic%20acid/cids': {'IdentifierList': {'CID': [10708]}},
        '/compound/name/Hemellitol/cids': {'IdentifierList': {'CID': [10686]}},
        '/compound/name/Hemel/cids': {'IdentifierList': {'CID': [3604]}},
        '/compound/name/Hemetoidin/cids': {'IdentifierList': {'CID': [5280352]}},
        # 'Heme d(1)' is unscripted: a suggestion PubChem cannot resolve is dropped.
        '/property/': {'PropertyTable': {'Properties': [
            props(26945, 'Hemin', HEMIN_SMILES, 'C34H32FeN4O4'),
            props(4973, 'Heme b'), props(444098, 'Protoporphyrin IX containing fe'),
            props(444097, 'Protoheme'), props(10708, 'Hemellitic acid'),
            props(10686, 'Hemellitol'), props(3604, 'HEMEL'), props(5280352, 'Hemetoidin'),
        ]}},
        '/compound/cid/26945/SDF?record_type=2d': fixture('heme-26945-2d.sdf'),
    })
