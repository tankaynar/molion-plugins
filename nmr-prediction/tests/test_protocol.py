"""main.py as Molion runs it: JSON-RPC over stdin and stdout."""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(*messages):
    lines = ''.join(json.dumps(m) + '\n' for m in messages)
    done = subprocess.run([sys.executable, 'main.py', '--data', 'data/shifts.bin.gz'], cwd=ROOT,
                          input=lines, capture_output=True, text=True, encoding='utf-8', timeout=60)
    return [json.loads(line) for line in done.stdout.splitlines() if line.strip()], done


def test_initialize_card_shutdown(raw):
    replies, done = run(
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': 1}},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'card',
         'params': {'cardId': 'nmr', 'documentId': 'd', 'scope': 'selection', 'structures': [raw['toluene']]}},
        {'jsonrpc': '2.0', 'method': 'shutdown'},
    )
    assert done.returncode == 0, done.stderr
    assert [r['id'] for r in replies] == [1, 2]
    assert [v['id'] for v in replies[1]['result']['views']] == ['1h', '13c']


def test_an_unknown_request_is_an_error_not_a_crash():
    replies, done = run(
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'invoke', 'params': {}},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'card', 'params': {'structures': []}},
    )
    assert 'error' in replies[1]
    assert replies[2]['result']['message'] == 'Select a structure.'
