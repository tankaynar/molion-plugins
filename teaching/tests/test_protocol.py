"""main.py as Molion runs it: each contribution's calls to Molion."""

import json
import subprocess
import sys

from conftest import ROOT, FakeMolion

import main
from teaching import newman
from teaching.rpc import Host


def run(molion, *requests):
    queue = [json.dumps(request) for request in requests]

    def readline():
        if molion.pending():
            return molion.readline()
        return queue.pop(0) + '\n' if queue else ''
    main.serve(Host(readline, molion.write))
    return molion


def invoke(contribution, context=None, result=None, kind='action'):
    params = {'contributionId': contribution, 'kind': kind, 'context': context or {}}
    if result is not None:
        params['result'] = {'id': result}
    return {'jsonrpc': '2.0', 'id': 5, 'method': 'invoke', 'params': params}


def final(molion):
    return [reply for reply in molion.replies if reply.get('id') == 5][-1]['result']


def edit(result):
    return {'documentId': 'd', 'undoDepth': 1, 'result': result}


SOURCE = {'molecules': [{'id': 'm1', 'atoms': [{'id': 'a', 'x': 0, 'y': 0}, {'id': 'b', 'x': 50, 'y': 0}],
                         'bonds': [{'id': 'ab', 'atomA': 'a', 'atomB': 'b'}]}]}


def test_initialize_names_the_plugin():
    molion = run(FakeMolion(), {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}})
    assert molion.replies[0]['result']['name'] == 'Teaching'


def test_newman_places_its_picture_right_of_the_molecule():
    projection = {'moleculeId': 'm1', 'dihedral': 180, 'rotatable': True, 'warnings': [],
                  'front': {'atom': 'a', 'substituents': [{'atom': None, 'label': 'H', 'element': 'H', 'angle': 0}]},
                  'back': {'atom': 'b', 'substituents': [{'atom': None, 'label': 'H', 'element': 'H', 'angle': 180}]}}
    molion = run(FakeMolion({'scene:get-projection': projection, 'scene:get-scene': SOURCE,
                             'scene:add-image': edit({'id': 'img'})}),
                 invoke('newman', {'bonds': ['ab']}))
    [asked] = molion.calls('scene:get-projection')
    assert asked['payload'] == {'kind': 'newman', 'bondId': 'ab'}
    [added] = molion.calls('scene:add-image')
    assert added['payload']['x'] > 50
    assert newman.load(added['payload']['pluginData'])['dihedral'] == 180
    assert final(molion)['ok'] is True


def test_newman_needs_one_bond():
    molion = run(FakeMolion(), invoke('newman', {'atoms': ['a']}))
    assert final(molion)['ok'] is False


def test_fischer_draws_one_molecule_of_atoms_and_bonds():
    projection = {'moleculeId': 'm1', 'warnings': [],
                  'top': {'atom': None, 'label': 'CHO', 'element': 'C'},
                  'chain': [{'atom': 'x', 'left': {'atom': None, 'label': 'H', 'element': 'H'},
                             'right': {'atom': None, 'label': 'OH', 'element': 'O'}}],
                  'bottom': {'atom': None, 'label': 'CH2OH', 'element': 'C'}}
    counter = {'n': 0}

    def add_atom(params):
        counter['n'] += 1
        return edit({'id': f'new{counter["n"]}'})
    molion = run(FakeMolion({'scene:get-projection': projection, 'scene:get-scene': SOURCE,
                             'scene:add-atom': add_atom, 'scene:add-bond': edit({'id': 'b'})}),
                 invoke('fischer-wedges', {'atoms': ['a']}))
    atoms = molion.calls('scene:add-atom')
    assert len(atoms) == 5
    assert all(call['payload'].get('attachTo') == 'new1' for call in atoms[1:])
    assert {call['payload'].get('label') for call in atoms} == {'CHO', None, 'OH', 'CH2OH'}
    bonds = molion.calls('scene:add-bond')
    assert len(bonds) == 4
    assert sum(call['payload']['stereo'] == 'Up' for call in bonds) == 2


def test_a_projection_molion_refuses_is_said_as_its_message():
    # A refusal arrives as a JSON-RPC error, which FakeMolion does not send: answered here.
    molion = FakeMolion()

    def write(message):
        if message.get('method') == 'scene':
            molion._lines.append(json.dumps({'jsonrpc': '2.0', 'id': message['id'],
                                             'error': {'code': -32000, 'message': 'there is no open carbon chain'}}))
        elif 'method' not in message:
            molion.replies.append(message)
    queue = [json.dumps(invoke('fischer', {'atoms': ['a']}))]
    main.serve(Host(lambda: molion.readline() if molion.pending() else (queue.pop(0) + '\n' if queue else ''), write))
    assert molion.replies[-1]['result'] == {'ok': False, 'error': 'There is no open carbon chain'}


def test_mark_answer_takes_the_bonds_between_selected_atoms():
    molion = run(FakeMolion({'scene:get-scene': SOURCE, 'scene:set-marks': edit({'changed': 3})}),
                 invoke('mark-answer', {'atoms': ['a', 'b'], 'annotations': ['t']}))
    [marked] = molion.calls('scene:set-marks')
    assert marked['payload'] == {'key': 'answer', 'value': '1', 'atoms': ['a', 'b'], 'bonds': ['ab'], 'annotations': ['t']}


def test_unmark_answer_sends_null():
    molion = run(FakeMolion({'scene:set-marks': edit({'changed': 1})}), invoke('unmark-answer', {'annotations': ['t']}))
    [marked] = molion.calls('scene:set-marks')
    assert marked['payload']['value'] is None


def test_set_step_offers_the_typed_step_and_saves_it():
    molion = run(FakeMolion(), {'jsonrpc': '2.0', 'id': 7, 'method': 'query',
                                'params': {'contributionId': 'set-step', 'text': '2 Proton transfer'}})
    [row] = molion.replies[0]['result']['results']
    assert row['id'] == '2|Proton transfer'
    molion = run(FakeMolion({'scene:set-marks': edit({'changed': 1})}),
                 invoke('set-step', {'curvedArrows': ['c1']}, result=row['id']))
    [marked] = molion.calls('scene:set-marks')
    assert marked['payload'] == {'key': 'step', 'value': '2|Proton transfer', 'curvedArrows': ['c1']}


def test_present_mechanism_sends_the_plan_to_the_presenter():
    scene = {**SOURCE, 'arrows': [], 'annotations': [],
             'curvedArrows': [{'id': 'c1', 'source': {'kind': 'atom', 'id': 'a'}, 'target': {'kind': 'bond', 'id': 'ab'},
                               'from': {'x': 0, 'y': 0}}]}
    molion = run(FakeMolion({'scene:get-scene': scene, 'scene:get-marks': {'marks': []},
                             'present': {'ended': 'finished', 'step': 1}}),
                 invoke('present-mechanism', kind='command'))
    [shown] = molion.calls('present')
    assert shown['steps'] == [{'reveal': {}}, {'reveal': {'curvedArrows': ['c1']}}]
    assert final(molion)['ok'] is True


def test_disconnect_offers_each_cut_then_places_the_chosen_one():
    def fragments(params):
        payload = params['payload']
        if payload['mode'] == 'homolytic':
            return {'moleculeId': 'm1', 'polarity': [{'bond': ['a', 'b'], 'positive': None, 'negative': None}],
                    'fragments': [{'smiles': '[CH3]', 'molblock': 'M1', 'atoms': ['a']}, {'smiles': '[OH]', 'molblock': 'M2', 'atoms': ['b']}]}
        positive = (payload.get('positive') or ['a'])[0]
        negative = 'b' if positive == 'a' else 'a'
        return {'moleculeId': 'm1', 'polarity': [{'bond': ['a', 'b'], 'positive': positive, 'negative': negative}],
                'fragments': [{'smiles': 'X', 'molblock': 'M1', 'atoms': ['a']}, {'smiles': 'Y', 'molblock': 'M2', 'atoms': ['b']}]}
    placed = {'n': 0}

    def add_molfile(params):
        placed['n'] += 1
        x = params['payload']['x']
        return edit({'molecules': [{'id': f'f{placed["n"]}', 'atoms': [{'id': f'fa{placed["n"]}', 'x': x - 10, 'y': 0},
                                                                     {'id': f'fb{placed["n"]}', 'x': x + 10, 'y': 0}]}]})
    answers = {
        'scene:get-bond': {'id': 'ab', 'atomA': 'a', 'atomB': 'b'},
        'scene:get-atom': lambda params: {'id': params['payload']['atomId'], 'element': 'C' if params['payload']['atomId'] == 'a' else 'O',
                                          'x': 0 if params['payload']['atomId'] == 'a' else 50, 'y': 0},
        'scene:get-fragments': fragments, 'scene:get-scene': SOURCE,
        'dialog': {'cancelled': False, 'values': {'cut': '2'}},
        'scene:add-arrow': edit({'id': 'arrow'}), 'scene:add-annotation': edit({'id': 'plus'}),
        'scene:add-from-molfile': add_molfile, 'scene:move': edit(None),
        'scene:add-image': edit({'id': 'wavy'}), 'scene:group': edit({'id': 'g'}),
    }
    molion = run(FakeMolion(answers), invoke('disconnect', {'bonds': ['ab']}))
    [dialog] = molion.calls('dialog')
    options = dialog['fields'][0]['options']
    assert [o['label'] for o in options] == ['C⁺ and O⁻', 'O⁺ and C⁻', 'C• and O• (radicals)']
    [arrow] = molion.calls('scene:add-arrow')
    assert arrow['payload']['kind'] == 'Retro'
    assert [c['payload']['molfile'] for c in molion.calls('scene:add-from-molfile')] == ['M1', 'M2']
    [grouped] = molion.calls('scene:group')
    assert grouped['payload'] == {'atoms': ['a'], 'images': ['wavy']}
    assert final(molion)['ok'] is True


def test_runs_as_a_process():
    process = subprocess.run([sys.executable, 'main.py'], cwd=ROOT, capture_output=True, text=True, timeout=30,
                             input=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}) + '\n')
    assert json.loads(process.stdout.splitlines()[0])['result']['name'] == 'Teaching'
