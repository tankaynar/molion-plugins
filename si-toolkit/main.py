#!/usr/bin/env python3
"""SI Toolkit — a Molion plugin for the supporting information of a paper.

Copy HRMS Line… writes "HRMS (ESI) m/z: [M+Na]⁺ calcd for C₁₅H₂₀NaO₃ 271.1305, found " for the
adduct chosen; Copy Elemental Analysis writes "Anal. Calcd for C₁₅H₂₀O₃: C, 72.55; H, 8.12";
Copy SI Stub and Export SI Stub as CSV… list every compound with its number, name, formula,
HRMS, SMILES and InChI. The SI card shows the same for the selection.

    python3 main.py

The protocol: Molion's plugin protocol, newline-delimited JSON-RPC 2.0 on stdin/stdout.
Logs go to stderr only; stdout is the channel. Standard library only.
"""

from __future__ import annotations

import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
sys.path.insert(0, HERE)

from si import card                      # noqa: E402
from si.actions import Actions           # noqa: E402
from si.rpc import Host, log             # noqa: E402
from si.settings import Settings         # noqa: E402

PROTOCOL_VERSION = 1


def serve(host: Host) -> int:
    """Answers each request until shutdown or end of input."""
    actions = Actions(host)
    while True:
        line = host.readline()
        if not line:
            return 0
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            log('ignored a line that is not JSON')
            continue
        method, request_id = message.get('method'), message.get('id')
        if method is None:
            continue                          # an answer to something we never ask
        params = message.get('params') or {}
        try:
            if method == 'initialize':
                actions.settings = Settings(params.get('dataDir'))
                result = {'name': 'SI Toolkit', 'version': '1.0.0', 'protocolVersion': PROTOCOL_VERSION}
            elif method == 'invoke':
                result = actions.invoke(params)
            elif method == 'query':
                result = actions.query(params)
            elif method == 'card':
                result = card.answer(host, params)
            elif method == 'shutdown':
                return 0
            else:
                result = {}
        except Exception as error:            # Molion shows it; the plugin keeps running
            log(traceback.format_exc())
            if request_id is not None:
                host.reply(request_id, error=str(error))
            continue
        if request_id is not None:
            host.reply(request_id, result)


def main() -> int:
    # The protocol is UTF-8, but Windows pipes default to the ANSI code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8')

    def write(message: dict) -> None:
        sys.stdout.write(json.dumps(message, ensure_ascii=False) + '\n')
        sys.stdout.flush()

    return serve(Host(sys.stdin.readline, write))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (BrokenPipeError, KeyboardInterrupt):
        pass
