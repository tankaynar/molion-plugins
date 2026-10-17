import pytest

from p2s import molfile
from p2s.structure import AROMATIC, DOUBLE, HASH, SINGLE, WEDGE, Atom, Bond, Structure


def ethanol(scale=40.0):
    return Structure([Atom('C', 0, 0), Atom('C', scale, 0), Atom('O', scale * 1.5, scale * 0.866)],
                     [Bond(0, 1), Bond(1, 2)])


def atom_lines(text):
    lines = text.split('\n')
    count = int(lines[3][:3])
    return lines[4:4 + count]


def bond_lines(text):
    lines = text.split('\n')
    atoms, bonds = int(lines[3][:3]), int(lines[3][3:6])
    return lines[4 + atoms:4 + atoms + bonds]


def coords(line):
    return float(line[:10]), float(line[10:20])


def test_counts_line_and_end():
    text = molfile.write(ethanol())
    assert text.split('\n')[3].startswith('  3  2')
    assert text.split('\n')[3].endswith('V2000')
    assert text.endswith('M  END\n')
    assert '\r' not in text


def test_the_median_bond_becomes_one_and_a_half_angstroms_whatever_the_picture_size():
    for scale in (12.0, 40.0, 300.0):
        lines = atom_lines(molfile.write(ethanol(scale)))
        (x0, y0), (x1, y1) = coords(lines[0]), coords(lines[1])
        assert abs(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 - 1.5) < 1e-3


def test_y_points_up_and_the_drawing_is_centred():
    lines = atom_lines(molfile.write(ethanol()))
    points = [coords(line) for line in lines]
    assert points[2][1] < points[1][1]         # the oxygen was drawn below, in picture pixels
    assert abs(sum(p[0] for p in points)) < 1e-3
    assert abs(sum(p[1] for p in points)) < 1e-3


def test_bond_kinds():
    structure = Structure([Atom('C', 0, 0), Atom('C', 40, 0), Atom('C', 80, 0), Atom('C', 120, 0),
                           Atom('C', 160, 0)],
                          [Bond(0, 1, DOUBLE), Bond(1, 2, WEDGE), Bond(2, 3, HASH), Bond(3, 4, AROMATIC)])
    assert [line.split() for line in bond_lines(molfile.write(structure))] == [
        ['1', '2', '2', '0'], ['2', '3', '1', '1'], ['3', '4', '1', '6'], ['4', '5', '4', '0']]


def test_charges_isotopes_and_aliases():
    structure = Structure([Atom('[NH+]', 0, 0), Atom('[13CH3]', 40, 0), Atom('[OMe]', 80, 0)],
                          [Bond(0, 1, SINGLE), Bond(1, 2, SINGLE)])
    text = molfile.write(structure)
    assert 'M  CHG  1   1   1' in text
    assert 'M  ISO  1   2  13' in text
    assert 'A    3\nOMe\n' in text
    assert atom_lines(text)[2][31:34].strip() == 'C'


def test_a_lone_atom_still_writes():
    assert 'M  END' in molfile.write(Structure([Atom('O', 5, 5)], []))


def test_a_bond_to_nowhere_is_refused():
    with pytest.raises(ValueError):
        molfile.write(Structure([Atom('C', 0, 0)], [Bond(0, 3)]))


def test_nothing_to_write_is_refused():
    with pytest.raises(ValueError):
        molfile.write(Structure())
