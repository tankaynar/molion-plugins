"""Present Mechanism's plan: stages by reaction arrows, curved arrows by stage and step."""

import pytest

from teaching import mechanism


def molecule(ident, x, y=0):
    return {'id': ident, 'atoms': [{'id': ident + '-a', 'x': x - 20, 'y': y}, {'id': ident + '-b', 'x': x + 20, 'y': y}],
            'bonds': [{'id': ident + '-ab', 'atomA': ident + '-a', 'atomB': ident + '-b'}]}


def curved(ident, atom, x, y=0):
    return {'id': ident, 'source': {'kind': 'atom', 'id': atom}, 'target': {'kind': 'atom', 'id': atom},
            'from': {'x': x, 'y': y}, 'to': {'x': x + 10, 'y': y}}


def sn2_scene():
    return {
        'molecules': [molecule('nucleophile', 0), molecule('substrate', 100), molecule('product', 400)],
        'arrows': [{'id': 'r1', 'x1': 200, 'y1': 0, 'x2': 300, 'y2': 0}],
        'annotations': [{'id': 'plus', 'x': 50, 'y': 0}, {'id': 'leaving', 'x': 480, 'y': 0}],
        'curvedArrows': [curved('push2', 'substrate-a', 110), curved('push1', 'nucleophile-a', 5)],
    }


def test_the_first_stage_then_each_arrow_then_the_next_stage():
    plan = mechanism.plan(sn2_scene())
    steps = [step['reveal'] for step in plan['steps']]
    assert steps[0] == {}
    assert steps[1] == {'curvedArrows': ['push1']}           # read left to right
    assert steps[2] == {'curvedArrows': ['push2']}
    assert steps[3] == {'arrows': ['r1'], 'moleculeIds': ['product'], 'annotations': ['leaving']}
    assert len(steps) == 4


def test_step_marks_order_the_arrows_and_caption_them():
    plan = mechanism.plan(sn2_scene(), {'push2': '1|Bond breaks', 'push1': '2'})
    assert plan['steps'][1] == {'reveal': {'curvedArrows': ['push2']}, 'caption': 'Bond breaks'}
    assert plan['steps'][2]['reveal'] == {'curvedArrows': ['push1']}


def test_nothing_to_present():
    with pytest.raises(ValueError):
        mechanism.plan({'molecules': [molecule('m', 0)]})


def test_a_curved_arrow_off_any_structure_goes_with_the_nearest():
    scene = sn2_scene()
    scene['curvedArrows'].append({'id': 'free', 'source': {'kind': 'position', 'x': 395, 'y': 5},
                                  'target': {'kind': 'position', 'x': 405, 'y': 5}, 'from': {'x': 395, 'y': 5}})
    plan = mechanism.plan(scene)
    assert plan['steps'][-1]['reveal'] == {'curvedArrows': ['free']}


@pytest.mark.parametrize('text, expected', [('3', (3, None)), ('2|Proton transfer', (2, 'Proton transfer')),
                                            (None, (mechanism.UNNUMBERED, None)), ('x', (mechanism.UNNUMBERED, None))])
def test_step_values(text, expected):
    assert mechanism.step_value(text) == expected
