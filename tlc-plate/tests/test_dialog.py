"""Edit TLC: what each thing the user does in the dialog changes, and what is redrawn."""

from tlc import drawing, model
from tlc.dialog import Session


def click(session, x, y, double=False):
    return session.handle({'event': {'type': 'click', 'point': [x, y], 'double': double}})


def change(session, field, value):
    return session.handle({'event': {'type': 'change', 'field': field, 'value': value}})


def button(session, id):
    return session.handle({'event': {'type': 'button', 'id': id}})


def drag(session, start, end, phase):
    return session.handle({'event': {'type': 'drag', 'phase': phase, 'from': start, 'to': end}})


def field_ids(answer):
    return [field.get('id') for field in answer['fields'] if field.get('id')]


def test_the_request_is_an_interactive_picture_and_fields():
    request = Session(model.new_plate()).request()
    assert request['title'] == 'Edit TLC Plate'
    assert request['picture']['interactive'] is True
    assert {'stain', 'eluent', 'showRf'} <= {field.get('id') for field in request['fields']}


def test_a_click_in_a_lane_adds_a_spot_and_selects_it():
    session = Session(model.new_plate())
    answer = click(session, drawing.lane_x(0), drawing.spot_y(0.4))
    assert session.plate['lanes'][0]['spots'] == [model.spot(0.4)]
    assert session.spot == (0, 0)
    assert 'spot-rf' in field_ids(answer) and 'lane-label' in field_ids(answer)
    assert '0.40' in answer['message']


def test_a_click_on_a_spot_selects_it_and_a_double_click_deletes_it():
    plate = model.new_plate()
    plate['lanes'][2]['spots'].append(model.spot(0.5))
    session = Session(plate)
    click(session, drawing.lane_x(2), drawing.spot_y(0.5))
    assert session.spot == (2, 0)
    assert len(session.plate['lanes'][2]['spots']) == 1
    click(session, drawing.lane_x(2), drawing.spot_y(0.5), double=True)
    assert session.plate['lanes'][2]['spots'] == []
    assert session.spot is None


def test_a_click_below_the_baseline_selects_the_lane_and_outside_deselects():
    session = Session(model.new_plate())
    click(session, drawing.lane_x(1), drawing.PLATE_HEIGHT + 10)
    assert session.lane == 1 and session.spot is None
    assert 'cospot-a' in field_ids(session.handle({'event': {'type': 'button', 'id': 'none'}}) or {'fields': session.fields()})
    click(session, 1, 1)
    assert session.lane is None


def test_dragging_moves_a_spot_live_and_to_another_lane():
    plate = model.new_plate()
    plate['lanes'][0]['spots'].append(model.spot(0.2))
    session = Session(plate)
    start = [drawing.lane_x(0), drawing.spot_y(0.2)]
    moving = drag(session, start, [drawing.lane_x(0), drawing.spot_y(0.5)], 'move')
    assert 'fields' not in moving and 'picture' in moving
    assert session.plate['lanes'][0]['spots'][0]['rf'] == 0.5
    done = drag(session, start, [drawing.lane_x(2), drawing.spot_y(0.7)], 'end')
    assert session.plate['lanes'][0]['spots'] == []
    assert session.plate['lanes'][2]['spots'][0]['rf'] == 0.7
    assert 'fields' in done


def test_a_drag_from_nowhere_does_nothing():
    session = Session(model.new_plate())
    assert drag(session, [1, 1], [5, 5], 'move') == {}


def test_spot_fields_change_the_spot():
    plate = model.new_plate()
    plate['lanes'][0]['spots'].append(model.spot(0.2))
    session = Session(plate)
    click(session, drawing.lane_x(0), drawing.spot_y(0.2))
    change(session, 'spot-rf', 0.35)
    change(session, 'spot-intensity', 'faint')
    change(session, 'spot-shape', 'tailing')
    change(session, 'spot-colour', '#123456')
    assert session.plate['lanes'][0]['spots'][0] == model.spot(0.35, 'faint', 'tailing', '#123456')
    button(session, 'stain-colour')
    assert session.plate['lanes'][0]['spots'][0]['colour'] is None
    button(session, 'remove-spot')
    assert session.plate['lanes'][0]['spots'] == []


def test_plate_fields_and_lane_buttons():
    session = Session(model.new_plate())
    change(session, 'stain', 'kmno4')
    change(session, 'eluent', '20% EtOAc/hexanes')
    change(session, 'showRf', True)
    assert (session.plate['stain'], session.plate['eluent'], session.plate['showRf']) == \
        ('kmno4', '20% EtOAc/hexanes', True)
    button(session, 'add-lane')
    assert len(session.plate['lanes']) == 4 and session.lane == 3
    change(session, 'lane-label', 'P')
    assert session.plate['lanes'][3]['label'] == 'P'
    button(session, 'remove-lane')
    assert len(session.plate['lanes']) == 3


def test_a_lane_becomes_a_cospot_of_two_samples():
    plate = model.new_plate()
    model.add_lane(plate, 'P')
    session = Session(plate)
    click(session, drawing.lane_x(3), drawing.PLATE_HEIGHT + 10)
    change(session, 'lane-kind', 'cospot')
    assert session.plate['lanes'][3]['cospot'] == [0, 2]
    change(session, 'cospot-b', '0')
    assert session.plate['lanes'][3]['cospot'] == [0, 2]   # the same lane twice is refused
    change(session, 'lane-kind', 'sample')
    assert session.plate['lanes'][3]['cospot'] is None


def test_a_limit_is_a_message_not_an_error():
    session = Session(model.new_plate())
    for _ in range(model.MAX_LANES):
        answer = button(session, 'add-lane')
    assert 'at most' in answer['message']


def test_the_working_copy_is_not_the_plate():
    plate = model.new_plate()
    session = Session(plate)
    click(session, drawing.lane_x(0), drawing.spot_y(0.4))
    assert plate['lanes'][0]['spots'] == []
