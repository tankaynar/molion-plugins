"""The plate as data: reading back, the teaching example's plates, co-spots and edits."""

import pytest

from tlc import model


def test_a_new_plate_follows_a_reaction():
    plate = model.new_plate()
    assert [lane['label'] for lane in plate['lanes']] == ['SM', 'Co', 'Rxn']
    assert plate['lanes'][1]['cospot'] == [0, 2]


def test_a_plate_survives_a_round_trip():
    plate = model.new_plate()
    plate['lanes'][0]['spots'].append(model.spot(0.42, 'faint', 'streak', '#112233'))
    plate['eluent'] = '30% EtOAc/hexanes'
    assert model.load(model.dump(plate)) == plate


def test_the_teaching_examples_plates_are_read():
    plate = model.load('{"lanes": 2, "spots": [{"lane": 1, "rf": 0.5}, {"lane": 7, "rf": 0.1}]}')
    assert [lane['label'] for lane in plate['lanes']] == ['1', '2']
    assert plate['lanes'][1]['spots'][0]['rf'] == 0.5
    assert plate['lanes'][0]['spots'] == []


@pytest.mark.parametrize('text', ['', 'nonsense', '[]', '{"lanes": "x"}', None])
def test_anything_else_is_not_a_plate(text):
    assert model.load(text) is None


def test_what_is_read_back_is_checked():
    plate = model.load('{"stain": "glitter", "lanes": [{"label": "a very long label indeed", "cospot": [0, 9],'
                       ' "spots": [{"rf": 3, "intensity": "loud", "shape": "cube", "colour": "red"}]}]}')
    assert plate['stain'] == 'uv254'
    assert len(plate['lanes'][0]['label']) == model.MAX_LABEL
    assert plate['lanes'][0]['cospot'] is None
    assert plate['lanes'][0]['spots'][0] == {'rf': 1.0, 'intensity': 'strong', 'shape': 'round', 'colour': None}


def test_a_cospot_runs_both_samples_and_merges_twins():
    plate = model.new_plate()
    plate['lanes'][0]['spots'] = [model.spot(0.30, 'faint'), model.spot(0.60)]
    plate['lanes'][2]['spots'] = [model.spot(0.31), model.spot(0.80)]
    shown = model.shown_spots(plate, 1)
    assert [item['rf'] for item in shown] == [0.30, 0.60, 0.80]
    # The twin at 0.30/0.31 takes the stronger look.
    assert shown[0]['intensity'] == 'strong'
    assert shown[0]['source'] == (0, 0)


def test_removing_a_sample_unlinks_its_cospot():
    plate = model.new_plate()
    model.remove_lane(plate, 2)
    assert plate['lanes'][1]['cospot'] is None
    plate = model.new_plate()
    model.add_lane(plate, 'P')
    model.remove_lane(plate, 0)
    assert all(lane['cospot'] is None for lane in plate['lanes'])


def test_removing_a_lane_shifts_cospots_after_it():
    plate = model.new_plate()
    model.add_lane(plate, 'P')
    plate['lanes'].insert(0, model.lane('X'))
    plate['lanes'][2]['cospot'] = [1, 3]
    model.remove_lane(plate, 0)
    assert plate['lanes'][1]['cospot'] == [0, 2]


def test_limits_are_messages():
    plate = model.new_plate()
    while len(plate['lanes']) < model.MAX_LANES:
        model.add_lane(plate)
    with pytest.raises(model.PlateError):
        model.add_lane(plate)
    single = {'version': 2, 'stain': 'none', 'eluent': '', 'showRf': False, 'lanes': [model.lane('1')]}
    with pytest.raises(model.PlateError):
        model.remove_lane(single, 0)
    with pytest.raises(model.PlateError):
        model.add_cospot_lane(single)


def test_labels_add_lanes_beyond_the_last():
    plate = model.new_plate()
    model.set_labels(plate, model.parse_labels('SM, Co, Rxn, Product'))
    assert [lane['label'] for lane in plate['lanes']] == ['SM', 'Co', 'Rxn', 'Product']
    assert model.parse_labels('A B  C') == ['A', 'B', 'C']
    assert model.parse_labels('crude A, pure A') == ['crude A', 'pure A']
