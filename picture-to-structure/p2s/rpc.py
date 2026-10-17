"""Newline-delimited JSON-RPC 2.0 with Molion, both ways on one pipe.

While the plugin waits on its own call (a `dialog` stays open until the user answers), Molion
may send requests of its own (`dialogEvent`); those are answered here, by whatever handler the
waiting call installed.
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Callable


def log(message: str) -> None:
    print(f'[picture-to-structure] {message}', file=sys.stderr, flush=True)


class HostError(RuntimeError):
    """Molion answered a call with an error."""


class Host:
    def __init__(self, readline: Callable[[], str], write: Callable[[dict], None]) -> None:
        self._readline = readline
        self._write = write
        self._next_id = 0
        self.handlers: dict[str, Callable[[dict], dict]] = {}

    def send(self, message: dict) -> None:
        self._write(message)

    def reply(self, request_id, result=None, error: str | None = None) -> None:
        if error is not None:
            self.send({'jsonrpc': '2.0', 'id': request_id, 'error': {'code': -32000, 'message': error}})
        else:
            self.send({'jsonrpc': '2.0', 'id': request_id, 'result': result})

    def readline(self) -> str:
        return self._readline()

    def notify(self, method: str, params: dict) -> None:
        self.send({'jsonrpc': '2.0', 'method': method, 'params': params})

    def progress(self, message: str, fraction: float | None = None) -> None:
        """Shown in Molion's status bar; each one also gives the action another 30 s."""
        self.notify('progress', {'message': message, 'fraction': fraction})

    def call(self, method: str, params: dict) -> dict:
        self._next_id += 1
        request_id = self._next_id
        self.send({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
        while True:
            line = self._readline()
            if not line:
                raise HostError('Molion closed the connection')
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if 'method' in message:
                self.serve_inbound(message)
                continue
            if message.get('id') != request_id:
                continue
            if 'error' in message:
                raise HostError((message['error'] or {}).get('message', 'host error'))
            result = message.get('result')
            return {} if result is None else result

    def serve_inbound(self, message: dict) -> None:
        if 'id' not in message:
            return
        handler = self.handlers.get(message['method'])
        if handler is None:
            self.reply(message['id'], {})
            return
        try:
            self.reply(message['id'], handler(message.get('params') or {}))
        except Exception as error:
            log(traceback.format_exc())
            self.reply(message['id'], error=str(error))

    def scene(self, operation: str, **payload) -> dict:
        return self.call('scene', {'operation': operation, 'payload': payload})

    def dialog(self, request: dict, on_event: Callable[[dict], dict] | None = None) -> dict:
        self.handlers['dialogEvent'] = on_event or (lambda _params: {})
        try:
            return self.call('dialog', request)
        finally:
            self.handlers.pop('dialogEvent', None)
