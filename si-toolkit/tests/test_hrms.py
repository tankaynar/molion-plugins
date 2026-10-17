"""Calculated m/z and the formulas of the ions, checked against hand-worked values."""

import copy

import pytest
from conftest import IBUPROFEN

from si import elemental, hrms
from si import formula as formulas


def ion(adduct_id, structure=IBUPROFEN):
    return hrms.ion(structure, hrms.BY_ID[adduct_id])


@pytest.mark.parametrize('adduct, mz, formula', [
    ('esi-mh', '207.1380', 'C₁₃H₁₉O₂'),
    ('esi-mna', '229.1199', 'C₁₃H₁₈NaO₂'),
    ('esi-mk', '245.0938', 'C₁₃H₁₈KO₂'),
    ('esi-mnh4', '224.1645', 'C₁₃H₂₂NO₂'),
    ('esi-m-h', '205.1234', 'C₁₃H₁₇O₂'),
    ('esi-mcl', '241.1001', 'C₁₃H₁₈ClO₂'),
    ('ei-m', '206.1301', 'C₁₃H₁₈O₂'),
])
def test_ibuprofen(adduct, mz, formula):
    found = ion(adduct)
    assert f'{found.mz:.4f}' == mz
    assert found.formula == formula


def test_the_line_ends_ready_for_the_measured_value():
    assert ion('esi-mna').line() == 'HRMS (ESI) m/z: [M+Na]⁺ calcd for C₁₃H₁₈NaO₂ 229.1199, found '


def test_an_ion_as_drawn_is_measured_as_it_is():
    cation = copy.deepcopy(IBUPROFEN)
    cation.update(charge=1, exactMass=100.0)
    found = ion('esi-mna', cation)
    assert (found.label, found.mz, found.formula) == ('[M]⁺', 100.0, 'C₁₃H₁₈O₂')
    cation.update(charge=2)
    assert ion('esi-mh', cation).mz == 50.0
    assert ion('esi-mh', cation).label == '[M]²⁺'


def test_a_drawn_isotope_is_kept_in_the_formula():
    labelled = copy.deepcopy(IBUPROFEN)
    labelled['composition'] = [{'element': 'C', 'isotope': 0, 'count': 12},
                               {'element': 'C', 'isotope': 13, 'count': 1},
                               {'element': 'H', 'isotope': 0, 'count': 17},
                               {'element': 'H', 'isotope': 2, 'count': 1},
                               {'element': 'O', 'isotope': 0, 'count': 2}]
    assert ion('esi-mh', labelled).formula == 'C₁₂¹³CH₁₈DO₂'
    assert ion('esi-mh', labelled).plain_formula == 'C12[13C]H18DO2'


def test_without_carbon_hill_order_is_alphabetical():
    counts = {('O', 0): 1, ('H', 0): 2, ('Na', 0): 1}
    assert formulas.formula(counts, unicode=False) == 'H2NaO'


def test_no_mass_no_line():
    unknown = dict(IBUPROFEN, exactMass=None, warnings=['R has no defined structure, so no masses are given'])
    with pytest.raises(hrms.NotMeasurable, match='R has no defined structure'):
        ion('esi-mh', unknown)
    with pytest.raises(hrms.NotMeasurable, match='polymer'):
        ion('esi-mh', dict(IBUPROFEN, kind='repeat-unit'))


def test_nothing_to_deprotonate():
    carbon_dioxide = {'kind': 'whole', 'charge': 0, 'exactMass': 43.98983,
                      'composition': [{'element': 'C', 'isotope': 0, 'count': 1},
                                      {'element': 'O', 'isotope': 0, 'count': 2}]}
    with pytest.raises(hrms.NotMeasurable):
        ion('esi-m-h', carbon_dioxide)


def test_elemental_analysis_lists_what_combustion_measures():
    assert elemental.line(IBUPROFEN) == 'Anal. Calcd for C₁₃H₁₈O₂: C, 75.69; H, 8.80'
    sulfonamide = dict(IBUPROFEN, elementalAnalysis=[
        {'element': 'C', 'percent': 49.1}, {'element': 'H', 'percent': 5.1}, {'element': 'N', 'percent': 8.18},
        {'element': 'O', 'percent': 18.7}, {'element': 'S', 'percent': 18.725}])
    assert elemental.line(sulfonamide).endswith('C, 49.10; H, 5.10; N, 8.18; S, 18.73')


def test_elemental_analysis_needs_a_reported_element():
    salt = dict(IBUPROFEN, elementalAnalysis=[{'element': 'Na', 'percent': 39.3}, {'element': 'Cl', 'percent': 60.7}])
    with pytest.raises(elemental.NotAnalysable, match='no C, H, N or S'):
        elemental.line(salt)
