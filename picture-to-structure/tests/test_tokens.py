from p2s import tokens


def test_organic_subset_and_two_letter_halogens():
    assert tokens.parse('C').element == 'C'
    assert tokens.parse('Cl').element == 'Cl'
    assert tokens.parse('Br').alias is None


def test_aromatic_atoms_are_their_element():
    label = tokens.parse('c')
    assert (label.element, label.aromatic) == ('C', True)
    assert tokens.parse('[nH]').element == 'N'


def test_bracket_atoms_carry_charge_and_isotope():
    assert tokens.parse('[NH+]').charge == 1
    assert tokens.parse('[O-]').charge == -1
    assert tokens.parse('[Fe+2]').charge == 2
    assert tokens.parse('[N++]').charge == 2
    label = tokens.parse('[13CH3]')
    assert (label.element, label.isotope) == ('C', 13)
    assert tokens.parse('[C@@H]').element == 'C'


def test_abbreviations_are_kept_as_text():
    for text, alias in [('[OMe]', 'OMe'), ('[Ph]', 'Ph'), ('[CO2Et]', 'CO2Et'), ('[R1]', 'R1'), ('Boc', 'Boc')]:
        label = tokens.parse(text)
        assert label.element is None
        assert label.alias == alias


def test_a_bare_element_outside_the_organic_subset():
    assert tokens.parse('Si').element == 'Si'


def test_abbreviations_that_spell_elements_stay_abbreviations():
    for text in ('[Ts]', '[Ac]', '[Pr]', '[Ar]', '[Y]'):
        label = tokens.parse(text)
        assert (label.element, label.alias) == (None, text[1:-1])
    assert tokens.parse('[Rb+]').element == 'Rb'      # a charged ion is still the element


def test_numbered_dummy_atoms_are_r_groups():
    assert tokens.parse('[2*]').alias == 'R2'
    assert tokens.parse('[13*]').alias == 'R13'
    assert tokens.parse('*').alias == 'R'
    assert tokens.parse('[R7]').alias == 'R7'
