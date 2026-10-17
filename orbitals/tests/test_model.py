"""The orbital as pluginData: made, read back, and refused when it is not ours."""

import pytest

from orbitals import model


def test_a_new_p_orbital_stands_upright():
    assert model.new_orbital('p')['angle'] == -90
    assert model.new_orbital('sp3')['angle'] == 0


def test_round_trip():
    orbital = model.new_orbital('dz2', 30)
    orbital['phase'] = 'signs'
    orbital['flip'] = True
    assert model.load(model.dump(orbital)) == orbital


@pytest.mark.parametrize('text', [None, '', 'not json', '{"v": 2, "type": "p"}', '{"v": 1, "type": "f"}', '[1]'])
def test_what_is_not_an_orbital(text):
    assert model.load(text) is None


def test_bad_fields_fall_back_to_defaults():
    loaded = model.load('{"v": 1, "type": "s", "phase": "glow", "colours": ["red", "#000000"], "angle": "up"}')
    assert loaded == model.new_orbital('s')


@pytest.mark.parametrize('angle, expected', [(0, 0), (180, 180), (190, -170), (-180, 180), (725, 5), (12.345, 12.3)])
def test_angles_are_normal(angle, expected):
    assert model.normal_angle(angle) == expected


def test_unknown_type_is_refused():
    with pytest.raises(model.OrbitalError):
        model.new_orbital('f')


def test_colours_are_checked():
    assert model.colour('#a1b2c3') == '#A1B2C3'
    with pytest.raises(model.OrbitalError):
        model.colour('blue')
