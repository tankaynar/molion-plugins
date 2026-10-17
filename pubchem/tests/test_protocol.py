"""main.py as Molion runs it: JSON-RPC requests in, answers out. The network is faked, except
in the subprocess test, which sends nothing that would reach it."""

import json
import os
import subprocess
import sys
import urllib.error

from conftest import HEMIN_SMILES, ROOT, FakePubChem, offline

import main
from pubchem_search.plugin import BUSY, UNREACHABLE, PubChemPlugin


def ask(plugin, *messages):
    replies = []
    lines = [json.dumps(m) for m in messages]
    main.serve(lines, replies.append, plugin)
    return replies


def query(text, id=2):
    return {'jsonrpc': '2.0', 'id': id, 'method': 'query', 'params': {'contributionId': 'search', 'text': text}}


def invoke(cid, id=3):
    return {'jsonrpc': '2.0', 'id': id, 'method': 'invoke',
            'params': {'contributionId': 'search', 'kind': 'command', 'context': {}, 'result': {'id': cid}}}


def test_a_query_answers_rows_molion_can_show(heme_pubchem):
    [reply] = ask(PubChemPlugin(heme_pubchem), query('heme'))
    rows = reply['result']['results']
    assert rows[0]['id'] == '26945'
    assert rows[0]['title'] == 'Hemin'
    assert rows[0]['smiles'] == HEMIN_SMILES
    assert rows[0]['detail'].startswith('C34H32FeN4O4')
    assert 'CID 26945' in rows[0]['detail']
    assert all(len(row['title']) <= 200 for row in rows)


def test_a_repeated_query_asks_pubchem_nothing(heme_pubchem):
    plugin = PubChemPlugin(heme_pubchem)
    ask(plugin, query('heme'))
    calls = len(heme_pubchem.calls)
    ask(plugin, query('Heme '))
    assert len(heme_pubchem.calls) == calls


def test_a_short_query_sends_nothing():
    fake = FakePubChem({})
    [reply] = ask(PubChemPlugin(fake), query('h'))
    assert reply['result'] == {'results': []}
    assert fake.calls == []


def test_no_network_is_a_message_not_an_error():
    [reply] = ask(PubChemPlugin(offline), query('aspirin'))
    assert reply['result'] == {'results': [], 'message': UNREACHABLE}


def test_a_busy_pubchem_says_so():
    import io
    busy = urllib.error.HTTPError('u', 503, 'Busy', {}, io.BytesIO(b''))
    fake = FakePubChem({'/compound/name/': busy, '/autocomplete/': busy})
    [reply] = ask(PubChemPlugin(fake), query('aspirin'))
    assert reply['result']['message'] == BUSY


def test_choosing_a_row_answers_the_drawing_to_place(heme_pubchem):
    plugin = PubChemPlugin(heme_pubchem)
    _, reply = ask(plugin, query('heme'), invoke('26945'))
    place = reply['result']['place']
    assert reply['result']['ok'] is True
    assert place['hydrogens'] == 'fold'
    assert place['title'] == 'Hemin'
    assert 'Fe' in place['molfile'] and place['molfile'].rstrip().endswith('M  END')


def test_without_a_drawing_the_search_smiles_is_placed():
    fake = FakePubChem({'/property/': {'PropertyTable': {'Properties': [{'CID': 702, 'Title': 'Ethanol',
                                                                         'SMILES': 'CCO', 'MolecularWeight': '46.07'}]}}})
    plugin = PubChemPlugin(fake)
    _, reply = ask(plugin, query('702'), invoke('702'))
    assert reply['result'] == {'ok': True, 'place': {'smiles': 'CCO', 'title': 'Ethanol'}}


def test_an_invoke_without_a_row_is_refused_politely():
    [reply] = ask(PubChemPlugin(offline), {'jsonrpc': '2.0', 'id': 1, 'method': 'invoke',
                                           'params': {'contributionId': 'search', 'kind': 'command'}})
    assert reply['result']['ok'] is False


def test_an_unknown_request_is_an_error_not_a_crash(heme_pubchem):
    replies = ask(PubChemPlugin(heme_pubchem),
                  {'jsonrpc': '2.0', 'id': 1, 'method': 'card', 'params': {}}, query('heme'))
    assert 'error' in replies[0]
    assert replies[1]['result']['results']


def test_main_shakes_hands_and_shuts_down():
    lines = ''.join(json.dumps(m) + '\n' for m in (
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': 1}},
        query('x'),
        {'jsonrpc': '2.0', 'method': 'shutdown'},
    ))
    done = subprocess.run([sys.executable, 'main.py'], cwd=ROOT, input=lines, capture_output=True,
                          text=True, encoding='utf-8', timeout=30)
    replies = [json.loads(line) for line in done.stdout.splitlines() if line.strip()]
    assert done.returncode == 0, done.stderr
    assert [r['id'] for r in replies] == [1, 2]
    assert replies[1]['result'] == {'results': []}


def test_the_manifest_declares_a_two_step_command():
    with open(os.path.join(ROOT, 'plugin.json'), encoding='utf-8') as f:
        manifest = json.load(f)
    [command] = manifest['contributes']['commands']
    assert command['query']['fallback'] is True
    assert manifest['capabilities'] == ['network']
