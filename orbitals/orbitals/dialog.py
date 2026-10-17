"""Edit Orbital: the orbital in Molion's dialog, edited on a working copy.

Molion draws the dialog from `request()` and sends a `dialogEvent` for every change;
`handle()` changes the copy and answers with the new picture. Nothing reaches the document
until Done, when the action saves the copy (one undo step). Handlers never call Molion: it is
still waiting on the `dialog` request.
"""

from __future__ import annotations

from . import drawing, model

SWATCHES = ['#3D6FD8', '#D8553D', '#2E9E6B', '#8A4FC7', '#E0A21A', '#555555']


class Session:
    def __init__(self, orbital: dict) -> None:
        self.orbital = model.copy_of(orbital)

    def request(self) -> dict:
        return {'title': 'Edit Orbital', 'doneLabel': 'Done',
                'picture': drawing.drawing(self.orbital), 'fields': self.fields(), 'message': None}

    def fields(self) -> list[dict]:
        orbital = self.orbital
        fields: list[dict] = [
            {'type': 'choice', 'id': 'type', 'label': 'Orbital', 'value': orbital['type'],
             'options': [{'value': kind, 'label': model.NAMES[kind]} for kind in model.TYPES]},
            {'type': 'choice', 'id': 'phase', 'label': 'Phase', 'value': orbital['phase'],
             'options': [{'value': phase, 'label': model.PHASE_NAMES[phase]} for phase in model.PHASES]},
        ]
        if orbital['phase'] == 'shaded':
            fields += [
                {'type': 'colour', 'id': 'positive', 'label': 'Positive', 'value': orbital['colours'][0], 'swatches': SWATCHES},
                {'type': 'colour', 'id': 'negative', 'label': 'Negative', 'value': orbital['colours'][1], 'swatches': SWATCHES},
            ]
        fields += [
            {'type': 'number', 'id': 'angle', 'label': 'Angle', 'value': orbital['angle'],
             'min': -180, 'max': 180, 'step': 1},
            {'type': 'checkbox', 'id': 'flip', 'label': 'Swap signs', 'value': orbital['flip']},
            {'type': 'buttons', 'buttons': [{'id': 'rotate-left', 'label': 'Turn Left 90°'},
                                            {'id': 'rotate-right', 'label': 'Turn Right 90°'}]},
        ]
        return fields

    def handle(self, params: dict) -> dict:
        event = params.get('event') or {}
        kind = event.get('type')
        try:
            if kind == 'change':
                return self._change(event.get('field'), event.get('value'))
            if kind == 'button':
                return self._button(event.get('id'))
        except model.OrbitalError as error:
            return {'message': str(error)}
        return {}

    def _redraw(self, fields: bool = False) -> dict:
        answer = {'picture': drawing.drawing(self.orbital), 'message': None}
        if fields:
            answer['fields'] = self.fields()
        return answer

    def _change(self, field: str | None, value) -> dict:
        orbital = self.orbital
        if field == 'type' and value in model.TYPES:
            orbital['type'] = value
            return self._redraw()
        if field == 'phase' and value in model.PHASES:
            orbital['phase'] = value
            return self._redraw(fields=True)
        if field == 'positive':
            orbital['colours'][0] = model.colour(value)
            return self._redraw()
        if field == 'negative':
            orbital['colours'][1] = model.colour(value)
            return self._redraw()
        if field == 'angle' and isinstance(value, (int, float)) and not isinstance(value, bool):
            orbital['angle'] = model.normal_angle(value)
            return self._redraw()
        if field == 'flip':
            orbital['flip'] = bool(value)
            return self._redraw()
        return {}

    def _button(self, button: str | None) -> dict:
        turn = {'rotate-left': -90, 'rotate-right': 90}.get(button)
        if turn is None:
            return {}
        self.orbital['angle'] = model.normal_angle(self.orbital['angle'] + turn)
        return self._redraw(fields=True)
