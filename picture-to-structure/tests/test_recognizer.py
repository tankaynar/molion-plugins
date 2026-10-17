"""The decoding around the model, with no model: token sequences in, atoms and bonds out."""

import json
import os

import pytest

np = pytest.importorskip('numpy')

from p2s.recognizer import Vocabulary, bonds_from, symmetrise  # noqa: E402
from p2s.structure import DOUBLE, HASH, SINGLE, WEDGE  # noqa: E402

SPECIAL = {'pad': 0, 'sos': 1, 'eos': 2, 'unk': 3, 'mask': 4}
STOI = {'<pad>': 0, '<sos>': 1, '<eos>': 2, '<unk>': 3, '<mask>': 4,
        '(': 5, ')': 6, '=': 7, '[': 8, ']': 9, '+': 10, 'C': 11, 'O': 12, 'N': 13, 'l': 14, 'H': 15,
        'M': 16, 'e': 17}
BINS = 64


@pytest.fixture
def vocab():
    return Vocabulary(STOI, BINS, SPECIAL)


def x(v, value):
    return v.offset + value


def y(v, value):
    return v.offset + BINS + value


def test_atoms_their_positions_and_hidden_indices(vocab):
    # C(=O)Cl with coordinates after each atom
    seq = [11, x(vocab, 0), y(vocab, 63), 5, 7, 12, x(vocab, 63), y(vocab, 0), 6,
           11, 14, x(vocab, 21), y(vocab, 42), 2]
    symbols, coords, indices = vocab.atoms(seq)
    assert symbols == ['C', 'O', 'Cl']
    assert coords == [(0.0, 1.0), (1.0, 0.0), (21 / 63, 42 / 63)]
    # the step whose input was each atom's y token
    assert indices == [3, 8, 13]


def test_bracket_atoms_and_abbreviations_are_one_atom(vocab):
    seq = [8, 13, 15, 10, 9, x(vocab, 1), y(vocab, 2), 8, 12, 16, 17, 9, x(vocab, 3), y(vocab, 4), 2]
    symbols, _, _ = vocab.atoms(seq)
    assert symbols == ['[NH+]', '[OMe]']


def test_an_atom_without_coordinates_is_dropped(vocab):
    symbols, _, _ = vocab.atoms([11, 12, x(vocab, 1), y(vocab, 1), 2])
    assert symbols == ['O']


def test_after_an_x_bin_only_a_y_bin_may_follow(vocab):
    mask = vocab.mask_after(x(vocab, 5))
    assert mask[:vocab.offset + BINS].all() and not mask[vocab.offset + BINS:].any()
    mask = vocab.mask_after(y(vocab, 5))
    assert not mask[:vocab.offset].any() and mask[vocab.offset:].all()
    assert vocab.mask_after(11) is None


def test_symmetrising_swaps_the_wedge_classes():
    probs = np.zeros((2, 2, 7))
    probs[0, 1, 5] = 1.0          # (0, 1) says class 5…
    probs[1, 0, 6] = 1.0          # …and (1, 0) agrees, from the other side
    out = symmetrise(probs)
    assert out[0, 1, 5] == 1.0 and out[1, 0, 6] == 1.0


def chain(classes_upper, n):
    classes = np.zeros((n, n), dtype=int)
    for (i, j), kind in classes_upper.items():
        classes[i, j] = kind
        classes[j, i] = {5: 6, 6: 5}.get(kind, kind)
    return classes


def test_plain_bonds():
    bonds = bonds_from(chain({(0, 1): 1, (1, 2): 2}, 3))
    assert [(b.begin, b.end, b.kind) for b in bonds] == [(0, 1, SINGLE), (1, 2, DOUBLE)]


def test_the_wedge_starts_at_the_atom_with_more_bonds():
    # 1 is a centre bonded to 0, 2 and 3; the wedge class sits on (0, 1) seen from 0.
    classes = chain({(0, 1): 6, (1, 2): 1, (1, 3): 1}, 4)
    wedge = [b for b in bonds_from(classes) if b.kind in (WEDGE, HASH)][0]
    assert (wedge.begin, wedge.end) == (1, 0)
    assert wedge.kind == WEDGE        # class 6 from 0 is class 5 from 1: a solid wedge from 1


def test_a_tie_goes_to_the_atom_whose_neighbours_continue():
    # 0 (ring-like: neighbours 4, 5 continue) and 1 (isopropyl CH: 2 and 3 are chain ends)
    classes = chain({(0, 1): 5, (1, 2): 1, (1, 3): 1, (0, 4): 1, (0, 5): 1, (4, 6): 1, (5, 7): 1}, 8)
    wedge = [b for b in bonds_from(classes) if b.kind in (WEDGE, HASH)][0]
    assert (wedge.begin, wedge.end, wedge.kind) == (0, 1, WEDGE)


def test_the_model_s_own_stereocentre_mark_wins_over_bond_counts():
    # 0 is a plain carbon with three bonds; 1 is spelled [C@@H] (also three): the wedge between
    # them starts at 1, as upstream's stereocentre search would decide.
    classes = chain({(0, 1): 5, (0, 2): 1, (0, 3): 1, (1, 4): 1, (1, 5): 1, (2, 6): 1, (3, 7): 1}, 8)
    symbols = ['C', '[C@@H]', 'C', 'C', 'C', 'O', 'C', 'C']
    wedge = [b for b in bonds_from(classes, symbols) if b.kind in (WEDGE, HASH)][0]
    assert (wedge.begin, wedge.end, wedge.kind) == (1, 0, HASH)


def test_the_published_vocabulary_matches_molscribes_layout():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tools', 'out', 'vocab.json')
    if not os.path.exists(path):
        pytest.skip('no exported model here')
    with open(path, encoding='utf-8') as f:
        stoi = json.load(f)
    vocab = Vocabulary(stoi, BINS, SPECIAL)
    assert vocab.size == 229
