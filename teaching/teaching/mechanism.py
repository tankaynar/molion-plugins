"""Present Mechanism: the steps of a drawn mechanism, for Molion's presenter. Pure.

A scheme is stages joined by reaction arrows, read in reading order (rows top to bottom,
each left to right). Every structure, text and curved arrow belongs to a stage: the
structures and text by where they sit between the reaction arrows, a curved arrow by the
structure its tail (else its head) is on. The presentation opens on the first stage
without its curved arrows; then each curved arrow is a step, in the order its step mark
gives (Set Step…) or else the order its tail is read in; then the next reaction arrow comes
with the next stage's structures and text, and so on.
"""

from __future__ import annotations

from . import geometry

UNNUMBERED = 10_000


def step_value(text: str | None) -> tuple[int, str | None]:
    """A step mark ("3" or "3|Proton transfer") as (number, caption)."""
    if not text:
        return (UNNUMBERED, None)
    number, _, caption = text.partition('|')
    try:
        return (int(number), caption.strip() or None)
    except ValueError:
        return (UNNUMBERED, None)


def _molecule_centre(mol: dict) -> tuple[float, float]:
    return geometry.centre(geometry.molecule_box(mol))


def plan(scene: dict, steps: dict[str, str] | None = None, title: str | None = None) -> dict:
    """The `present` request for a scene (a get-scene answer). `steps` are the curved arrows'
    step marks, by id. Raises ValueError when there is nothing to step through."""
    steps = steps or {}
    molecules = [m for m in scene.get('molecules') or [] if m.get('atoms')]
    arrows = scene.get('arrows') or []
    annotations = scene.get('annotations') or []
    curved = scene.get('curvedArrows') or []
    if not curved and not arrows:
        raise ValueError('Nothing to step through: draw the mechanism’s curved arrows first.')

    # Everything with a place, read in order; a reaction arrow by its midpoint.
    items = [('m:' + m['id'], *_molecule_centre(m)) for m in molecules]
    items += [('a:' + a['id'], (a['x1'] + a['x2']) / 2, (a['y1'] + a['y2']) / 2) for a in arrows]
    items += [('t:' + t['id'], t['x'], t['y']) for t in annotations]
    order = geometry.reading_order(items)

    stage_of: dict[str, int] = {}
    stage = 0
    arrow_order = []
    for key in order:
        if key.startswith('a:'):
            stage += 1
            arrow_order.append(key[2:])
            stage_of[key] = stage
        else:
            stage_of[key] = stage
    stages = stage

    atom_molecule = {atom['id']: m['id'] for m in molecules for atom in m['atoms']}
    bond_molecule = {bond['id']: m['id'] for m in molecules for bond in m['bonds']}

    def anchor_stage(anchor: dict) -> int | None:
        kind, ident = anchor.get('kind'), anchor.get('id')
        mol = atom_molecule.get(ident) if kind == 'atom' else bond_molecule.get(ident) if kind == 'bond' else None
        return stage_of.get('m:' + mol) if mol else None

    def nearest_stage(point: dict | None) -> int:
        if not point or not molecules:
            return 0
        best = min(molecules, key=lambda m: (_molecule_centre(m)[0] - point['x']) ** 2 + (_molecule_centre(m)[1] - point['y']) ** 2)
        return stage_of['m:' + best['id']]

    curved_by_stage: dict[int, list[dict]] = {}
    for arrow in curved:
        where = anchor_stage(arrow['source'])
        if where is None:
            where = anchor_stage(arrow['target'])
        if where is None:
            where = nearest_stage(arrow.get('from'))
        curved_by_stage.setdefault(where, []).append(arrow)

    rows = geometry.rows([(c['id'], (c.get('from') or {}).get('x', 0), (c.get('from') or {}).get('y', 0)) for c in curved])

    def curved_key(arrow: dict):
        number, _ = step_value(steps.get(arrow['id']))
        start = arrow.get('from') or {'x': 0, 'y': 0}
        return (number, rows.get(arrow['id'], 0), start['x'], start['y'])

    result_steps = [{'reveal': {}}]
    for k in range(stages + 1):
        if k > 0:
            reveal = {'arrows': [arrow_order[k - 1]],
                      'moleculeIds': [m['id'] for m in molecules if stage_of['m:' + m['id']] == k],
                      'annotations': [t['id'] for t in annotations if stage_of['t:' + t['id']] == k]}
            result_steps.append({'reveal': {key: ids for key, ids in reveal.items() if ids}})
        for arrow in sorted(curved_by_stage.get(k, []), key=curved_key):
            _, caption = step_value(steps.get(arrow['id']))
            step = {'reveal': {'curvedArrows': [arrow['id']]}}
            if caption:
                step['caption'] = caption
            result_steps.append(step)

    request = {'steps': result_steps}
    if title:
        request['title'] = title
    return request
