"""The SI stub: which compounds, in what order, and how they are written."""

import csv
import io

from conftest import IBUPROFEN

from si import hrms, numbers, stub
from si.compounds import Compound


def sort(texts):
    return sorted(texts, key=numbers.sort_key_for(texts))


def test_arabic_numbers_sort_as_numbers_with_their_series():
    assert sort(['10', '2', '3b', '1', '3a']) == ['1', '2', '3a', '3b', '10']


def test_roman_numerals_sort_by_value():
    assert sort(['IV', 'II', 'IX', 'V', 'I', 'III']) == ['I', 'II', 'III', 'IV', 'V', 'IX']


def test_letters_are_letters_when_not_every_one_is_a_numeral():
    assert sort(['C', 'B', 'AA', 'A', 'D']) == ['A', 'B', 'C', 'D', 'AA']


def compound(number='3a', name='ibuprofen', structure=IBUPROFEN):
    return Compound('m1', number, structure, name, 'CC(C)Cc1ccc(cc1)C(C)C(=O)O', 'InChI=1S/C13H18O2/c1')


def test_a_block_per_compound():
    text = stub.text([compound()], hrms.BY_ID['esi-mh'])
    assert text == ('3a: ibuprofen\n'
                    'C₁₃H₁₈O₂; HRMS (ESI) m/z: [M+H]⁺ calcd for C₁₃H₁₉O₂ 207.1380, found\n'
                    'SMILES: CC(C)Cc1ccc(cc1)C(C)C(=O)O\n'
                    'InChI: InChI=1S/C13H18O2/c1\n')


def test_an_unnumbered_unnamed_compound_starts_with_its_formula():
    assert stub.heading(compound(number=None, name=None)) == ''
    # The formula line says what it is, once.
    assert stub.block(compound(number=None, name=None), None).split('\n')[:2] == [
        'C₁₃H₁₈O₂', 'SMILES: CC(C)Cc1ccc(cc1)C(C)C(=O)O']
    assert stub.heading(compound(number=None)) == 'ibuprofen'


def test_csv_quotes_what_needs_it_and_ends_lines_with_lf():
    rows = [compound(name='2-[4-(2-methylpropyl)phenyl]propanoic acid, "racemic"'), compound(number=None)]
    text = stub.csv_text(rows, hrms.BY_ID['esi-mna'])
    assert '\r' not in text
    parsed = list(csv.reader(io.StringIO(text)))
    assert parsed[0] == stub.CSV_HEADER
    assert parsed[1] == ['3a', '2-[4-(2-methylpropyl)phenyl]propanoic acid, "racemic"', 'C13H18O2', 'ESI',
                         '[M+Na]⁺', '229.1199', 'CC(C)Cc1ccc(cc1)C(C)C(=O)O', 'InChI=1S/C13H18O2/c1']
    assert parsed[2][0] == ''


def test_a_compound_without_a_mass_keeps_its_row():
    row = list(csv.reader(io.StringIO(stub.csv_text([compound(structure=dict(IBUPROFEN, exactMass=None))],
                                                    hrms.BY_ID['esi-mh']))))[1]
    assert row[3:6] == ['', '', '']
