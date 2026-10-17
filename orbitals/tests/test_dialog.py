"""Edit Orbital: the working copy changes with every event; the picture is redrawn."""

from orbitals import model
from orbitals.dialog import Session


def change(session, field, value):
    return session.handle({'event': {'type': 'change', 'field': field, 'value': value}})


def test_the_request_shows_the_orbital_and_its_fields():
    request = Session(model.new_orbital('p')).request()
    assert request['title'] == 'Edit Orbital'
    ids = [field.get('id') for field in request['fields']]
    assert ids[:4] == ['type', 'phase', 'positive', 'negative']


def test_changing_the_type_redraws():
    session = Session(model.new_orbital('p'))
    answer = change(session, 'type', 'dxy')
    assert session.orbital['type'] == 'dxy'
    assert 'picture' in answer and 'fields' not in answer


def test_outline_hides_the_colours():
    session = Session(model.new_orbital('p'))
    answer = change(session, 'phase', 'none')
    assert 'positive' not in [field.get('id') for field in answer['fields']]


def test_a_bad_colour_is_a_message_not_a_change():
    session = Session(model.new_orbital('p'))
    answer = change(session, 'positive', 'blue')
    assert answer == {'message': 'A colour is #RRGGBB.'}
    assert session.orbital['colours'][0] == model.POSITIVE


def test_turning_buttons():
    session = Session(model.new_orbital('p'))
    session.handle({'event': {'type': 'button', 'id': 'rotate-right'}})
    assert session.orbital['angle'] == 0


def test_the_original_is_untouched():
    orbital = model.new_orbital('p')
    session = Session(orbital)
    change(session, 'angle', 45)
    assert orbital['angle'] == -90
