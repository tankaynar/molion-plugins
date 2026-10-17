"""main.py as Molion runs it: requests in, calls out, and the dialog's events served mid-call."""

import json
import os
import subprocess
import sys

from conftest import ROOT, FakeMolion, plate_image

import main
from tlc import drawing, model
from tlc.rpc import Host


def run(molion, *requests):
    """Serves `requests` in order; the fake's answers to the plugin's calls come first."""
    queue = [json.dumps(request) for request in requests]

    def readline():
        if molion.pending():
            return molion.readline()
        return queue.pop(0) + '\n' if queue else ''
    main.serve(Host(readline, molion.write))
    return molion


def invoke(contribution, images=('plate-1',), result=None, id=5):
    params = {'contributionId': contribution, 'kind': 'action', 'context': {'images': list(images)}}
    if result is not None:
        params['result'] = {'id': result}
    return {'jsonrpc': '2.0', 'id': id, 'method': 'invoke', 'params': params}


def final(molion):
    return [reply for reply in molion.replies if reply.get('id') == 5][-1]


def test_initialize_names_the_plugin():
    molion = run(FakeMolion(), {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}})
    assert molion.replies[0]['result']['name'] == 'TLC Plate'


def test_new_plate_places_a_locked_plate_where_the_user_clicked():
    molion = run(FakeMolion({'gesture': {'cancelled': False, 'point': {'x': 10, 'y': 20}}}),
                 {'jsonrpc': '2.0', 'id': 5, 'method': 'invoke', 'params': {'contributionId': 'new-plate'}})
    [added] = molion.calls('scene:add-image')
    assert (added['payload']['x'], added['payload']['y']) == (10, 20)
    assert added['payload']['locks'] == ['replace', 'resize', 'opacity']
    assert model.load(added['payload']['pluginData']) == model.new_plate()
    assert final(molion)['result']['ok'] is True


def test_an_action_without_a_plate_says_so():
    molion = run(FakeMolion(), invoke('add-lane', images=()))
    assert final(molion)['result'] == {'ok': False, 'error': 'Select one TLC plate first.'}


def test_edit_serves_the_dialogs_events_then_saves_once_at_the_placed_scale():
    plate = model.new_plate()
    image = plate_image(plate, height=drawing.height(plate) * 2)
    click = {'jsonrpc': '2.0', 'id': 900, 'method': 'dialogEvent', 'params': {
        'event': {'type': 'click', 'point': [drawing.lane_x(0), drawing.spot_y(0.5)], 'double': False},
        'values': {}}}
    molion = run(FakeMolion({'scene:get-image': image, 'dialog': {'cancelled': False, 'values': {}}},
                            inbound={'dialog': [click]}),
                 invoke('edit'))
    [request] = molion.calls('dialog')
    assert request['title'] == 'Edit TLC Plate'
    event_reply = next(reply for reply in molion.replies if reply['id'] == 900)
    assert 'picture' in event_reply['result'] and 'fields' in event_reply['result']
    [saved] = molion.calls('scene:update-image')
    after = model.load(saved['payload']['pluginData'])
    assert after['lanes'][0]['spots'][0]['rf'] == 0.5
    assert saved['payload']['height'] == drawing.height(after) * 2
    assert final(molion)['result']['ok'] is True


def test_a_cancelled_edit_changes_nothing():
    molion = run(FakeMolion({'scene:get-image': plate_image(), 'dialog': {'cancelled': True, 'reason': 'escape'}}),
                 invoke('edit'))
    assert molion.calls('scene:update-image') == []


def test_a_failing_event_handler_is_an_error_reply_and_the_dialog_stays():
    bad = {'jsonrpc': '2.0', 'id': 901, 'method': 'dialogEvent', 'params': {'event': {'type': 'click', 'point': 'x'}}}
    molion = run(FakeMolion({'scene:get-image': plate_image(), 'dialog': {'cancelled': True}},
                            inbound={'dialog': [bad]}),
                 invoke('edit'))
    reply = next(reply for reply in molion.replies if reply['id'] == 901)
    assert 'error' in reply


def test_two_step_actions_apply_the_chosen_row():
    for contribution, row, check in [
        ('set-stain', 'kmno4', lambda p: p['stain'] == 'kmno4'),
        ('set-eluent', 'eluent:5% MeOH/DCM', lambda p: p['eluent'] == '5% MeOH/DCM'),
        ('label-lanes', 'labels:["A", "B", "C", "D"]', lambda p: [l['label'] for l in p['lanes']] == ['A', 'B', 'C', 'D']),
        ('toggle-rf', None, lambda p: p['showRf'] is True),
        ('add-cospot', None, lambda p: p['lanes'][-1]['cospot'] == [0, 2]),
        ('remove-lane', None, lambda p: len(p['lanes']) == 2),
    ]:
        molion = run(FakeMolion({'scene:get-image': plate_image()}), invoke(contribution, result=row))
        [saved] = molion.calls('scene:update-image')
        assert check(model.load(saved['payload']['pluginData'])), contribution


def query(contribution, text):
    return {'jsonrpc': '2.0', 'id': 7, 'method': 'query', 'params': {
        'contributionId': contribution, 'text': text, 'kind': 'action', 'context': {'images': ['plate-1']}}}


def test_the_searches_answer_rows():
    molion = run(FakeMolion(), query('set-stain', 'perm'), query('set-eluent', 'meoh'), query('label-lanes', 'SM, P'))
    stain_rows, eluent_rows, label_rows = (reply['result']['results'] for reply in molion.replies)
    assert [row['id'] for row in stain_rows] == ['kmno4']
    assert eluent_rows[0]['id'] == 'eluent:meoh'
    assert any(row['title'] == '5% MeOH/DCM' for row in eluent_rows)
    assert label_rows[0]['title'] == 'SM · P'
    assert all(len(row['title']) <= 200 for row in stain_rows + eluent_rows + label_rows)


def test_main_starts_and_answers_over_real_pipes():
    process = subprocess.run([sys.executable, os.path.join(ROOT, 'main.py')],
                             input=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}) + '\n',
                             capture_output=True, text=True, timeout=30)
    assert json.loads(process.stdout.splitlines()[0])['result']['protocolVersion'] == 1
