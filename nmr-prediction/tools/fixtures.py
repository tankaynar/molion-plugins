#!/usr/bin/env python3
"""Writes tests/fixtures/structures.json: molecules as Molion sends them, so the tests run on
the standard library alone. Run with RDKit 2025.9.2 after changing
tools/structure_json.py.

    python tools/fixtures.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from rdkit import Chem                     # noqa: E402
from structure_json import describe        # noqa: E402

MOLECULES = {
    'ethyl acetate': 'CCOC(C)=O',
    '4-methylanisole': 'COc1ccc(C)cc1',
    'toluene': 'Cc1ccccc1',
    'benzene': 'c1ccccc1',
    'isopropylbenzene': 'CC(C)c1ccccc1',
    'propan-1-ol': 'CCCO',
    'styrene': 'C=Cc1ccccc1',
    'methyl (E)-crotonate': 'C/C=C/C(=O)OC',
    'methyl (Z)-crotonate': 'C/C=C\\C(=O)OC',
    'benzaldehyde': 'O=Cc1ccccc1',
    'cyclohexene': 'C1=CCCCC1',
    '4-methylcyclohexene': 'CC1CC=CCC1',
    'thiophene': 'c1ccsc1',
}


def main():
    fixtures = {name: describe(Chem.MolFromSmiles(smiles), molecule_id=name) for name, smiles in MOLECULES.items()}
    path = os.path.join(ROOT, 'tests', 'fixtures', 'structures.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(fixtures, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write('\n')
    print(f'wrote {path}')


if __name__ == '__main__':
    main()
