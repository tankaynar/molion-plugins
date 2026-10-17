"""The plugin without Molion or a model: a fake host answering from a script."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class FakeMolion:
    """Plays Molion for Host: records what the plugin sends, answers calls by method.

    `answers` maps a method (or "scene:<operation>") to a result, a function of the params, or
    an exception instance to answer with an error. Notifications are recorded, not answered.
    """

    def __init__(self, answers=None):
        self.answers = answers or {}
        self.sent = []
        self.replies = []
        self._lines = []

    def write(self, message):
        self.sent.append(message)
        if 'method' not in message:
            self.replies.append(message)
            return
        if 'id' not in message:
            return
        key = message['method']
        if key == 'scene':
            key = 'scene:' + message['params']['operation']
        answer = self.answers.get(key, {})
        if callable(answer):
            answer = answer(message['params'])
        if isinstance(answer, Exception):
            reply = {'jsonrpc': '2.0', 'id': message['id'], 'error': {'code': -32000, 'message': str(answer)}}
        else:
            reply = {'jsonrpc': '2.0', 'id': message['id'], 'result': answer}
        self._lines.append(json.dumps(reply))

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


def picture(data='iVBORw0KGgo=', crop=None, **image):
    base = {'id': 'img-1', 'centerX': 100.0, 'centerY': 50.0, 'width': 200.0, 'height': 100.0,
            'locks': [], 'kind': 'raster', 'crop': crop}
    base.update(image)
    answer = {'image': base}
    if data is not None:
        answer['data'] = data
    return answer
