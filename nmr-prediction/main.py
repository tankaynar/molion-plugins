#!/usr/bin/env python3
"""NMR Prediction — a Molion plugin card with predicted ¹H and ¹³C spectra.

Molion sends the selected structures as it perceives them (a `card`
request); this answers with the spectra to draw, each peak linked to its atoms. It never
changes the drawing, and needs no network: the shift table is in data/.

Where the user has ORCA set up in Molion, its "Calculate NMR with ORCA" action asks Molion to
calculate the shifts (`calculate`, the `orca` capability), and the card shows them once done.

    python3 main.py [--data data/shifts.bin.gz]

The protocol: Molion's plugin protocol, newline-delimited JSON-RPC 2.0 on stdin/stdout.
Logs go to stderr only; stdout is the channel.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
sys.path.insert(0, HERE)

from nmr import calculated, card          # noqa: E402
from nmr.host import Host, HostError      # noqa: E402
from nmr.table import ShiftTable          # noqa: E402

DEFAULT_DATA = os.path.join('data', 'shifts.bin.gz')


def log(message: str) -> None:
    print(f'[nmr-prediction] {message}', file=sys.stderr, flush=True)


def find_data(path: str) -> str:
    """The table: as given, else beside the plugin (Molion starts it in its own folder; a
    frozen build keeps its program in bin/)."""
    if os.path.isabs(path) or os.path.exists(path):
        return path
    for base in (HERE, os.path.dirname(HERE)):
        candidate = os.path.join(base, path)
        if os.path.exists(candidate):
            return candidate
    return path


def calculate(host: Host, params: dict) -> dict:
    """Calculate NMR with ORCA: each selected molecule (each one drawn, with nothing selected)."""
    context = params.get('context') or {}
    payload = {'selection': True} if context.get('atoms') or context.get('bonds') else {}
    try:
        structures = host.call('scene', {'operation': 'get-structure', 'payload': payload})
    except HostError as error:
        return {'ok': False, 'error': str(error)}
    document_id = structures.get('documentId') or ''
    molecules = [s.get('moleculeId') for s in structures.get('structures') or [] if s.get('moleculeId') and not s.get('error')]
    if not molecules:
        return {'ok': False, 'error': structures.get('empty') or 'Select a structure to calculate.'}
    for molecule_id in molecules:
        answer = calculated.ask(host, document_id, molecule_id, start=True)
        if answer.state in ('unavailable', 'failed'):
            return {'ok': False, 'error': answer.message or "ORCA can't calculate this."}
    return {'ok': True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default=DEFAULT_DATA)
    args = parser.parse_args()
    # The protocol is UTF-8, but Windows pipes default to the ANSI code page (cp1252), which
    # cannot encode the δ in a peak label. Molion sets PYTHONIOENCODING, but other hosts need not.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8')

    host = Host()
    table = None
    while (message := host.read()) is not None:
        method, request_id = message.get('method'), message.get('id')
        if method is None:
            continue                          # an answer to something we never ask
        try:
            if method == 'initialize':
                table = ShiftTable.load(find_data(args.data))
                log(f"shift table: {table.size('13C')} carbon and {table.size('1H')} hydrogen environments")
                result = {}
            elif method == 'card':
                result = card.answer(message.get('params') or {}, table, host)
            elif method == 'invoke':
                params = message.get('params') or {}
                if params.get('contributionId') != calculated.ACTION:
                    raise ValueError(f"no action '{params.get('contributionId')}'")
                result = calculate(host, params)
            elif method == 'shutdown':
                return 0
            else:
                raise ValueError(f"unknown method '{method}'")
        except Exception as error:            # the card shows it; the plugin keeps running
            log(traceback.format_exc())
            if request_id is not None:
                host.send({'jsonrpc': '2.0', 'id': request_id, 'error': {'code': -32000, 'message': str(error)}})
            continue
        if request_id is not None:
            host.send({'jsonrpc': '2.0', 'id': request_id, 'result': result})
    return 0


if __name__ == '__main__':
    sys.exit(main())
