"""The plugin without Molion: a fake host that answers its calls from a script."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tlc import model  # noqa: E402


class FakeMolion:
    """Plays Molion for Host: records what the plugin sends, answers calls by method.

    `answers` maps a method (or "scene:<operation>") to a result or a function of the params.
    `inbound` is a list of requests Molion sends while the plugin waits on a call of that
    method, e.g. dialogEvents while a dialog is open; their replies are kept in `replies`.
    """

    def __init__(self, answers=None, inbound=None):
        self.answers = answers or {}
        self.inbound = inbound or {}
        self.sent = []
        self.replies = []
        self._lines = []

    def write(self, message):
        self.sent.append(message)
        if 'method' not in message:
            self.replies.append(message)
            return
        method = message['method']
        key = method
        if method == 'scene':
            key = 'scene:' + message['params']['operation']
        for request in self.inbound.get(key, []):
            self._lines.append(json.dumps(request))
        answer = self.answers.get(key, {})
        if callable(answer):
            answer = answer(message['params'])
        self._lines.append(json.dumps({'jsonrpc': '2.0', 'id': message['id'], 'result': answer}))

    def pending(self):
        return bool(self._lines)

    def readline(self):
        return self._lines.pop(0) + '\n' if self._lines else ''

    def calls(self, key):
        found = []
        for message in self.sent:
            if 'method' not in message:
                continue
            method = message['method']
            if method == 'scene':
                method = 'scene:' + message['params']['operation']
            if method == key:
                found.append(message['params'])
        return found


def plate_image(plate=None, width=None, height=None):
    from tlc import drawing
    plate = plate or model.new_plate()
    return {
        'image': {'id': 'plate-1', 'centerX': 100, 'centerY': 100,
                  'width': width or drawing.plate_width(plate), 'height': height or drawing.height(plate),
                  'rotation': 0},
        'pluginData': model.dump(plate),
    }
