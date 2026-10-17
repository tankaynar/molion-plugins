"""The plate as data: what is kept in the picture's pluginData and redrawn from.

    {"version": 2, "stain": "uv254", "eluent": "30% EtOAc/hexanes", "showRf": false,
     "lanes": [{"label": "SM", "cospot": null, "spots": [{"rf": 0.42, "intensity": "strong",
                "shape": "round", "colour": null}]},
               {"label": "Co", "cospot": [0, 2], "spots": []}, …]}

A co-spot lane shows its own spots and those of the two lanes it was spotted from; spots
closer than MERGE_RF run as one, which is the point of co-spotting. Molion stores the text and
never reads it, so everything read back is checked and clamped here.
"""

from __future__ import annotations

import copy
import json
import re

from . import stains

VERSION = 2
MAX_LANES = 12
MAX_SPOTS = 12
MAX_LABEL = 12
MAX_ELUENT = 60
MERGE_RF = 0.03

INTENSITIES = ('strong', 'medium', 'faint')
SHAPES = ('round', 'streak', 'tailing')
_HEX = re.compile(r'^#[0-9A-Fa-f]{6}$')


def new_plate() -> dict:
    """The plate most reactions are followed on: starting material, co-spot, reaction."""
    return {'version': VERSION, 'stain': stains.DEFAULT, 'eluent': '', 'showRf': False,
            'lanes': [lane('SM'), lane('Co', cospot=[0, 2]), lane('Rxn')]}


def lane(label: str = '', cospot: list[int] | None = None) -> dict:
    return {'label': label, 'cospot': cospot, 'spots': []}


def spot(rf: float, intensity: str = 'strong', shape: str = 'round', colour: str | None = None) -> dict:
    return {'rf': clamp_rf(rf), 'intensity': intensity, 'shape': shape, 'colour': colour}


def clamp_rf(rf: float) -> float:
    return round(min(1.0, max(0.0, float(rf))), 2)


# ── Reading and writing ──────────────────────────────────────────────────

def load(text: str | None) -> dict | None:
    """pluginData → a valid plate, or None when it is not a plate at all."""
    try:
        data = json.loads(text or '')
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    if isinstance(data.get('lanes'), int):
        return _from_v1(data)
    if not isinstance(data.get('lanes'), list):
        return None
    return normalise(data)


def dump(plate: dict) -> str:
    return json.dumps(plate, ensure_ascii=False, separators=(',', ':'))


def _from_v1(data: dict) -> dict:
    """The teaching example's plates: {"lanes": 3, "spots": [{"lane": 0, "rf": 0.5}]}."""
    count = min(MAX_LANES, max(1, int(data['lanes'])))
    plate = {'version': VERSION, 'stain': 'none', 'eluent': '', 'showRf': False,
             'lanes': [lane(str(index + 1)) for index in range(count)]}
    for old in data.get('spots') or []:
        if isinstance(old, dict) and isinstance(old.get('lane'), int) and 0 <= old['lane'] < count:
            target = plate['lanes'][old['lane']]['spots']
            if len(target) < MAX_SPOTS and isinstance(old.get('rf'), (int, float)):
                target.append(spot(old['rf']))
    return plate


def normalise(data: dict) -> dict:
    lanes_in = [entry for entry in data['lanes'] if isinstance(entry, dict)][:MAX_LANES] or [lane('1')]
    plate = {
        'version': VERSION,
        'stain': data.get('stain') if data.get('stain') in stains.BY_ID else stains.DEFAULT,
        'eluent': str(data.get('eluent') or '')[:MAX_ELUENT],
        'showRf': bool(data.get('showRf')),
        'lanes': [],
    }
    for entry in lanes_in:
        spots = []
        for item in (entry.get('spots') or [])[:MAX_SPOTS]:
            if not isinstance(item, dict) or not isinstance(item.get('rf'), (int, float)):
                continue
            colour = item.get('colour')
            spots.append(spot(item['rf'],
                              item.get('intensity') if item.get('intensity') in INTENSITIES else 'strong',
                              item.get('shape') if item.get('shape') in SHAPES else 'round',
                              colour.upper() if isinstance(colour, str) and _HEX.match(colour) else None))
        plate['lanes'].append({'label': str(entry.get('label') or '')[:MAX_LABEL],
                               'cospot': entry.get('cospot'), 'spots': spots})
    for index, entry in enumerate(plate['lanes']):
        entry['cospot'] = _valid_cospot(plate, index, entry['cospot'])
    return plate


def _valid_cospot(plate: dict, index: int, cospot) -> list[int] | None:
    """A co-spot names two other lanes that are samples themselves; anything else is dropped."""
    if not isinstance(cospot, list) or len(cospot) != 2:
        return None
    count = len(plate['lanes'])
    first, second = cospot
    if not all(isinstance(value, int) and 0 <= value < count and value != index for value in (first, second)):
        return None
    if first == second:
        return None
    return [first, second]


def copy_of(plate: dict) -> dict:
    return copy.deepcopy(plate)


# ── What a lane shows ────────────────────────────────────────────────────

def is_cospot(plate: dict, index: int) -> bool:
    return plate['lanes'][index]['cospot'] is not None


def shown_spots(plate: dict, index: int) -> list[dict]:
    """Every spot drawn in a lane, each with `source` = (lane, spot index) it is stored as.

    A co-spot lane runs its own spots and its two samples' together; two closer than
    MERGE_RF are one spot, drawn once (the stronger look wins, so a faint impurity under a
    strong product does not wash it out).
    """
    entry = plate['lanes'][index]
    shown = [dict(item, source=(index, number)) for number, item in enumerate(entry['spots'])]
    if entry['cospot'] is not None:
        for sample in entry['cospot']:
            if is_cospot(plate, sample):
                continue                      # a co-spot of a co-spot is not drawn twice
            for number, item in enumerate(plate['lanes'][sample]['spots']):
                twin = next((other for other in shown if abs(other['rf'] - item['rf']) < MERGE_RF), None)
                if twin is None:
                    shown.append(dict(item, source=(sample, number)))
                elif INTENSITIES.index(item['intensity']) < INTENSITIES.index(twin['intensity']):
                    twin.update({key: item[key] for key in ('intensity', 'shape', 'colour')})
    shown.sort(key=lambda item: item['rf'])
    return shown


def spot_colour(plate: dict, item: dict) -> str:
    return item.get('colour') or stains.get(plate['stain'])['spot']


# ── Edits ────────────────────────────────────────────────────────────────

class PlateError(ValueError):
    """An edit the plate cannot take; the message is shown to the user."""


def add_lane(plate: dict, label: str = '', cospot: list[int] | None = None) -> int:
    if len(plate['lanes']) >= MAX_LANES:
        raise PlateError(f'A plate holds at most {MAX_LANES} lanes.')
    plate['lanes'].append(lane(label[:MAX_LABEL] or str(len(plate['lanes']) + 1), cospot))
    return len(plate['lanes']) - 1


def add_cospot_lane(plate: dict) -> int:
    """A co-spot of the first sample lane and the last, as reactions are followed."""
    samples = [index for index in range(len(plate['lanes'])) if not is_cospot(plate, index)]
    if len(samples) < 2:
        raise PlateError('A co-spot needs two sample lanes.')
    return add_lane(plate, 'Co', [samples[0], samples[-1]])


def remove_lane(plate: dict, index: int) -> None:
    if len(plate['lanes']) <= 1:
        raise PlateError('A plate needs at least one lane.')
    del plate['lanes'][index]
    for number, entry in enumerate(plate['lanes']):
        if entry['cospot'] is None:
            continue
        if index in entry['cospot']:
            entry['cospot'] = None             # its sample is gone: a sample lane of its own
        else:
            entry['cospot'] = [value - 1 if value > index else value for value in entry['cospot']]
        entry['cospot'] = _valid_cospot(plate, number, entry['cospot'])


def add_spot(plate: dict, index: int, rf: float) -> int:
    spots = plate['lanes'][index]['spots']
    if len(spots) >= MAX_SPOTS:
        raise PlateError(f'A lane holds at most {MAX_SPOTS} spots.')
    spots.append(spot(rf))
    return len(spots) - 1


def set_labels(plate: dict, labels: list[str]) -> None:
    """Labels lanes from the left, adding lanes for any labels beyond the last."""
    labels = [label.strip()[:MAX_LABEL] for label in labels][:MAX_LANES]
    while len(plate['lanes']) < len(labels):
        add_lane(plate)
    for entry, label in zip(plate['lanes'], labels):
        entry['label'] = label


def parse_labels(text: str) -> list[str]:
    """"SM, Co, Rxn" or "SM Co Rxn" → the labels; commas win when there are any."""
    parts = text.split(',') if ',' in text else text.split()
    return [part.strip() for part in parts if part.strip()]
