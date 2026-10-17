#!/usr/bin/env python3
"""PubChem — a Molion plugin: Search PubChem… in the palette, and PubChem's own drawing of the
compound chosen, placed like a template.

It contributes one two-step command. Molion asks it a `query` as the user types after choosing
Search PubChem…, shows the rows it answers, and sends the chosen row back as an `invoke`; this
answers with the compound's 2D record for Molion to place. It never reads or changes the
drawing, and is the only part of Molion that goes online, once the user has turned it on.

    python3 main.py

The protocol: Molion's plugin protocol, newline-delimited JSON-RPC 2.0 on stdin/stdout.
Logs go to stderr only; stdout is the channel.
"""

from __future__ import annotations

import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
sys.path.insert(0, HERE)

from pubchem_search import net                       # noqa: E402
from pubchem_search.plugin import PubChemPlugin      # noqa: E402


def log(message: str) -> None:
    print(f'[pubchem] {message}', file=sys.stderr, flush=True)


def serve(lines, write, plugin: PubChemPlugin) -> int:
    """Answers each request in `lines` through `write` until shutdown or end of input."""
    for line in lines:
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
                result = {}
            elif method == 'query':
                result = plugin.query(params)
            elif method == 'invoke':
                result = plugin.invoke(params)
            elif method == 'shutdown':
                return 0
            else:
                raise ValueError(f"unknown method '{method}'")
        except Exception as error:            # Molion shows it; the plugin keeps running
            log(traceback.format_exc())
            if request_id is not None:
                write({'jsonrpc': '2.0', 'id': request_id, 'error': {'code': -32000, 'message': str(error)}})
            continue
        if request_id is not None:
            write({'jsonrpc': '2.0', 'id': request_id, 'result': result})
    return 0


def main() -> int:
    if '--ca-certificates' in sys.argv:
        # For checking a frozen build: zero means a frozen build can verify no HTTPS at all.
        print(net.ca_certificate_count())
        return 0
    # The protocol is UTF-8, but Windows pipes default to the ANSI code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8')

    def write(message: dict) -> None:
        sys.stdout.write(json.dumps(message, ensure_ascii=False) + '\n')
        sys.stdout.flush()

    return serve(sys.stdin, write, PubChemPlugin(net.fetch))


if __name__ == '__main__':
    sys.exit(main())
