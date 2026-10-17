"""The plugin without Molion: a fake host that answers its calls from a script."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class FakeMolion:
    """Plays Molion for Host: records what the plugin sends, answers calls by method.

    `answers` maps a method (or "scene:<operation>") to a result or a function of the params.
    A function may raise `Refuse` to answer with an error.
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
            return                                   # a notification
        method = message['method']
        key = 'scene:' + message['params']['operation'] if method == 'scene' else method
        answer = self.answers.get(key, {})
        try:
            if callable(answer):
                answer = answer(message['params'])
            reply = {'jsonrpc': '2.0', 'id': message['id'], 'result': answer}
        except Refuse as error:
            reply = {'jsonrpc': '2.0', 'id': message['id'], 'error': {'code': -32000, 'message': str(error)}}
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


class Refuse(Exception):
    """Raised by an answer function: Molion answers the call with this error."""


# Ibuprofen, as get-analysis describes it.
IBUPROFEN = {'moleculeId': 'm1', 'kind': 'whole', 'formula': 'C13H18O2', 'charge': 0,
             'composition': [{'element': 'C', 'isotope': 0, 'count': 13},
                             {'element': 'H', 'isotope': 0, 'count': 18},
                             {'element': 'O', 'isotope': 0, 'count': 2}],
             'exactMass': 206.13067982, 'molecularWeight': 206.285,
             'elementalAnalysis': [{'element': 'C', 'percent': 75.6911}, {'element': 'H', 'percent': 8.7951},
                                   {'element': 'O', 'percent': 15.5138}],
             'unknownLabels': [], 'warnings': [], 'error': None}
