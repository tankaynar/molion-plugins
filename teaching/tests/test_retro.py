"""Retrosynthetic Disconnect's options and its mark."""

from teaching import retro


def answer(positive, negative, smiles):
    return {'polarity': [{'bond': ['c', 'o'], 'positive': positive, 'negative': negative}],
            'fragments': [{'smiles': s, 'molblock': '', 'atoms': []} for s in smiles]}


def test_options_name_the_charged_ends():
    elements = {'c': 'C', 'o': 'O'}
    offered = retro.options([('heterolytic', answer('c', 'o', ['C[C+]=O', 'C[O-]'])),
                             ('heterolytic', answer('o', 'c', ['C[C-]=O', 'C[O+]'])),
                             ('homolytic', answer(None, None, ['C[C]=O', 'C[O]']))], elements)
    assert [o['label'] for o in offered] == ['C⁺ and O⁻', 'O⁺ and C⁻',
                                             'C• and O• (radicals)']


def test_an_option_without_synthons_is_left_out():
    offered = retro.options([('heterolytic', {'polarity': [], 'fragments': []})], {})
    assert offered == []


def test_the_mark_crosses_the_bond():
    mark = retro.bond_mark({'x': 0, 'y': 0}, {'x': 10, 'y': 0})
    assert (mark['x'], mark['y'], mark['rotation']) == (5, 0, 90)
    assert retro.wavy()['ops']
