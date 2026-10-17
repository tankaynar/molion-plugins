"""Edit TLC: the plate in Molion's dialog, edited on a working copy.

Molion draws the dialog from `request()` and sends a `dialogEvent` for everything the user
does; `handle()` changes the copy and answers with what to redraw. Nothing reaches the
document until Done, when the action saves the copy (one undo step). Handlers never call
Molion: it is still waiting on the `dialog` request, so a call would wait forever.
"""

from __future__ import annotations

from . import drawing, model, stains

HINTS = ['Click · add or select a spot   Drag · move it', 'Double-click · delete a spot']

INTENSITY_LABELS = [('strong', 'Strong'), ('medium', 'Medium'), ('faint', 'Faint')]
SHAPE_LABELS = [('round', 'Round'), ('streak', 'Streak'), ('tailing', 'Tailing')]


class Session:
    def __init__(self, plate: dict) -> None:
        self.plate = model.copy_of(plate)
        self.lane: int | None = None
        self.spot: tuple[int, int] | None = None      # (lane it is stored in, number)
        self._dragging: tuple[int, int] | None = None

    # ── What Molion shows ────────────────────────────────────────────────

    def request(self) -> dict:
        return {'title': 'Edit TLC Plate', 'doneLabel': 'Done',
                'picture': self.picture(), 'fields': self.fields(), 'message': None}

    def picture(self) -> dict:
        selected = {'lane': self.lane, 'spot': self.spot} if self.lane is not None else None
        picture = drawing.drawing(self.plate, selected=selected)
        picture['interactive'] = True
        return picture

    def fields(self) -> list[dict]:
        plate = self.plate
        fields: list[dict] = [
            {'type': 'heading', 'text': 'Plate'},
            {'type': 'choice', 'id': 'stain', 'label': 'Stain', 'value': plate['stain'],
             'options': [{'value': stain['id'], 'label': stain['name']} for stain in stains.STAINS]},
            {'type': 'text', 'id': 'eluent', 'label': 'Eluent', 'value': plate['eluent'],
             'placeholder': '30% EtOAc/hexanes'},
            {'type': 'checkbox', 'id': 'showRf', 'label': 'Rf values', 'value': plate['showRf']},
            {'type': 'buttons', 'buttons': [{'id': 'add-lane', 'label': 'Add Lane'},
                                            {'id': 'add-cospot', 'label': 'Add Co-spot'}]},
        ]
        if self.lane is not None:
            fields += self._lane_fields(self.lane)
        if self.spot is not None:
            fields += self._spot_fields(*self.spot)
        fields += [{'type': 'note', 'text': hint} for hint in HINTS]
        return fields

    def _lane_fields(self, index: int) -> list[dict]:
        entry = self.plate['lanes'][index]
        fields = [
            {'type': 'heading', 'text': f'Lane {index + 1}'},
            {'type': 'text', 'id': 'lane-label', 'label': 'Label', 'value': entry['label'],
             'placeholder': str(index + 1)},
        ]
        samples = [other for other in range(len(self.plate['lanes']))
                   if other != index and not model.is_cospot(self.plate, other)]
        if len(samples) >= 2 or entry['cospot'] is not None:
            fields.append({'type': 'choice', 'id': 'lane-kind', 'label': 'Lane',
                           'value': 'cospot' if entry['cospot'] is not None else 'sample',
                           'options': [{'value': 'sample', 'label': 'Sample'},
                                       {'value': 'cospot', 'label': 'Co-spot'}]})
        if entry['cospot'] is not None:
            first, second = entry['cospot']
            # Molion refuses a choice whose value is not an option, so the pair is always offered.
            choices = sorted(set(samples) | {first, second})
            options = [{'value': str(other), 'label': self._lane_name(other)} for other in choices]
            fields.append({'type': 'choice', 'id': 'cospot-a', 'label': 'Of', 'value': str(first), 'options': options})
            fields.append({'type': 'choice', 'id': 'cospot-b', 'label': 'And', 'value': str(second), 'options': options})
        if len(self.plate['lanes']) > 1:
            fields.append({'type': 'buttons', 'buttons': [{'id': 'remove-lane', 'label': 'Remove Lane'}]})
        return fields

    def _spot_fields(self, index: int, number: int) -> list[dict]:
        item = self.plate['lanes'][index]['spots'][number]
        stain = stains.get(self.plate['stain'])
        swatches = list(dict.fromkeys(stain['swatches'] + ([item['colour']] if item['colour'] else [])))
        buttons = [{'id': 'remove-spot', 'label': 'Delete Spot'}]
        if item['colour']:
            buttons.append({'id': 'stain-colour', 'label': 'Use Stain Colour'})
        title = 'Spot' if index == self.lane else f'Spot (from {self._lane_name(index)})'
        return [
            {'type': 'heading', 'text': title},
            {'type': 'number', 'id': 'spot-rf', 'label': 'Rf', 'value': item['rf'], 'min': 0, 'max': 1, 'step': 0.01},
            {'type': 'choice', 'id': 'spot-intensity', 'label': 'Intensity', 'value': item['intensity'],
             'options': [{'value': value, 'label': label} for value, label in INTENSITY_LABELS]},
            {'type': 'choice', 'id': 'spot-shape', 'label': 'Shape', 'value': item['shape'],
             'options': [{'value': value, 'label': label} for value, label in SHAPE_LABELS]},
            {'type': 'colour', 'id': 'spot-colour', 'label': 'Colour',
             'value': model.spot_colour(self.plate, item), 'swatches': swatches},
            {'type': 'buttons', 'buttons': buttons},
        ]

    def _lane_name(self, index: int) -> str:
        label = self.plate['lanes'][index]['label']
        return f'{index + 1} ({label})' if label and label != str(index + 1) else str(index + 1)

    # ── What the user did ────────────────────────────────────────────────

    def handle(self, params: dict) -> dict:
        event = params.get('event') or {}
        kind = event.get('type')
        try:
            if kind == 'click':
                return self._click(*event['point'], bool(event.get('double')))
            if kind == 'drag':
                return self._drag(event['from'], event['to'], event.get('phase') == 'end')
            if kind == 'change':
                return self._change(event.get('field'), event.get('value'))
            if kind == 'button':
                return self._button(event.get('id'))
        except model.PlateError as error:
            return {'message': str(error)}
        return {}

    def _redraw(self, fields: bool = True, message: str | None = None) -> dict:
        answer = {'picture': self.picture(), 'message': message}
        if fields:
            answer['fields'] = self.fields()
        return answer

    def _select(self, lane_index: int | None, spot: tuple[int, int] | None = None) -> None:
        self.lane, self.spot = lane_index, spot

    def _click(self, x: float, y: float, double: bool) -> dict:
        hit = drawing.spot_at(self.plate, x, y)
        if double:
            if hit is None:
                return {}
            lane_index, number = hit[1]['source']
            del self.plate['lanes'][lane_index]['spots'][number]
            self._select(hit[0])
            return self._redraw(message='Deleted the spot.')
        if hit is not None:
            self._select(hit[0], hit[1]['source'])
            return self._redraw()
        lane_index = drawing.lane_at(self.plate, x)
        if lane_index is None or not 0 <= y <= drawing.PLATE_HEIGHT + drawing.LABEL_HEIGHT:
            self._select(None)
            return self._redraw()
        if drawing.FRONT_Y - 8 <= y <= drawing.BASELINE_Y - 4:
            number = model.add_spot(self.plate, lane_index, drawing.rf_at(y))
            self._select(lane_index, (lane_index, number))
            return self._redraw(message=f'Spot in lane {lane_index + 1} at Rf {drawing.rf_at(y):.2f}.')
        self._select(lane_index)
        return self._redraw()

    def _drag(self, start: list[float], end: list[float], finished: bool) -> dict:
        if self._dragging is None:
            hit = drawing.spot_at(self.plate, *start)
            if hit is None:
                return {}
            self._dragging = hit[1]['source']
            self._select(hit[0], self._dragging)
        lane_index, number = self._dragging
        item = self.plate['lanes'][lane_index]['spots'][number]
        item['rf'] = drawing.rf_at(end[1])
        # A spot stored in a lane may move to another sample lane; one dragged inside a
        # co-spot lane belongs to its sample, so only its Rf changes.
        target = drawing.lane_at(self.plate, end[0])
        if (target is not None and target != lane_index and self.lane == lane_index
                and not model.is_cospot(self.plate, target)
                and len(self.plate['lanes'][target]['spots']) < model.MAX_SPOTS):
            del self.plate['lanes'][lane_index]['spots'][number]
            self.plate['lanes'][target]['spots'].append(item)
            self._dragging = (target, len(self.plate['lanes'][target]['spots']) - 1)
            self._select(target, self._dragging)
        if finished:
            self._dragging = None
            return self._redraw(message=f"Rf {item['rf']:.2f}")
        return self._redraw(fields=False)

    def _change(self, field: str | None, value) -> dict:
        plate = self.plate
        if field == 'stain' and value in stains.BY_ID:
            plate['stain'] = value
            return self._redraw()
        if field == 'eluent':
            plate['eluent'] = str(value or '')[:model.MAX_ELUENT]
            return self._redraw(fields=False)
        if field == 'showRf':
            plate['showRf'] = bool(value)
            return self._redraw(fields=False)
        if self.lane is not None:
            entry = plate['lanes'][self.lane]
            if field == 'lane-label':
                entry['label'] = str(value or '')[:model.MAX_LABEL]
                return self._redraw(fields=False)
            if field == 'lane-kind':
                if value == 'sample':
                    entry['cospot'] = None
                else:
                    samples = [other for other in range(len(plate['lanes']))
                               if other != self.lane and not model.is_cospot(plate, other)]
                    if len(samples) < 2:
                        raise model.PlateError('A co-spot needs two sample lanes.')
                    entry['cospot'] = [samples[0], samples[-1]]
                return self._redraw()
            if field in ('cospot-a', 'cospot-b') and entry['cospot'] is not None:
                pair = list(entry['cospot'])
                pair[0 if field == 'cospot-a' else 1] = int(value)
                if pair[0] == pair[1]:
                    return self._redraw(message='Choose two different lanes.')
                entry['cospot'] = pair
                return self._redraw()
        if self.spot is not None:
            lane_index, number = self.spot
            item = plate['lanes'][lane_index]['spots'][number]
            if field == 'spot-rf':
                item['rf'] = model.clamp_rf(value)
                return self._redraw(fields=False)
            if field == 'spot-intensity' and value in model.INTENSITIES:
                item['intensity'] = value
                return self._redraw(fields=False)
            if field == 'spot-shape' and value in model.SHAPES:
                item['shape'] = value
                return self._redraw(fields=False)
            if field == 'spot-colour' and isinstance(value, str):
                default = stains.get(plate['stain'])['spot']
                item['colour'] = None if value.upper() == default else value.upper()
                return self._redraw()
        return {}

    def _button(self, button: str | None) -> dict:
        plate = self.plate
        if button == 'add-lane':
            self._select(model.add_lane(plate))
            return self._redraw()
        if button == 'add-cospot':
            self._select(model.add_cospot_lane(plate))
            return self._redraw()
        if button == 'remove-lane' and self.lane is not None:
            model.remove_lane(plate, self.lane)
            self._select(None)
            return self._redraw()
        if button == 'remove-spot' and self.spot is not None:
            lane_index, number = self.spot
            del plate['lanes'][lane_index]['spots'][number]
            self._select(self.lane)
            return self._redraw()
        if button == 'stain-colour' and self.spot is not None:
            lane_index, number = self.spot
            plate['lanes'][lane_index]['spots'][number]['colour'] = None
            return self._redraw()
        return {}
