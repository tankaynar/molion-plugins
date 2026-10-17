"""HOSE codes: the same surroundings always give the same code, however atoms are numbered."""

import copy
import random

from nmr import hose
from nmr.structure import read


def renumbered(entry, seed):
    """The same molecule with its atoms listed in another order."""
    order = list(range(len(entry['atoms'])))
    random.Random(seed).shuffle(order)
    where = {old: new for new, old in enumerate(order)}
    shuffled = copy.deepcopy(entry)
    shuffled['atoms'] = [entry['atoms'][old] for old in order]
    for bond in shuffled['bonds']:
        bond['atoms'] = [where[i] for i in bond['atoms']]
    return shuffled, where


def test_codes_do_not_depend_on_numbering(raw):
    for name in ('4-methylanisole', 'isopropylbenzene', 'methyl (E)-crotonate'):
        entry = raw[name]
        original = read(entry)
        for seed in range(3):
            shuffled_entry, where = renumbered(entry, seed)
            shuffled = read(shuffled_entry)
            for atom in original.heavy_atoms:
                assert hose.codes(original, atom.index) == hose.codes(shuffled, where[atom.index])


def test_equivalent_atoms_share_codes(molecule):
    benzene = molecule('benzene')
    assert len({tuple(hose.codes(benzene, a.index)) for a in benzene.heavy_atoms}) == 1


def test_deeper_codes_say_more(molecule):
    toluene = molecule('toluene')
    methyl = next(a for a in toluene.heavy_atoms if not a.aromatic)
    codes = hose.codes(toluene, methyl.index)
    assert len(codes) == hose.MAX_DEPTH
    assert codes[0] == 'CH3(c)'
    assert all(len(codes[i]) < len(codes[i + 1]) for i in range(len(codes) - 1))


def test_rings_close(molecule):
    # Five atoms round: the walk is back at its start within five spheres.
    thiophene = molecule('thiophene')
    assert '&' in hose.codes(thiophene, 0)[-1]


def test_keys_are_stable_and_distinct():
    assert hose.key('13C', 1, 'CH3(c)') == hose.key('13C', 1, 'CH3(c)')
    assert hose.key('13C', 1, 'CH3(c)') != hose.key('1H', 1, 'CH3(c)')
    assert hose.key('13C', 1, 'CH3(c)') != hose.key('13C', 2, 'CH3(c)')
