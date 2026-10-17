"""The card's answer: its shape (Molion refuses what it cannot draw), links and copy lines."""

import copy
import re

from nmr import card


def answer(table, raw, *names, scope='selection', focus=None):
    structures = [copy.deepcopy(raw[n]) for n in names]
    if focus is not None:
        structures[0]['focus'] = focus
    return card.answer({'cardId': 'nmr', 'scope': scope, 'structures': structures}, table)


def peaks(view):
    return next(b for b in view['blocks'] if b['type'] == 'spectrum')['peaks']


def test_two_views_with_linked_peaks(table, raw):
    result = answer(table, raw, 'ethyl acetate')
    proton, carbon = result['views']
    assert (proton['id'], proton['label'], carbon['id'], carbon['label']) == ('1h', '¹H', '13c', '¹³C')
    assert len(peaks(proton)) == 3 and len(peaks(carbon)) == 4
    ids = {a['id'] for a in raw['ethyl acetate']['atoms']}
    for view in result['views']:
        links = [p['link'] for p in peaks(view)]
        assert len(links) == len(set(links))
        for peak in peaks(view):
            assert peak['atoms'] and set(peak['atoms']) <= ids
            assert peak['height'] > 0
    axis = next(b for b in proton['blocks'] if b['type'] == 'spectrum')['axis']
    assert axis['reversed'] and axis['min'] < axis['max']


def test_heights_are_hydrogens_and_lines_follow_them(table, raw):
    proton = answer(table, raw, 'ethyl acetate')['views'][0]
    quartet = next(p for p in peaks(proton) if p['readout'].split(' · ')[1].startswith('q'))
    assert quartet['height'] == 2
    assert len(quartet['lines']) == 4
    assert sum(i for _, i in quartet['lines']) == quartet['height']


def test_equivalent_atoms_are_one_peak(table, raw):
    proton = answer(table, raw, 'benzene')['views'][0]
    peak, = peaks(proton)
    assert peak['height'] == 6 and len(peak['atoms']) == 6


def test_copy_lines_read_like_an_si(table, raw):
    proton, carbon = answer(table, raw, 'ethyl acetate')['views']
    assert proton['copy'].startswith('¹H NMR (400 MHz, predicted) δ ')
    assert re.search(r'\d\.\d\d \(q, J = 7\.0 Hz, 2H\)', proton['copy'])
    assert carbon['copy'].startswith('¹³C NMR (101 MHz, predicted) δ ')
    values = [float(v) for v in carbon['copy'].split('δ ')[1].rstrip('.').split(', ')]
    assert values == sorted(values, reverse=True)


def test_a_selection_shows_only_its_peaks(table, raw):
    methylene = next(a['id'] for a in raw['ethyl acetate']['atoms'] if a['hydrogens'] == 2)
    proton, carbon = answer(table, raw, 'ethyl acetate', focus=[methylene])['views']
    assert [p['atoms'] for p in peaks(proton)] == [[methylene]]
    assert [p['atoms'] for p in peaks(carbon)] == [[methylene]]


def test_the_whole_document_of_several_asks_for_one(table, raw):
    result = answer(table, raw, 'toluene', 'benzene', scope='document')
    assert 'views' not in result and 'Select a structure' in result['message']


def test_a_selection_of_several_is_a_mixture(table, raw):
    result = answer(table, raw, 'toluene', 'benzene')
    links = [p['link'] for p in peaks(result['views'][0])]
    assert len(links) == len(set(links)) == 5


def test_a_structure_the_server_could_not_read(table):
    result = card.answer({'scope': 'selection', 'structures': [{'error': 'Some atoms have impossible valences'}]}, table)
    assert result['message'] == "Can't predict: Some atoms have impossible valences"


def test_labels_light_their_label_atom(table):
    # OMe drawn as a label: the expanded C has no id and names the label's atom.
    structure = {'atoms': [
        {'id': 'ring', 'element': 'C', 'hydrogens': 3},
        {'id': 'label', 'element': 'O', 'hydrogens': 0},
        {'origin': 'label', 'element': 'C', 'hydrogens': 3},
    ], 'bonds': [{'atoms': [0, 1], 'order': 1}, {'atoms': [1, 2], 'order': 1}]}
    result = card.answer({'scope': 'selection', 'structures': [structure]}, table)
    linked = sorted(a for p in peaks(result['views'][0]) for a in p['atoms'])
    assert linked == ['label', 'ring']


def test_the_data_is_credited(table, raw):
    notes = [b['text'] for b in answer(table, raw, 'toluene')['views'][0]['blocks'] if b['type'] == 'note']
    assert card.DATA_NOTE in notes
