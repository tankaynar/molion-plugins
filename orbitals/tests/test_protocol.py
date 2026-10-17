"""main.py as Molion runs it: tools and commands place orbitals; actions edit them."""

import json
import subprocess
import sys

from conftest import ROOT, FakeMolion, orbital_image

import main
from orbitals import drawing, model
from orbitals.rpc import Host


def run(molion, *requests):
    queue = [json.dumps(request) for request in requests]

    def readline():
        if molion.pending():
            return molion.readline()
        return queue.pop(0) + '\n' if queue else ''
    main.serve(Host(readline, molion.write))
    return molion


def invoke(contribution, kind='action', images=('orbital-1',), gesture=None):
    params = {'contributionId': contribution, 'kind': kind, 'context': {'images': list(images)}}
    if gesture is not None:
        params['gesture'] = gesture
    return {'jsonrpc': '2.0', 'id': 5, 'method': 'invoke', 'params': params}


def final(molion):
    return [reply for reply in molion.replies if reply.get('id') == 5][-1]


def test_initialize_names_the_plugin():
    molion = run(FakeMolion(), {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}})
    assert molion.replies[0]['result']['name'] == 'Orbitals'


def test_a_click_on_an_atom_puts_the_orbital_on_it_upright():
    gesture = {'cancelled': False, 'kind': 'vector', 'start': {'x': 5, 'y': 6}, 'end': {'x': 5, 'y': 6},
               'length': 0, 'angleDegrees': 0, 'startAtom': {'id': 'a1', 'x': 50, 'y': 60}}
    molion = run(FakeMolion(), invoke('tool-p', kind='tool', images=(), gesture=gesture))
    [added] = molion.calls('scene:add-image')
    payload = added['payload']
    assert (payload['x'], payload['y']) == (50, 60)
    assert payload['locks'] == ['replace', 'crop', 'rotate']
    assert model.load(payload['pluginData'])['angle'] == -90
    assert final(molion)['result']['ok'] is True


def test_a_drag_aims_the_orbital():
    gesture = {'cancelled': False, 'kind': 'vector', 'start': {'x': 0, 'y': 0}, 'end': {'x': 0, 'y': 40},
               'length': 40, 'angleDegrees': 90}
    molion = run(FakeMolion(), invoke('tool-sp3', kind='tool', images=(), gesture=gesture))
    [added] = molion.calls('scene:add-image')
    assert model.load(added['payload']['pluginData'])['angle'] == 90


def test_a_place_command_asks_for_a_clickable_gesture_with_a_preview():
    answers = {'gesture': {'cancelled': True, 'reason': 'escape'}}
    molion = run(FakeMolion(answers), invoke('place-dz2', kind='command', images=()))
    [asked] = molion.calls('gesture')
    assert asked['kind'] == 'vector' and asked['click'] is True
    assert asked['preview']['ops'][0]['origin'] == 'start'
    assert molion.calls('scene:add-image') == []


def test_an_action_without_an_orbital_says_so():
    molion = run(FakeMolion(), invoke('flip-phase', images=()))
    assert final(molion)['result'] == {'ok': False, 'error': 'Select one orbital first.'}


def test_rotate_keeps_the_size_the_user_gave_it():
    orbital = model.new_orbital('p')
    image = orbital_image(orbital, height=drawing.drawing(orbital)['height'] * 2)
    molion = run(FakeMolion({'scene:get-image': image}), invoke('rotate-90'))
    [updated] = molion.calls('scene:update-image')
    payload = updated['payload']
    turned = model.load(payload['pluginData'])
    assert turned['angle'] == 0
    assert payload['height'] == drawing.drawing(turned)['height'] * 2


def test_edit_serves_the_dialog_then_saves_once():
    events = [{'jsonrpc': '2.0', 'id': 90, 'method': 'dialogEvent',
               'params': {'event': {'type': 'change', 'field': 'type', 'value': 'sp2'}}}]
    answers = {'scene:get-image': orbital_image(), 'dialog': {'cancelled': False, 'values': {}}}
    molion = run(FakeMolion(answers, inbound={'dialog': events}), invoke('edit'))
    [reply] = [r for r in molion.replies if r.get('id') == 90]
    assert 'picture' in reply['result']
    [updated] = molion.calls('scene:update-image')
    assert model.load(updated['payload']['pluginData'])['type'] == 'sp2'


def test_a_cancelled_edit_changes_nothing():
    answers = {'scene:get-image': orbital_image(), 'dialog': {'cancelled': True, 'reason': 'escape'}}
    molion = run(FakeMolion(answers), invoke('edit'))
    assert molion.calls('scene:update-image') == []


def test_runs_as_a_process():
    process = subprocess.run([sys.executable, 'main.py'], cwd=ROOT, capture_output=True, text=True, timeout=30,
                             input=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}) + '\n')
    assert json.loads(process.stdout.splitlines()[0])['result']['name'] == 'Orbitals'
