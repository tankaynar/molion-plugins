"""main.py as Molion starts it: a real process over pipes, without onnxruntime."""

import json
import os
import subprocess
import sys

from conftest import ROOT


def test_the_process_answers_initialize_and_exits_on_shutdown(tmp_path):
    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
         'params': {'protocolVersion': 1, 'host': 'molion', 'dataDir': str(tmp_path)}},
        {'jsonrpc': '2.0', 'method': 'shutdown'},
    ]
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    env.pop('MOLION_P2S_MODEL_DIR', None)
    done = subprocess.run([sys.executable, os.path.join(ROOT, 'main.py')],
                          input=''.join(json.dumps(r) + '\n' for r in requests),
                          capture_output=True, text=True, timeout=30, env=env)
    assert done.returncode == 0, done.stderr
    [reply] = [json.loads(line) for line in done.stdout.splitlines() if line.strip()]
    assert reply['result']['name'] == 'Picture to Structure'
