"""Calculated shifts through Molion's `calculate`: what the card shows in each state, and the
action that starts one. Molion is a stub here; its side is tested in Molion's own suite."""

import copy
import io
import json

from nmr import calculated, card
from nmr.host import Host, HostError

import main


class StubHost:
    """Answers `calculate` with `reply`, `scene` with `structures`, and records the calls."""

    def __init__(self, reply=None, structures=None, refuse=None):
        self.reply = reply or {'state': 'none'}
        self.structures = structures
        self.refuse = refuse
        self.calls = []

    def call(self, method, params):
        self.calls.append((method, params))
        if self.refuse:
            raise HostError(self.refuse)
        return self.structures if method == 'scene' else self.reply


def structure(raw, name):
    entry = copy.deepcopy(raw[name])
    entry['moleculeId'] = 'm1'
    return entry


def done_reply(entry, carbon=None, proton=None):
    """A done answer for `entry`, as Molion maps it: every drawn atom's index, then each heavy
    atom's implicit hydrogens after them, with shifts given per element by `carbon`/`proton`."""
    atoms, shifts = [], []
    for index, atom in enumerate(entry['atoms']):
        shifts.append(carbon(atom) if carbon and atom['element'] == 'C' else None)
        atoms.append({'id': atom['id'], 'index': index, 'hydrogens': []})
    for index, atom in enumerate(entry['atoms']):
        for _ in range(atom.get('hydrogens') or 0):
            atoms[index]['hydrogens'].append(len(shifts))
            shifts.append(proton(atom) if proton else None)
    return {'state': 'done', 'methodLine': 'TPSS/pcSseg-1//r2SCAN-3c (ORCA), gas phase',
            'result': {'shifts_ppm': shifts}, 'atoms': atoms}


def answer(table, entry, host):
    return card.answer({'cardId': 'nmr', 'documentId': 'doc', 'scope': 'selection',
                        'structures': [entry]}, table, host)


def blocks(view, kind):
    return [b for b in view['blocks'] if b['type'] == kind]


def positions(view):
    return sorted(p['position'] for p in blocks(view, 'spectrum')[0]['peaks'])


def test_the_card_asks_without_starting(table, raw):
    host = StubHost()
    answer(table, structure(raw, 'propan-1-ol'), host)
    assert host.calls == [('calculate', {'documentId': 'doc', 'moleculeId': 'm1',
                                         'kind': 'orca.nmr', 'start': False})]


def test_nothing_calculated_offers_the_button(table, raw):
    result = answer(table, structure(raw, 'propan-1-ol'), StubHost({'state': 'none'}))
    assert result['subtitle'] == 'Predicted'
    for view in result['views']:
        assert blocks(view, 'button') == [{'type': 'button', 'label': 'Calculate NMR with ORCA',
                                           'action': 'calculate-orca'}]


def test_running_shows_the_prediction_without_the_button(table, raw):
    # Molion draws the job's progress in the card itself
    result = answer(table, structure(raw, 'propan-1-ol'), StubHost({'state': 'running', 'progress': 0.4}))
    assert result['subtitle'] == 'Predicted'
    assert not blocks(result['views'][0], 'button')


def test_without_orca_the_card_is_as_it_was(table, raw):
    entry = structure(raw, 'propan-1-ol')
    unavailable = answer(table, entry, StubHost({'state': 'unavailable', 'message': 'ORCA is not set up'}))
    refused = answer(table, entry, StubHost(refuse="did not declare the 'orca' capability"))
    plain = answer(table, entry, None)
    assert unavailable == refused == plain
    assert not blocks(plain['views'][0], 'button')


def test_a_failure_says_why_and_offers_again(table, raw):
    result = answer(table, structure(raw, 'propan-1-ol'), StubHost({'state': 'failed', 'message': 'SCF did not converge'}))
    view = result['views'][0]
    assert any('SCF did not converge' in n['text'] for n in blocks(view, 'note'))
    assert blocks(view, 'button')


def test_done_shows_calculated_shifts_averaged_per_class(table, raw):
    entry = structure(raw, 'propan-1-ol')
    carbons = {a['id']: 10.0 * (i + 1) for i, a in enumerate(entry['atoms'])}
    reply = done_reply(entry, carbon=lambda a: carbons[a['id']], proton=lambda a: carbons[a['id']] / 10)
    result = answer(table, entry, StubHost(reply))

    assert result['subtitle'] == 'Calculated'
    proton, carbon = result['views']
    expected = sorted(carbons[a['id']] for a in entry['atoms'] if a['element'] == 'C')
    assert positions(carbon) == expected
    assert positions(proton) == sorted(round(carbons[a['id']] / 10, 3) for a in entry['atoms'] if a['hydrogens'])
    assert 'calculated' in carbon['copy'] and 'predicted' not in carbon['copy']
    notes = [n['text'] for n in blocks(proton, 'note')]
    assert 'Calculated with TPSS/pcSseg-1//r2SCAN-3c (ORCA), gas phase.' in notes
    assert card.DATA_NOTE not in notes
    assert not blocks(proton, 'button')


def test_a_shift_the_calculation_lacks_stays_predicted_and_says_so(table, raw):
    entry = structure(raw, 'propan-1-ol')
    # Carbons calculated, hydrogens not: the ¹H peaks are the table's, and labelled so
    reply = done_reply(entry, carbon=lambda a: 50.0)
    proton, carbon = answer(table, entry, StubHost(reply))['views']
    assert all(p['readout'].endswith('predicted') for p in blocks(proton, 'spectrum')[0]['peaks'])
    assert 'predicted' in proton['copy'] and card.DATA_NOTE in [n['text'] for n in blocks(proton, 'note')]
    assert 'calculated' in carbon['copy']


def test_a_class_averages_its_atoms(raw):
    entry = structure(raw, 'benzene')
    atoms = calculated.ask(StubHost(done_reply(entry, carbon=lambda a: 128.0 + int(a['id'][1:]),
                                               proton=lambda a: 7.0)), 'doc', 'm1')
    from nmr.structure import read
    group = read(entry).heavy_atoms
    assert abs(calculated.carbon_shift(atoms, group) - (128.0 + sum(range(6)) / 6)) < 1e-9
    assert calculated.proton_shift(atoms, group) == 7.0


# ── The action ───────────────────────────────────────────────────────────

def test_the_action_starts_each_molecule(raw):
    structures = {'documentId': 'doc', 'structures': [{'moleculeId': 'm1'}, {'moleculeId': 'm2'},
                                                      {'moleculeId': 'm3', 'error': 'valence'}]}
    host = StubHost({'state': 'queued'}, structures)
    result = main.calculate(host, {'context': {'atoms': ['a0'], 'isEmpty': False}})
    assert result == {'ok': True}
    assert host.calls[0] == ('scene', {'operation': 'get-structure', 'payload': {'selection': True}})
    assert [p['moleculeId'] for m, p in host.calls[1:]] == ['m1', 'm2']
    assert all(p['start'] for _, p in host.calls[1:])


def test_the_action_with_nothing_selected_takes_the_drawing():
    host = StubHost({'state': 'queued'}, {'documentId': 'doc', 'structures': [{'moleculeId': 'm1'}]})
    assert main.calculate(host, {'context': {'atoms': [], 'isEmpty': True}}) == {'ok': True}
    assert host.calls[0][1]['payload'] == {}


def test_the_action_reports_why_it_cannot():
    host = StubHost({'state': 'unavailable', 'message': 'ORCA is not set up'},
                    {'documentId': 'doc', 'structures': [{'moleculeId': 'm1'}]})
    assert main.calculate(host, {'context': {}}) == {'ok': False, 'error': 'ORCA is not set up'}
    empty = StubHost(structures={'documentId': 'doc', 'structures': [], 'empty': 'No atoms in the selection.'})
    assert main.calculate(empty, {'context': {}}) == {'ok': False, 'error': 'No atoms in the selection.'}


# ── The channel ──────────────────────────────────────────────────────────

def test_a_call_waits_for_its_own_answer():
    incoming = io.StringIO(
        json.dumps({'jsonrpc': '2.0', 'method': 'toast', 'params': {}}) + '\n'
        + json.dumps({'jsonrpc': '2.0', 'id': 7, 'method': 'card', 'params': {}}) + '\n'
        + json.dumps({'jsonrpc': '2.0', 'id': 1000001, 'result': {'state': 'none'}}) + '\n')
    outgoing = io.StringIO()
    host = Host(incoming, outgoing)
    assert host.call('calculate', {}) == {'state': 'none'}
    sent = [json.loads(line) for line in outgoing.getvalue().splitlines()]
    assert sent[0]['method'] == 'calculate'
    assert sent[1]['id'] == 7 and 'error' in sent[1]        # never left hanging
