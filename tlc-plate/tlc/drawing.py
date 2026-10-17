"""The plate as a vector picture: Molion's display-list ops in the plate's own units.

The same drawing is placed on the canvas and shown in the Edit TLC dialog; the dialog's copy
also marks what is selected. Molion stretches the box (0..width × 0..height) onto the picture,
so these units are only proportions.
"""

from __future__ import annotations

from . import model, stains

LANE_WIDTH = 56
MARGIN = 20
PLATE_HEIGHT = 300
FRONT_Y = 28                       # solvent front
BASELINE_Y = PLATE_HEIGHT - 28     # where the samples were applied
# Lane labels and the caption sit below the plate, on neutral ground: on a coloured plate
# (KMnO₄'s purple) pencil-grey text would not read, least of all on a dark screen, where
# Molion mirrors neutral ink to light but leaves colours as they are.
LABEL_HEIGHT = 22
CAPTION_HEIGHT = 20
SPOT_RX, SPOT_RY = 10, 7

EDGE = '#8C8C8C'
PENCIL = '#5E5E5E'
PAPER = '#FFFFFF'
SELECTION = '#1E90FF'              # DodgerBlue, as every selection in Molion

ALPHA = {'strong': ('E6', '50'), 'medium': ('A6', '38'), 'faint': ('5C', '22')}


# ── Geometry ─────────────────────────────────────────────────────────────

def plate_width(plate: dict) -> int:
    return MARGIN * 2 + LANE_WIDTH * len(plate['lanes'])


def caption(plate: dict) -> str:
    stain = stains.get(plate['stain'])['caption']
    parts = [part for part in (plate['eluent'].strip(), stain) if part]
    return ', '.join(parts)


def height(plate: dict) -> int:
    return PLATE_HEIGHT + LABEL_HEIGHT + (CAPTION_HEIGHT if caption(plate) else 0)


def lane_x(index: int) -> float:
    return MARGIN + LANE_WIDTH * (index + 0.5)


def spot_y(rf: float) -> float:
    return BASELINE_Y - rf * (BASELINE_Y - FRONT_Y)


def rf_at(y: float) -> float:
    return model.clamp_rf((BASELINE_Y - y) / (BASELINE_Y - FRONT_Y))


def lane_at(plate: dict, x: float) -> int | None:
    index = int((x - MARGIN) // LANE_WIDTH)
    return index if 0 <= index < len(plate['lanes']) and x >= MARGIN else None


def spot_at(plate: dict, x: float, y: float, reach: float = 14) -> tuple[int, dict] | None:
    """The shown spot nearest (x, y) within `reach`, with the lane it is shown in."""
    best, best_distance = None, reach * reach
    for index in range(len(plate['lanes'])):
        for item in model.shown_spots(plate, index):
            dx, dy = lane_x(index) - x, (spot_y(item['rf']) - y) * SPOT_RX / SPOT_RY
            distance = dx * dx + dy * dy
            if distance <= best_distance:
                best, best_distance = (index, item), distance
    return best


# ── Drawing ──────────────────────────────────────────────────────────────

def drawing(plate: dict, alpha: str = '', selected: dict | None = None) -> dict:
    """`{width, height, ops}` for add-image/update-image and the dialog.

    `alpha` ("80") fades everything, for the placement preview. `selected` is the dialog's
    selection: {"lane": i} and optionally {"spot": (lane, number)}, drawn in DodgerBlue.
    """
    width = plate_width(plate)
    stain = stains.get(plate['stain'])
    pencil = stain.get('pencil', PENCIL)
    fade = alpha
    ops: list[dict] = [
        {'op': 'rect', 'at': [0, 0], 'size': [width, PLATE_HEIGHT],
         'fill': stain['background'] + fade, 'stroke': EDGE + fade, 'width': 1.5},
    ]
    if selected and selected.get('lane') is not None:
        x = MARGIN + LANE_WIDTH * selected['lane']
        ops.append({'op': 'rect', 'at': [x + 2, 4], 'size': [LANE_WIDTH - 4, PLATE_HEIGHT - 8],
                    'fill': SELECTION + '18', 'stroke': SELECTION + '60', 'width': 1})
    ops += [
        {'op': 'line', 'from': [6, FRONT_Y], 'to': [width - 6, FRONT_Y],
         'color': pencil + fade, 'width': 1, 'dash': [5, 4]},
        {'op': 'line', 'from': [6, BASELINE_Y], 'to': [width - 6, BASELINE_Y],
         'color': pencil + fade, 'width': 1},
    ]
    for index, entry in enumerate(plate['lanes']):
        x = lane_x(index)
        ops.append({'op': 'line', 'from': [x, BASELINE_Y - 4], 'to': [x, BASELINE_Y + 4],
                    'color': pencil + fade, 'width': 1})
        label = entry['label'] or str(index + 1)
        ops.append({'op': 'text', 'text': label[:model.MAX_LABEL], 'at': [x, PLATE_HEIGHT + 5],
                    'align': 'middle', 'baseline': 'top', 'size': 13 if len(label) <= 4 else 10,
                    'color': PENCIL + fade})
        for item in model.shown_spots(plate, index):
            ops += _spot(plate, stain, x, item, fade)
            if plate['showRf']:
                # On a paper-coloured backing, so it reads on any stain and either screen.
                y = spot_y(item['rf'])
                ops.append({'op': 'rect', 'at': [x + SPOT_RX + 1, y - 5], 'size': [19, 10],
                            'fill': PAPER + (fade or 'D0')})
                ops.append({'op': 'text', 'text': f"{item['rf']:.2f}",
                            'at': [x + SPOT_RX + 2, y], 'align': 'start',
                            'baseline': 'middle', 'size': 8, 'color': PENCIL + fade})
    if selected and selected.get('spot') is not None:
        lane_index, number = selected['spot']
        if lane_index < len(plate['lanes']) and number < len(plate['lanes'][lane_index]['spots']):
            rf = plate['lanes'][lane_index]['spots'][number]['rf']
            for index in _lanes_showing(plate, lane_index):
                ops.append({'op': 'ellipse', 'center': [lane_x(index), spot_y(rf)],
                            'rx': SPOT_RX + 5, 'ry': SPOT_RY + 5, 'stroke': SELECTION, 'width': 1.5})
    text = caption(plate)
    if text:
        ops.append({'op': 'text', 'text': text, 'at': [width / 2, PLATE_HEIGHT + LABEL_HEIGHT + 2],
                    'align': 'middle', 'baseline': 'top', 'size': 11, 'color': PENCIL + fade})
    return {'width': width, 'height': height(plate), 'ops': ops}


def _lanes_showing(plate: dict, lane_index: int) -> list[int]:
    """The lane a spot is stored in, and the co-spot lanes that run it too."""
    return [lane_index] + [index for index, entry in enumerate(plate['lanes'])
                           if entry['cospot'] is not None and lane_index in entry['cospot']]


def _spot(plate: dict, stain: dict, x: float, item: dict, fade: str) -> list[dict]:
    colour = model.spot_colour(plate, item)
    core, halo = ALPHA[item['intensity']]
    if fade:
        core = halo = fade
    y = spot_y(item['rf'])
    ops: list[dict] = []
    if item['shape'] == 'streak':
        # Smeared from the baseline up to the spot: the whole run is faint, the top darker.
        bottom = min(BASELINE_Y - 4, y + 60)
        middle = (y + bottom) / 2
        ops.append({'op': 'ellipse', 'center': [x, middle], 'rx': SPOT_RX - 2, 'ry': (bottom - y) / 2 + SPOT_RY,
                    'fill': colour + halo})
        ops.append({'op': 'ellipse', 'center': [x, y], 'rx': SPOT_RX - 1, 'ry': SPOT_RY,
                    'fill': colour + core})
    elif item['shape'] == 'tailing':
        tail = min(BASELINE_Y - 4, y + 26)
        ops.append({'op': 'polygon', 'points': [[x - SPOT_RX + 2, y], [x + SPOT_RX - 2, y],
                                                [x + 3, tail], [x - 3, tail]],
                    'fill': colour + halo})
        ops.append({'op': 'ellipse', 'center': [x, y], 'rx': SPOT_RX + 2, 'ry': SPOT_RY + 2, 'fill': colour + halo})
        ops.append({'op': 'ellipse', 'center': [x, y], 'rx': SPOT_RX, 'ry': SPOT_RY, 'fill': colour + core})
    else:
        ops.append({'op': 'ellipse', 'center': [x, y], 'rx': SPOT_RX + 2, 'ry': SPOT_RY + 2, 'fill': colour + halo})
        ops.append({'op': 'ellipse', 'center': [x, y], 'rx': SPOT_RX, 'ry': SPOT_RY, 'fill': colour + core})
    if stain.get('circled'):
        # Under UV the spots fade once the lamp is off, so they are circled in pencil.
        ops.append({'op': 'ellipse', 'center': [x, y], 'rx': SPOT_RX + 4, 'ry': SPOT_RY + 4,
                    'stroke': PENCIL + (fade or 'C0'), 'width': 1})
    return ops


def preview(plate: dict) -> dict:
    """The placement preview: the plate faded, centred under the cursor."""
    picture = drawing(plate, alpha='80')
    return {'ops': [{'op': 'group', 'origin': 'cursor', 'ops': [
        {'op': 'group', 'origin': [-picture['width'] / 2, -picture['height'] / 2], 'ops': picture['ops']}]}]}
