"""Fischer and Haworth layouts: atoms and bonds where the projection says."""

from teaching import projections
from teaching.geometry import BOND

GLYCERALDEHYDE = {
    'top': {'atom': '1', 'label': 'CHO', 'element': 'C'},
    'chain': [{'atom': '2', 'left': {'atom': None, 'label': 'H', 'element': 'H'},
               'right': {'atom': '3', 'label': 'OH', 'element': 'O'}, 'unspecified': False}],
    'bottom': {'atom': '4', 'label': 'CH2OH', 'element': 'C'},
}


def by_key(atoms):
    return {atom['key']: atom for atom in atoms}


def test_fischer_puts_the_oh_on_the_right_and_labels_the_ends():
    atoms, bonds = projections.fischer(GLYCERALDEHYDE)
    keyed = by_key(atoms)
    assert keyed['c1r']['x'] == BOND and keyed['c1r']['label'] == 'OH' and keyed['c1r']['element'] == 'O'
    assert keyed['c1l']['element'] == 'H' and keyed['c1l']['label'] is None
    assert keyed['top']['label'] == 'CHO' and keyed['bottom']['label'] == 'CH2OH'
    assert keyed['top']['y'] < keyed['c1']['y'] < keyed['bottom']['y']
    assert all(bond['stereo'] == 'None' for bond in bonds)


def test_fischer_with_wedges_wedges_the_horizontals_from_the_centre():
    _, bonds = projections.fischer(GLYCERALDEHYDE, wedges=True)
    wedged = [bond for bond in bonds if bond['stereo'] == 'Up']
    assert {(bond['a'], bond['b']) for bond in wedged} == {('c1', 'c1l'), ('c1', 'c1r')}


def test_a_ketose_carbon_gets_its_double_bond():
    answer = {**GLYCERALDEHYDE, 'chain': [{'atom': '2', 'double': {'atom': '5', 'label': 'O', 'element': 'O'}}]}
    atoms, bonds = projections.fischer(answer)
    assert {'a': 'c1', 'b': 'c1r', 'order': 'Double', 'stereo': 'None'} in bonds
    assert by_key(atoms)['c1r']['label'] is None


def glucopyranose():
    ring = ['o', 'c1', 'c2', 'c3', 'c4', 'c5']
    groups = [('c1', 'OH', 'O', True), ('c1', 'H', 'H', False), ('c2', 'OH', 'O', False), ('c2', 'H', 'H', True),
              ('c3', 'OH', 'O', True), ('c4', 'OH', 'O', False), ('c5', 'CH2OH', 'C', True), ('c5', 'H', 'H', False)]
    return {'ringSize': 6, 'ring': ring, 'anomer': 'beta', 'series': 'D',
            'substituents': [{'ringAtom': r, 'atom': None, 'label': l, 'element': e, 'up': u} for r, l, e, u in groups]}


def test_haworth_ring_with_bold_front_edges():
    atoms, bonds = projections.haworth(glucopyranose())
    ring_bonds = [b for b in bonds if b['a'].startswith('r') and b['b'].startswith('r')]
    assert len(ring_bonds) == 6
    bold = {(b['a'], b['b']) for b in ring_bonds if b['stereo'] == 'UpOrDown'}
    assert bold == {('r1', 'r2'), ('r2', 'r3'), ('r3', 'r4')}
    assert by_key(atoms)['r0']['element'] == 'O'


def test_haworth_groups_go_straight_up_or_down():
    atoms, bonds = projections.haworth(glucopyranose())
    keyed = by_key(atoms)
    for bond in bonds:
        if bond['b'].startswith('s'):
            ring_atom, group = keyed[bond['a']], keyed[bond['b']]
            assert group['x'] == ring_atom['x']
    # C1's OH is up (smaller y), C2's down.
    c1_oh = next(a for a in atoms if a.get('label') == 'OH' and a['x'] == keyed['r1']['x'])
    assert c1_oh['y'] < keyed['r1']['y']


def test_a_furanose():
    answer = {'ringSize': 5, 'ring': ['o', 'c1', 'c2', 'c3', 'c4'], 'substituents': []}
    atoms, bonds = projections.haworth(answer)
    assert len(atoms) == 5
    assert {(b['a'], b['b']) for b in bonds if b['stereo'] == 'UpOrDown'} == {('r1', 'r2'), ('r2', 'r3'), ('r3', 'r4')}
