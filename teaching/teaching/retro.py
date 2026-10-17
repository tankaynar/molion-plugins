"""Retrosynthetic Disconnect: a bond cut into synthons, drawn beside the target with the retro
arrow and a wavy line across the bond.

The synthons come from Molion's get-fragments (Molion cuts the bond and puts the
charges on); this file offers the ways of cutting it, and lays the result out.
"""

from __future__ import annotations

import math

from .geometry import BOND

SUPERSCRIPT = {'+': '⁺', '-': '⁻', '•': '•'}


def option_label(polarity: dict, elements: dict[str, str], mode: str) -> str:
    """"C⁺ and O⁻", or "C• and O•", for the bond's two ends."""
    if mode == 'homolytic':
        a, b = polarity['bond']
        return f"{elements.get(a, '?')}• and {elements.get(b, '?')}• (radicals)"
    return (f"{elements.get(polarity['positive'], '?')}{SUPERSCRIPT['+']} and "
            f"{elements.get(polarity['negative'], '?')}{SUPERSCRIPT['-']}")


def options(answers: list[tuple[str, dict]], elements: dict[str, str]) -> list[dict]:
    """The ways of cutting the bond that worked, each {value, label, answer}: `answers` are
    (mode, get-fragments answer) in the order offered."""
    result = []
    for n, (mode, answer) in enumerate(answers):
        polarity = (answer.get('polarity') or [None])[0]
        if polarity is None or not answer.get('fragments'):
            continue
        result.append({'value': str(n), 'label': option_label(polarity, elements, mode), 'answer': answer})
    return result


def wavy(length: float = 0.9 * BOND, waves: int = 3, amplitude: float = 4.0) -> dict:
    """The disconnection mark: a wavy line across the bond, as a picture (length along x)."""
    pad = amplitude + 2
    steps = waves * 12
    points = [(length * i / steps, pad + amplitude * math.sin(2 * math.pi * waves * i / steps)) for i in range(steps + 1)]
    ops = [{'op': 'line', 'from': [round(x1, 2), round(y1, 2)], 'to': [round(x2, 2), round(y2, 2)],
            'color': '#000000', 'width': 1.6, 'cap': 'round'}
           for (x1, y1), (x2, y2) in zip(points, points[1:])]
    return {'width': round(length, 2), 'height': round(2 * pad, 2), 'ops': ops}


def bond_mark(a: dict, b: dict) -> dict:
    """Where the wavy line goes: the bond's midpoint, turned across it (degrees, clockwise)."""
    angle = math.degrees(math.atan2(b['y'] - a['y'], b['x'] - a['x'])) + 90.0
    return {'x': (a['x'] + b['x']) / 2, 'y': (a['y'] + b['y']) / 2, 'rotation': round(angle % 360.0, 2)}
