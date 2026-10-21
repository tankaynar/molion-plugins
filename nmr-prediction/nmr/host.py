"""Asking Molion something mid-request: newline-delimited JSON-RPC on the plugin's own stdin and
stdout, the same channel Molion's requests come in on.

Molion sends a plugin one request at a time and waits for its answer, so while the plugin waits
on its own call nothing else of Molion's is pending; anything else that arrives is answered
with an error rather than left hanging.
"""

from __future__ import annotations

import json
import sys


class HostError(RuntimeError):
    """Molion refused the call (a capability not declared, an older Molion without it)."""


class Host:
    def __init__(self, reader=None, writer=None):
        self._reader = reader or sys.stdin
        self._writer = writer or sys.stdout
        self._next_id = 1_000_000

    def send(self, message: dict) -> None:
        self._writer.write(json.dumps(message, ensure_ascii=False) + '\n')
        self._writer.flush()

    def read(self) -> dict | None:
        """The next message, or None once Molion has closed the channel."""
        while True:
            line = self._reader.readline()
            if not line:
                return None
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

    def call(self, method: str, params: dict) -> dict:
        self._next_id += 1
        call_id = self._next_id
        self.send({'jsonrpc': '2.0', 'id': call_id, 'method': method, 'params': params})
        while True:
            message = self.read()
            if message is None:
                raise HostError('Molion closed the channel')
            if 'method' in message:
                if message.get('id') is not None:
                    self.send({'jsonrpc': '2.0', 'id': message['id'],
                               'error': {'code': -32000, 'message': 'busy with a call of its own'}})
                continue
            if message.get('id') != call_id:
                continue
            if 'error' in message:
                raise HostError((message['error'] or {}).get('message') or 'refused')
            return message.get('result') or {}
