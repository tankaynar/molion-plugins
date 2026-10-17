"""Shifts against measured values (CDCl3, from the literature), within what HOSE codes
can promise: a few ppm for carbon, a few tenths for hydrogen."""

import pytest

from nmr import predict

CARBON_TOLERANCE = 3.0
PROTON_TOLERANCE = 0.25


def shifts(table, structure, nucleus, atoms):
    return sorted((predict.shift_of(table, structure, a.index, nucleus).value for a in atoms), reverse=True)


@pytest.mark.parametrize('name, carbon, proton', [
    ('ethyl acetate', [171.1, 60.4, 21.0, 14.2], [4.12, 2.05, 1.26]),
    ('toluene', [137.9, 129.1, 128.3, 125.3, 21.5], [7.25, 7.17, 7.15, 2.35]),
    ('4-methylanisole', [157.6, 129.9, 129.8, 113.8, 55.2, 20.5], [7.09, 6.81, 3.78, 2.29]),
])
def test_common_molecules(table, molecule, name, carbon, proton):
    structure = molecule(name)
    by_class = {}
    for atom in predict.carbons(structure):
        by_class.setdefault(atom.symmetry_class, atom)
    got = shifts(table, structure, predict.CARBON, by_class.values())
    assert got == pytest.approx(carbon, abs=CARBON_TOLERANCE)

    by_class = {}
    for atom in predict.protonated(structure):
        by_class.setdefault(atom.symmetry_class, atom)
    got = shifts(table, structure, predict.PROTON, by_class.values())
    assert got == pytest.approx(proton, abs=PROTON_TOLERANCE)


def test_deepest_match_is_used(table, molecule):
    structure = molecule('ethyl acetate')
    carbonyl = next(a for a in structure.heavy_atoms if a.element == 'C' and a.hydrogens == 0)
    shift = predict.shift_of(table, structure, carbonyl.index, predict.CARBON)
    assert shift.depth == 5 and not shift.rough
    assert shift.count >= 1


def test_an_unknown_environment_has_no_prediction(table):
    from nmr.structure import read
    lonely = read({'atoms': [{'id': 'x', 'element': 'Og', 'hydrogens': 0}], 'bonds': []})
    assert predict.shift_of(table, lonely, 0, predict.CARBON) is None
