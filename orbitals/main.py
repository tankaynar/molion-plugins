#!/usr/bin/env python3
"""Orbitals — a Molion plugin: atomic and hybrid orbitals as pictures it draws.

The ORBITALS tools (s, p, sp³, d) and the Place … Orbital commands put an orbital on the atom
clicked, or aimed along a drag. Double-clicking one, or Edit Orbital… in the palette, opens it
in Molion's dialog: its type, how its phase is shown, its colours and its angle. Its scene
templates (an sp³ set, ethylene's π bond, benzene's p orbitals…) need no process at all.

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

from orbitals.actions import Actions     # noqa: E402
from orbitals.rpc import Host, log       # noqa: E402

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
                result = {'name': 'Orbitals', 'version': '1.0.0', 'protocolVersion': PROTOCOL_VERSION}
            elif method == 'invoke':
                result = actions.invoke(params)
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
