"""The picture: within Molion's limits, in its vocabulary, and hit-testable."""

import re

from tlc import drawing, model, stains

OPS = {'line', 'polygon', 'ellipse', 'rect', 'text', 'bezier', 'group'}
COLOUR = re.compile(r'^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$')


def walk(ops):
    for op in ops:
        yield op
        if op['op'] == 'group':
            yield from walk(op['ops'])


def full_plate():
    plate = model.new_plate()
    while len(plate['lanes']) < model.MAX_LANES:
        model.add_lane(plate)
    for lane in plate['lanes']:
        lane['spots'] = [model.spot(index / model.MAX_SPOTS, shape=model.SHAPES[index % 3])
                         for index in range(model.MAX_SPOTS)]
    plate['showRf'] = True
    plate['eluent'] = 'x' * model.MAX_ELUENT
    plate['stain'] = 'uv254'
    return plate


def test_the_fullest_plate_is_within_the_picture_limit():
    picture = drawing.drawing(full_plate())
    count = sum(1 + len(op.get('points', [])) for op in walk(picture['ops']))
    assert count <= 10_000


def test_every_op_is_one_molion_draws():
    for stain in stains.STAINS:
        plate = full_plate()
        plate['stain'] = stain['id']
        picture = drawing.drawing(plate, selected={'lane': 1, 'spot': (0, 0)})
        for op in walk(picture['ops']):
            assert op['op'] in OPS
            for key in ('fill', 'stroke', 'color'):
                if key in op:
                    assert COLOUR.match(op[key]), op
            if op['op'] == 'text':
                assert len(op['text']) <= 200


def test_the_preview_is_within_the_preview_limit():
    preview = drawing.preview(model.new_plate())
    assert sum(1 + len(op.get('points', [])) for op in walk(preview['ops'])) <= 2000
    assert preview['ops'][0]['origin'] == 'cursor'


def test_a_caption_only_when_there_is_something_to_say():
    plate = model.new_plate()
    plate['stain'] = 'none'
    assert drawing.height(plate) == drawing.PLATE_HEIGHT + drawing.LABEL_HEIGHT
    plate['eluent'] = '5% MeOH/DCM'
    plate['stain'] = 'kmno4'
    assert drawing.caption(plate) == '5% MeOH/DCM, KMnO₄'
    assert drawing.height(plate) == drawing.PLATE_HEIGHT + drawing.LABEL_HEIGHT + drawing.CAPTION_HEIGHT


def test_spots_are_found_where_they_are_drawn():
    plate = model.new_plate()
    plate['lanes'][2]['spots'].append(model.spot(0.5))
    x, y = drawing.lane_x(2), drawing.spot_y(0.5)
    lane, item = drawing.spot_at(plate, x + 3, y + 2)
    assert lane == 2 and item['source'] == (2, 0)
    # The co-spot lane shows it too, and a hit there still names the sample's spot.
    lane, item = drawing.spot_at(plate, drawing.lane_x(1), y)
    assert lane == 1 and item['source'] == (2, 0)
    assert drawing.spot_at(plate, x, drawing.spot_y(0.9)) is None
    assert drawing.rf_at(y) == 0.5
    assert drawing.lane_at(plate, 1) is None
