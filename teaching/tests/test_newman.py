"""The Newman picture and its dialog."""

from teaching import newman

ANSWER = {
    'front': {'atom': 'c2', 'substituents': [
        {'atom': 'c1', 'label': 'CH3', 'element': 'C', 'angle': 0.0},
        {'atom': None, 'label': 'H', 'element': 'H', 'angle': 120.0},
        {'atom': None, 'label': 'H', 'element': 'H', 'angle': 240.0}]},
    'back': {'atom': 'c3', 'substituents': [
        {'atom': 'c4', 'label': 'CH3', 'element': 'C', 'angle': 180.0},
        {'atom': None, 'label': 'H', 'element': 'H', 'angle': 300.0},
        {'atom': None, 'label': 'H', 'element': 'H', 'angle': 60.0}]},
    'dihedral': 180.0, 'rotatable': True,
}


def test_the_model_from_an_answer():
    model = newman.from_projection(ANSWER)
    assert model['dihedral'] == model['modelled'] == 180.0
    assert [g['label'] for g in model['front']] == ['CH3', 'H', 'H']


def test_turning_moves_the_back_groups_together():
    model = newman.from_projection(ANSWER)
    gauche = newman.turned(model, 60)
    assert [g['angle'] for g in gauche['back']] == [60.0, 180.0, 300.0]
    assert gauche['front'] == model['front']


def test_the_picture_has_a_circle_and_six_labelled_bonds():
    ops = newman.drawing(newman.from_projection(ANSWER))['ops']
    assert sum(op['op'] == 'ellipse' for op in ops) == 1
    assert sum(op['op'] == 'line' for op in ops) == 6
    assert sorted(op['text'] for op in ops if op['op'] == 'text') == ['CH₃', 'CH₃', 'H', 'H', 'H', 'H']


def test_the_back_carbon_hides_the_middle_of_the_back_bonds():
    ops = newman.drawing(newman.from_projection(ANSWER))['ops']
    circle = next(i for i, op in enumerate(ops) if op['op'] == 'ellipse')
    # Back bonds before the circle (drawn under it), front bonds after.
    assert all(op['from'] == ops[circle]['center'] for op in ops[circle + 1:] if op['op'] == 'line')


def test_eclipsed_back_bonds_are_drawn_a_little_round():
    eclipsed = newman.turned(newman.from_projection(ANSWER), 0)
    lines = [op for op in newman.drawing(eclipsed)['ops'] if op['op'] == 'line']
    starts = {tuple(op['from']) for op in lines}
    assert len(starts) > 1


def test_the_dialog_turns_by_preset_and_by_number():
    session = newman.Session(newman.from_projection(ANSWER))
    answer = session.handle({'event': {'type': 'change', 'field': 'preset', 'value': 'eclipsed'}})
    assert session.newman['dihedral'] == 0
    assert 'fields' in answer
    answer = session.handle({'event': {'type': 'change', 'field': 'dihedral', 'value': 90}})
    assert session.newman['dihedral'] == 90
    assert 'fields' not in answer


def test_a_ring_bond_does_not_turn():
    session = newman.Session({**newman.from_projection(ANSWER), 'rotatable': False})
    assert session.handle({'event': {'type': 'change', 'field': 'dihedral', 'value': 90}}) == {}
    assert session.request()['fields'][0]['type'] == 'note'


def test_round_trip():
    model = newman.from_projection(ANSWER)
    assert newman.load(newman.dump(model)) == model
    assert newman.load('{"v": 1}') is None


def test_formula_labels_set_their_counts_low():
    assert newman.formula_text('NH2') == 'NH₂'
    assert newman.formula_text('CH2OH') == 'CH₂OH'
    assert newman.formula_text('C(CH3)3') == 'C(CH₃)₃'
    assert newman.formula_text('CO2Et') == 'CO₂Et'
    assert newman.formula_text('H') == 'H'
