"""main.py as Molion runs it: the calls each contribution makes, and what it answers."""

import copy
import json
import subprocess
import sys

from conftest import IBUPROFEN, ROOT, FakeMolion, Refuse

import main
from si.rpc import Host


def run(molion, *requests):
    queue = [json.dumps(request) for request in requests]

    def readline():
        if molion.pending():
            return molion.readline()
        return queue.pop(0) + '\n' if queue else ''
    main.serve(Host(readline, molion.write))
    return molion


def request(method, params, request_id=5):
    return {'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params}


def invoke(contribution, result=None):
    params = {'contributionId': contribution, 'kind': 'command', 'context': {}}
    if result is not None:
        params['result'] = {'id': result}
    return request('invoke', params)


def query(text=''):
    return request('query', {'contributionId': 'copy-hrms', 'text': text})


def final(molion, request_id=5):
    return [reply for reply in molion.replies if reply.get('id') == request_id][-1]['result']


def molecule(molecule_id, atom, number=None):
    found = {'id': molecule_id, 'atoms': [{'id': atom}], 'bonds': []}
    if number:
        found['number'] = {'mode': 'auto', 'text': number}
    return found


def analysis(params):
    structures = []
    for molecule_id in params['payload']['moleculeIds']:
        structure = copy.deepcopy(IBUPROFEN)
        structure['moleculeId'] = molecule_id
        structures.append(structure)
    return {'documentId': 'd', 'scope': 'atoms', 'empty': None, 'structures': structures}


def strings(params):
    payload = params['payload']
    if 'name' in payload['targets'] and NAMES_FAIL:
        raise Refuse('the namer could not start')
    return {'documentId': 'd', 'molecules': [
        dict({'moleculeId': i, 'smiles': f'S{i}', 'inchi': f'I{i}', 'error': None},
             **({'name': f'name of {i}'} if 'name' in payload['targets'] else {}))
        for i in payload['moleculeIds']]}


NAMES_FAIL = False


def drawing(selection=None, molecules=None):
    return FakeMolion({
        'scene:get-molecules': molecules if molecules is not None else [molecule('m1', 'a1', '2'), molecule('m2', 'a2', '1')],
        'scene:get-selection': {'atoms': selection or [], 'bonds': []},
        'scene:get-analysis': analysis,
        'scene:get-strings': strings,
        'clipboard': None,
        'saveFile': {'cancelled': False, 'name': 'si-stub.csv', 'path': '/x/si-stub.csv'},
    })


def test_initialize_names_the_plugin():
    molion = run(FakeMolion(), request('initialize', {}, 1))
    assert final(molion, 1)['name'] == 'SI Toolkit'


def test_the_adducts_are_listed_as_the_search_opens():
    molion = run(drawing(selection=['a1']), query())
    rows = final(molion)['results']
    assert rows[0] == {'id': 'esi-mh', 'title': '[M+H]⁺', 'section': 'ESI', 'subtitle': 'm/z 207.1380 · C₁₃H₁₉O₂'}
    assert {r['id'] for r in rows} >= {'esi-mna', 'esi-m-h', 'ei-m'}


def test_typing_filters_the_adducts():
    rows = final(run(drawing(), query('na')))['results']
    assert [r['id'] for r in rows] == ['esi-mna']
    assert [r['id'] for r in final(run(drawing(), query('m-h')))['results']] == ['esi-m-h']
    assert [r['id'] for r in final(run(drawing(), query('[M+NH4]+')))['results']] == ['esi-mnh4']
    assert {r['id'] for r in final(run(drawing(), query('neg')))['results']} == {'esi-m-h', 'esi-mcl'}
    assert final(run(drawing(), query('xyz'))) == {'results': [], 'message': 'No adduct matches.'}


def test_several_structures_get_a_line_each():
    molion = run(drawing(), dict(query('na'), id=4), invoke('copy-hrms', 'esi-mna'))
    assert final(molion, 4)['results'][0]['subtitle'] == 'One line for each of 2 structures'
    [copied] = molion.calls('clipboard')
    assert copied['text'].count('[M+Na]⁺ calcd for C₁₃H₁₈NaO₂ 229.1199, found ') == 2
    assert final(molion)['message'] == 'Copied 2 HRMS lines'


def test_the_adduct_chosen_comes_first_next_time(tmp_path):
    molion = run(drawing(), request('initialize', {'dataDir': str(tmp_path)}, 1),
                 invoke('copy-hrms', 'esi-mna'))
    assert final(molion)['ok'] is True
    molion = run(drawing(), request('initialize', {'dataDir': str(tmp_path)}, 1), query())
    assert final(molion)['results'][0]['id'] == 'esi-mna'


def test_with_nothing_drawn_there_is_nothing_to_copy():
    molion = run(drawing(molecules=[]), query(), invoke('copy-elemental'))
    assert final(molion) == {'ok': False, 'error': 'Draw a structure first.'}
    assert molion.calls('clipboard') == []


def test_copy_elemental_analysis_of_the_selection():
    molion = run(drawing(selection=['a2']), invoke('copy-elemental'))
    [asked] = molion.calls('scene:get-analysis')
    assert asked['payload'] == {'moleculeIds': ['m2']}
    [copied] = molion.calls('clipboard')
    assert copied['text'] == 'Anal. Calcd for C₁₃H₁₈O₂: C, 75.69; H, 8.80'


def test_the_stub_lists_every_compound_in_number_order():
    molion = run(drawing(selection=['a1']), invoke('copy-stub'))
    [copied] = molion.calls('clipboard')
    blocks = copied['text'].split('\n\n')
    assert blocks[0].startswith('1: name of m2\n')
    assert blocks[1].startswith('2: name of m1\n')
    assert final(molion)['message'] == 'Copied the SI stub for 2 compounds'


def test_the_stub_goes_without_names_when_the_namer_cannot_run():
    global NAMES_FAIL
    NAMES_FAIL = True
    try:
        molion = run(drawing(), invoke('copy-stub'))
    finally:
        NAMES_FAIL = False
    [copied] = molion.calls('clipboard')
    assert copied['text'].startswith('1\nC₁₃H₁₈O₂; HRMS')


def test_export_saves_a_csv():
    molion = run(drawing(), invoke('export-stub'))
    [saved] = molion.calls('saveFile')
    assert (saved['extension'], saved['suggestedName']) == ('csv', 'si-stub.csv')
    assert saved['content'].splitlines()[1].startswith('1,name of m2,C13H18O2,ESI,[M+H]⁺,207.1380,Sm2,Im2')
    assert final(molion) == {'ok': True, 'message': 'Saved si-stub.csv'}


def test_a_cancelled_export_is_not_an_error():
    molion = drawing()
    molion.answers['saveFile'] = {'cancelled': True}
    assert final(run(molion, invoke('export-stub'))) == {'ok': True}


def test_the_card_shows_each_view_with_its_copy(tmp_path):
    # The adduct copied last does not reach the card: the card would show it only once
    # the drawing next changed.
    molion = run(drawing(), request('initialize', {'dataDir': str(tmp_path)}, 1),
                 dict(invoke('copy-hrms', 'esi-mk'), id=4),
                 request('card', {'cardId': 'si', 'scope': 'selection', 'structures': [{'moleculeId': 'm1'}]}))
    answer = final(molion)
    assert [(v['id'], v['label']) for v in answer['views']] == [
        ('mh', '[M+H]⁺'), ('mna', '[M+Na]⁺'), ('anal', 'Anal.'), ('stub', 'SI')]
    mh_view, mna_view, anal_view, stub_view = answer['views']
    assert mh_view['copy'] == 'HRMS (ESI) m/z: [M+H]⁺ calcd for C₁₃H₁₉O₂ 207.1380, found '
    assert '229.1199' in mna_view['copy']
    assert mh_view['blocks'] == [{'type': 'note', 'label': '2',
                                  'text': 'HRMS (ESI) m/z: [M+H]⁺ calcd for C₁₃H₁₉O₂ 207.1380'}]
    assert anal_view['blocks'] == [{'type': 'note', 'label': '2', 'text': 'Anal. Calcd for C₁₃H₁₈O₂: C, 75.69; H, 8.80'}]
    assert stub_view['copy'] == '2\nC₁₃H₁₈O₂\nSMILES: Sm1\nInChI: Im1\n'
    assert stub_view['blocks'] == [{'type': 'note', 'label': '2', 'text': 'C₁₃H₁₈O₂ · Sm1'}]
    assert answer['subtitle'] == 'Calculated'
    # The card never waits on the namer.
    assert all('name' not in c['payload']['targets'] for c in molion.calls('scene:get-strings'))
    assert len(molion.calls('clipboard')) == 1      # the invoke's; a card never copies


def test_every_card_string_fits():
    many = [molecule(f'm{i}', f'a{i}', str(i)) for i in range(15)]
    molion = drawing(molecules=many)
    answer = final(run(molion, request('card', {'cardId': 'si', 'scope': 'document',
                                                 'structures': [{'moleculeId': m['id']} for m in many]})))
    for view in answer['views']:
        assert len(view['blocks']) <= 10
        assert all(len(block['text']) <= 200 for block in view['blocks'])
        assert len(view.get('copy', '')) <= 8000


def test_runs_as_a_process():
    process = subprocess.run([sys.executable, 'main.py'], cwd=ROOT, capture_output=True, text=True, timeout=30,
                             input=json.dumps(request('initialize', {}, 1)) + '\n')
    assert json.loads(process.stdout.splitlines()[0])['result']['name'] == 'SI Toolkit'


def test_a_stub_without_names_says_why():
    molion = drawing()

    def unnamed(params):
        reply = strings(dict(params, payload=dict(params['payload'], targets=['smiles', 'inchi'])))
        for found in reply['molecules']:
            found['nameError'] = 'Names cannot be checked: the namer is not built.'
        return reply
    molion.answers['scene:get-strings'] = unnamed
    assert final(run(molion, invoke('copy-stub')))['message'] == (
        'Copied the SI stub for 2 compounds, without names (Names cannot be checked: the namer is not built)')


def test_several_structures_on_the_card_are_told_apart_by_number_or_formula():
    molion = drawing(molecules=[molecule('m1', 'a1', '10'), molecule('m2', 'a2'), molecule('m3', 'a3', '2')])
    answer = final(run(molion, request('card', {'cardId': 'si', 'scope': 'document', 'structures': [
        {'moleculeId': 'm1'}, {'moleculeId': 'm2'}, {'moleculeId': 'm3'}]})))
    # Numbered first, in number order.
    assert [block['label'] for block in answer['views'][0]['blocks']] == ['2', '10', 'C₁₃H₁₈O₂']
    assert answer['views'][3]['blocks'][2] == {'type': 'note', 'label': 'C₁₃H₁₈O₂', 'text': 'Sm2'}
    assert answer['subtitle'] == 'Calculated for 3 structures'
