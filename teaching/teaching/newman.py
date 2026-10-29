"""A Newman projection as a picture this plugin owns, and the dialog that turns it.

pluginData: {"v": 1, "front": [{"label", "angle"}], "back": [{"label", "angle"}],
"dihedral": d, "modelled": d0, "rotatable": bool}. Angles are degrees clockwise from
12 o'clock as the viewer sees them; the front's first group is its most important (at 0
as modelled), the back's likewise, and `dihedral` is the back's first angle less the
front's. Turning the bond turns the back groups together.
"""

from __future__ import annotations

import json
import math

VERSION = 1
CIRCLE = 30.0          # the back carbon
REACH = 58.0           # how far a bond reaches from the centre
LABEL_GAP = 4.0
TEXT_SIZE = 15
INK = '#000000'
WIDTH = 1.6
# An eclipsed back bond is drawn this far round, so it can be seen behind the front one.
ECLIPSE_SHOW = 10.0

PRESETS = [('modelled', 'As modelled'), ('anti', 'Staggered, anti (180°)'), ('gauche', 'Staggered, gauche (60°)'),
           ('eclipsed', 'Eclipsed (0°)'), ('eclipsed-120', 'Eclipsed (120°)')]
PRESET_DIHEDRAL = {'anti': 180.0, 'gauche': 60.0, 'eclipsed': 0.0, 'eclipsed-120': 120.0}


def from_projection(answer: dict) -> dict:
    """The model from a get-projection (newman) answer."""
    def groups(end):
        return [{'label': s['label'], 'angle': float(s['angle'])} for s in end['substituents']]
    return {'v': VERSION, 'front': groups(answer['front']), 'back': groups(answer['back']),
            'dihedral': float(answer['dihedral']), 'modelled': float(answer['dihedral']),
            'rotatable': bool(answer.get('rotatable', True))}


def dump(newman: dict) -> str:
    return json.dumps(newman, separators=(',', ':'), ensure_ascii=False)


def load(text: str | None) -> dict | None:
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get('v') != VERSION or not data.get('front') or not data.get('back'):
        return None
    return data


def copy_of(newman: dict) -> dict:
    return json.loads(json.dumps(newman))


def turned(newman: dict, dihedral: float) -> dict:
    """The projection with its bond turned to `dihedral`: every back group moves together."""
    result = copy_of(newman)
    delta = float(dihedral) - newman['dihedral']
    for group in result['back']:
        group['angle'] = (group['angle'] + delta) % 360.0
    result['dihedral'] = float(dihedral) % 360.0
    return result


def _eclipsed(newman: dict) -> bool:
    return any(abs((b['angle'] - f['angle'] + 180) % 360 - 180) < 1.0
               for b in newman['back'] for f in newman['front'])


def _point(angle: float, radius: float, centre: tuple[float, float]) -> tuple[float, float]:
    theta = math.radians(angle)
    return (centre[0] + radius * math.sin(theta), centre[1] - radius * math.cos(theta))


_SUBSCRIPTS = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')


def formula_text(label: str) -> str:
    """A group's label as a formula is written: counts after an element or a bracket set low
    (NH2 → NH₂, CH2OH → CH₂OH). A display-list text op has no subscripts of its own."""
    out = []
    for i, ch in enumerate(label):
        out.append(ch.translate(_SUBSCRIPTS) if ch.isdigit() and i > 0 and (label[i - 1].isalpha()
                   or label[i - 1] == ')' or out[-1] in '₀₁₂₃₄₅₆₇₈₉') else ch)
    return ''.join(out)


def _label(text: str, angle: float, end: tuple[float, float]) -> dict:
    theta = math.radians(angle)
    dx, dy = math.sin(theta), -math.cos(theta)
    align = 'start' if dx > 0.3 else 'end' if dx < -0.3 else 'middle'
    baseline = 'top' if dy > 0.3 else 'bottom' if dy < -0.3 else 'middle'
    at = [round(end[0] + dx * LABEL_GAP, 2), round(end[1] + dy * LABEL_GAP, 2)]
    return {'op': 'text', 'text': formula_text(text), 'at': at, 'align': align, 'baseline': baseline,
            'size': TEXT_SIZE, 'color': INK}


def drawing(newman: dict) -> dict:
    """{width, height, ops}: the back carbon a circle, its bonds from the circle's edge; the
    front carbon the centre, its bonds from it. Labels sit past each bond's end."""
    pad = REACH + 46
    centre = (pad, pad)
    shift = ECLIPSE_SHOW if _eclipsed(newman) else 0.0
    ops = []
    for group in newman['back']:
        angle = group['angle'] + shift
        start, end = _point(angle, CIRCLE, centre), _point(angle, REACH, centre)
        ops.append({'op': 'line', 'from': [round(start[0], 2), round(start[1], 2)],
                    'to': [round(end[0], 2), round(end[1], 2)], 'color': INK, 'width': WIDTH, 'cap': 'round'})
        ops.append(_label(group['label'], angle, end))
    ops.append({'op': 'ellipse', 'center': list(centre), 'rx': CIRCLE, 'ry': CIRCLE, 'fill': '#FFFFFF',
                'stroke': INK, 'width': WIDTH})
    for group in newman['front']:
        end = _point(group['angle'], REACH, centre)
        ops.append({'op': 'line', 'from': list(centre), 'to': [round(end[0], 2), round(end[1], 2)],
                    'color': INK, 'width': WIDTH, 'cap': 'round'})
        ops.append(_label(group['label'], group['angle'], end))
    return {'width': 2 * pad, 'height': 2 * pad, 'ops': ops}


class Session:
    """Edit Newman: the projection turned on a working copy. Handlers never call Molion."""

    def __init__(self, newman: dict) -> None:
        self.newman = copy_of(newman)

    def request(self) -> dict:
        return {'title': 'Edit Newman Projection', 'doneLabel': 'Done',
                'picture': drawing(self.newman), 'fields': self.fields(), 'message': None}

    def fields(self) -> list[dict]:
        if not self.newman['rotatable']:
            return [{'type': 'note', 'text': 'This bond is in a ring or is a multiple bond, so it does not turn.'}]
        return [
            {'type': 'choice', 'id': 'preset', 'label': 'Conformation', 'value': self._preset(),
             'options': [{'value': value, 'label': label} for value, label in PRESETS]},
            {'type': 'number', 'id': 'dihedral', 'label': 'Dihedral', 'value': round(self.newman['dihedral']),
             'min': 0, 'max': 359, 'step': 1},
            {'type': 'note', 'text': 'The dihedral is measured between the first group in front and the first behind.'},
        ]

    def _preset(self) -> str:
        for value, dihedral in PRESET_DIHEDRAL.items():
            if abs((self.newman['dihedral'] - dihedral + 180) % 360 - 180) < 0.5:
                return value
        return 'modelled'

    def handle(self, params: dict) -> dict:
        event = params.get('event') or {}
        if event.get('type') != 'change' or not self.newman['rotatable']:
            return {}
        field, value = event.get('field'), event.get('value')
        if field == 'preset':
            target = self.newman['modelled'] if value == 'modelled' else PRESET_DIHEDRAL.get(value)
            if target is None:
                return {}
            self.newman = turned(self.newman, target)
            return {'picture': drawing(self.newman), 'fields': self.fields()}
        if field == 'dihedral' and isinstance(value, (int, float)) and not isinstance(value, bool):
            # Not the fields: they would be rebuilt under the user's typing.
            self.newman = turned(self.newman, value)
            return {'picture': drawing(self.newman)}
        return {}
