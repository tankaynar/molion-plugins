"""First-order multiplets of common groups, as they are reported."""

import pytest

from nmr import multiplets


def split_of(structure, predicate):
    atom = next(a for a in structure.heavy_atoms if predicate(a))
    return multiplets.multiplet_of(structure, atom)


def test_ethyl_is_a_quartet_and_a_triplet(molecule):
    ester = molecule('ethyl acetate')
    ch2 = split_of(ester, lambda a: a.hydrogens == 2)
    ch3 = split_of(ester, lambda a: a.hydrogens == 3 and any(
        ester.atoms[n].hydrogens == 2 for n, *_ in a.neighbours))
    acetyl = split_of(ester, lambda a: a.hydrogens == 3 and not any(
        ester.atoms[n].hydrogens == 2 for n, *_ in a.neighbours))
    assert (ch2.name, ch2.j_text) == ('q', '7.0')
    assert (ch3.name, ch3.j_text) == ('t', '7.0')
    assert acetyl.name == 's' and acetyl.j_text is None


def test_isopropyl_is_a_septet_and_a_doublet(molecule):
    cumene = molecule('isopropylbenzene')
    assert split_of(cumene, lambda a: a.hydrogens == 1 and not a.aromatic).name == 'sept'
    assert split_of(cumene, lambda a: a.hydrogens == 3).name == 'd'


def test_couplings_close_together_merge(molecule):
    propanol = molecule('propan-1-ol')
    middle = split_of(propanol, lambda a: a.hydrogens == 2 and all(
        propanol.atoms[n].element == 'C' for n, *_ in a.neighbours))
    assert middle.name == 'sext'


def test_hydroxyl_is_broad(molecule):
    assert split_of(molecule('propan-1-ol'), lambda a: a.element == 'O').name == 'br s'


def test_para_disubstituted_ring_gives_doublets(molecule):
    anisole = molecule('4-methylanisole')
    ring = [a for a in anisole.heavy_atoms if a.aromatic and a.hydrogens == 1]
    assert {multiplets.multiplet_of(anisole, a).name for a in ring} == {'d'}
    assert multiplets.multiplet_of(anisole, ring[0]).couplings == [(1, multiplets.J_ORTHO)]


def test_monosubstituted_ring_has_meta_couplings(molecule):
    toluene = molecule('toluene')
    names = {multiplets.multiplet_of(toluene, a).name
             for a in toluene.heavy_atoms if a.aromatic and a.hydrogens == 1}
    assert names == {'dd', 't', 'tt'}


def test_alkene_geometry_sets_the_coupling(molecule):
    trans = split_of(molecule('methyl (E)-crotonate'), lambda a: a.hydrogens == 1 and any(
        o == 2 for _, o, *_ in a.neighbours) and any(molecule('methyl (E)-crotonate').atoms[n].hydrogens == 3
                                                      for n, *_ in a.neighbours))
    cis = split_of(molecule('methyl (Z)-crotonate'), lambda a: a.hydrogens == 1 and any(
        o == 2 for _, o, *_ in a.neighbours) and any(molecule('methyl (Z)-crotonate').atoms[n].hydrogens == 3
                                                      for n, *_ in a.neighbours))
    assert trans.name == 'dq' and trans.couplings[0][1] == multiplets.J_TRANS
    assert cis.name == 'dq' and cis.couplings[0][1] == multiplets.J_CIS


def test_vinyl_group(molecule):
    styrene = molecule('styrene')
    ch = split_of(styrene, lambda a: a.hydrogens == 1 and not a.aromatic)
    ch2 = split_of(styrene, lambda a: a.hydrogens == 2)
    assert (ch.name, ch.j_text) == ('dd', '16.5, 10.5')
    assert ch2.name == 'm'


def test_ring_alkene_is_cis(molecule):
    ring = molecule('4-methylcyclohexene')
    alkene = split_of(ring, lambda a: a.hydrogens == 1 and any(o == 2 for _, o, *_ in a.neighbours))
    assert multiplets.J_CIS in [j for _, j in alkene.couplings]


# Equivalent hydrogens do not split each other: cyclohexene's two alkene H are one class.
def test_symmetric_ring_alkene_couples_only_to_its_neighbours(molecule):
    ring = molecule('cyclohexene')
    alkene = split_of(ring, lambda a: a.hydrogens == 1)
    assert [j for _, j in alkene.couplings] == [multiplets.J_VICINAL]


def test_five_membered_aromatic_couplings_are_small(molecule):
    thiophene = molecule('thiophene')
    js = {j for a in thiophene.heavy_atoms if a.hydrogens
          for _, j in multiplets.multiplet_of(thiophene, a).couplings}
    assert js == {multiplets.J_FIVE_RING}


def test_lines_are_binomial_and_sum_to_one():
    lines = multiplets._lines([(3, 7.0)])
    assert len(lines) == 4
    assert [round(i * 8) for _, i in lines] == [1, 3, 3, 1]
    assert sum(i for _, i in lines) == pytest.approx(1)
    assert lines[1][0] - lines[0][0] == pytest.approx(7.0 / multiplets.FREQUENCY)
