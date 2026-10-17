"""Newline-delimited JSON-RPC 2.0 with Molion, both ways on one pipe.

While the plugin waits on its own call (a `dialog` stays open until the user is done), Molion
sends requests of its own (`dialogEvent`); those are answered here, by whatever handler the
waiting call installed.
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Callable


def log(message: str) -> None:
    print(f'[teaching] {message}', file=sys.stderr, flush=True)


class HostError(RuntimeError):
    """Molion answered a call with an error."""


class Host:
    def __init__(self, readline: Callable[[], str], write: Callable[[dict], None]) -> None:
        self._readline = readline
        self._write = write
        self._next_id = 0
        # Answers Molion's requests that arrive while a call waits, by method.
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
            return message.get('result') or {}

    def serve_inbound(self, message: dict) -> None:
        """A request from Molion that arrived mid-call: a handler's answer, else an empty one."""
        if 'id' not in message:
            return
        handler = self.handlers.get(message['method'])
        if handler is None:
            self.reply(message['id'], {})
            return
        try:
            self.reply(message['id'], handler(message.get('params') or {}))
        except Exception as error:            # the dialog stays open and shows the message
            log(traceback.format_exc())
            self.reply(message['id'], error=str(error))

    def scene(self, operation: str, **payload) -> dict:
        return self.call('scene', {'operation': operation, 'payload': payload})

    def gesture(self, kind: str, prompt: str, **options) -> dict:
        return self.call('gesture', {'kind': kind, 'prompt': prompt, **options})

    def dialog(self, request: dict, on_event: Callable[[dict], dict]) -> dict:
        self.handlers['dialogEvent'] = on_event
        try:
            return self.call('dialog', request)
        finally:
            self.handlers.pop('dialogEvent', None)


def present(host: Host, request: dict) -> dict:
    """The drawing a step at a time, full screen, until the user leaves; how it ended."""
    return host.call('present', request)
