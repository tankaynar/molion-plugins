"""The pictures: within Molion's limits, lobes closed and signed, centred on the nucleus."""

import math

import pytest

from orbitals import drawing, model

PICTURE_LIMIT = 10_000      # ops + polygon points: Molion's limit for a picture
PREVIEW_LIMIT = 2_000


def size(ops):
    return len(ops) + sum(len(op.get('points', [])) for op in ops)


@pytest.mark.parametrize('kind', model.TYPES)
def test_every_orbital_fits_the_limits(kind):
    orbital = model.new_orbital(kind)
    assert size(drawing.drawing(orbital)['ops']) <= PICTURE_LIMIT
    assert size(drawing.preview(orbital)['ops'][0]['ops']) + 1 <= PREVIEW_LIMIT


@pytest.mark.parametrize('kind, lobes', [('s', 1), ('p', 2), ('sp', 2), ('sp2', 2), ('sp3', 2),
                                          ('dxy', 4), ('dx2y2', 4), ('dz2', 4)])
def test_lobe_counts(kind, lobes):
    assert len(drawing.lobes(kind)) == lobes


def test_a_p_orbitals_lobes_have_opposite_signs():
    signs = sorted(sign for sign, _ in drawing.lobes('p'))
    assert signs == [-1, 1]


def test_a_hybrid_has_a_big_front_lobe_and_a_small_back_one():
    reach = {sign: max(math.hypot(x, y) for x, y in points) for sign, points in drawing.lobes('sp3')}
    assert reach[1] == pytest.approx(drawing.LOBE, rel=0.02)
    assert 0.3 * drawing.LOBE < reach[-1] < 0.6 * drawing.LOBE


def test_more_p_character_means_a_bigger_back_lobe():
    def back(kind):
        return max(math.hypot(x, y) for sign, points in drawing.lobes(kind) if sign < 0 for x, y in points)
    assert back('sp') < back('sp2') < back('sp3')


def test_the_box_is_centred_on_the_nucleus():
    picture = drawing.drawing(model.new_orbital('sp3', 30))
    nucleus = picture['ops'][-1]
    assert nucleus['op'] == 'ellipse'
    assert nucleus['center'] == [picture['width'] / 2, picture['height'] / 2]


def test_turning_turns_the_lobes():
    up = drawing.drawing(model.new_orbital('p', -90))
    across = drawing.drawing(model.new_orbital('p', 0))
    assert up['height'] > up['width']
    assert across['width'] > across['height']


def test_shaded_lobes_take_the_phase_colours_and_flip_swaps_them():
    orbital = model.new_orbital('p')
    fills = [op['fill'] for op in drawing.drawing(orbital)['ops'] if op['op'] == 'polygon']
    assert sorted(fills) == sorted([model.POSITIVE + drawing.SHADE_ALPHA, model.NEGATIVE + drawing.SHADE_ALPHA])
    orbital['flip'] = True
    flipped = [op['fill'] for op in drawing.drawing(orbital)['ops'] if op['op'] == 'polygon']
    assert flipped == list(reversed(fills))


def test_signs_are_written_in_outlined_lobes():
    orbital = model.new_orbital('dxy')
    orbital['phase'] = 'signs'
    ops = drawing.drawing(orbital)['ops']
    assert all('fill' not in op for op in ops if op['op'] == 'polygon')
    assert sorted(op['text'] for op in ops if op['op'] == 'text') == ['+', '+', '−', '−']


def test_the_preview_follows_the_drag():
    group = drawing.preview(model.new_orbital('p'))['ops'][0]
    assert (group['origin'], group['rotate']) == ('start', 'vector')
