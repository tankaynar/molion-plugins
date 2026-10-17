"""MolScribe on onnxruntime: a picture in, atoms where they were drawn and bonds out.

The decoding is MolScribe's greedy search, rewritten for numpy: the decoder sees the whole
sequence so far at each step (tools/export_onnx.py exports it that way), the same output
constraint applies (an x bin must be followed by its y bin, and a y bin by a symbol), and the
bond head reads the hidden state at each atom's y token. tools/parity.py checks the result
against upstream torch.

MolScribe's wedge classes say which atom of a pair is in front but not which end is narrow;
upstream settles that with RDKit's stereocentre search. The model itself marks stereocentres,
though: it spells them as SMILES does ("[C@@H]", "[C@]"). So the narrow end is the atom so
marked, else the one with more bonds, else the one with more neighbours that are not chain
ends; Molion perceives the stereo from the drawn wedge as from any other.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass

import numpy as np

from . import preprocess
from .structure import AROMATIC, DOUBLE, HASH, SINGLE, TRIPLE, WEDGE, Atom, Bond, Structure

_ORDER = {1: SINGLE, 2: DOUBLE, 3: TRIPLE, 4: AROMATIC}


class Vocabulary:
    """MolScribe's CharTokenizer: symbol ids, then x bins, then y bins."""

    def __init__(self, stoi: dict[str, int], bins: int, special: dict[str, int]) -> None:
        self.itos = {i: s for s, i in stoi.items()}
        self.offset = len(stoi)
        self.bins = bins
        self.size = self.offset + 2 * bins
        self.pad, self.sos, self.eos, self.unk = special['pad'], special['sos'], special['eos'], special['unk']
        self.first_symbol = 5

    def is_x(self, token: int) -> bool:
        return self.offset <= token < self.offset + self.bins

    def is_y(self, token: int) -> bool:
        return self.offset + self.bins <= token

    def is_symbol(self, token: int) -> bool:
        return self.first_symbol <= token < self.offset or token == self.unk

    def is_atom(self, token: int) -> bool:
        if not self.is_symbol(token):
            return False
        text = self.itos[token]
        return text.isalpha() or text.startswith('[') or text == '*' or text == '<unk>'

    def x_of(self, token: int) -> float:
        return (token - self.offset) / (self.bins - 1)

    def y_of(self, token: int) -> float:
        return (token - self.offset - self.bins) / (self.bins - 1)

    def mask_after(self, token: int) -> np.ndarray | None:
        """Tokens that may not follow `token`, or None for no constraint."""
        if self.is_x(token):
            mask = np.ones(self.size, dtype=bool)
            mask[self.offset + self.bins:] = False
            return mask
        if self.is_y(token):
            mask = np.zeros(self.size, dtype=bool)
            mask[self.offset:] = True
            return mask
        return None

    def atoms(self, sequence: list[int]) -> tuple[list[str], list[tuple[float, float]], list[int]]:
        """Upstream's sequence_to_smiles: each atom's text, its 0–1 position, and the index of
        the hidden state that describes it (the step whose input was its y token)."""
        symbols, coords, indices = [], [], []
        i = 0
        while i < len(sequence):
            token = sequence[i]
            if token in (self.eos, self.pad):
                break
            if self.is_x(token) or self.is_y(token) or not self.is_atom(token):
                i += 1
                continue
            if self.itos[token] == '[':
                j = i + 1
                while j < len(sequence):
                    if not self.is_symbol(sequence[j]):
                        break
                    if self.itos[sequence[j]] == ']':
                        j += 1
                        break
                    j += 1
            elif (i + 1 < len(sequence) and self.is_symbol(sequence[i + 1])
                  and (self.itos[token], self.itos[sequence[i + 1]]) in (('C', 'l'), ('B', 'r'))):
                j = i + 2
            else:
                j = i + 1
            text = ''.join(self.itos[sequence[k]] for k in range(i, j))
            if j + 2 < len(sequence) and self.is_x(sequence[j]) and self.is_y(sequence[j + 1]):
                coords.append((self.x_of(sequence[j]), self.y_of(sequence[j + 1])))
                symbols.append(text)
                indices.append(j + 2)
                i = j + 2
            else:
                i = j
        return symbols, coords, indices


def symmetrise(probs: np.ndarray) -> np.ndarray:
    """Upstream's get_edge_prediction: average (i, j) with (j, i), the wedge classes swapped."""
    swapped = probs.transpose(1, 0, 2)[:, :, [0, 1, 2, 3, 4, 6, 5]]
    return (probs + swapped) / 2


def _stereo_rank(classes: np.ndarray, degree: np.ndarray, atom: int,
                 symbols: list[str] | None) -> tuple[int, int, int]:
    """How likely `atom` is the narrow end of a wedge: marked a stereocentre by the model
    first, then more bonds, then more neighbours that are not chain ends (a ring carbon
    outranks an isopropyl CH, whose methyls end there)."""
    marked = int(symbols is not None and '@' in symbols[atom])
    neighbours = [n for n in np.flatnonzero(classes[atom]) if n != atom]
    return marked, int(degree[atom]), sum(1 for n in neighbours if degree[n] > 1)


def bonds_from(classes: np.ndarray, symbols: list[str] | None = None) -> list[Bond]:
    count = classes.shape[0]
    degree = (classes != 0).sum(axis=1) - (np.diag(classes) != 0)
    bonds = []
    for i in range(count):
        for j in range(i + 1, count):
            kind = int(classes[i, j])
            if kind == 0:
                continue
            if kind in _ORDER:
                bonds.append(Bond(i, j, _ORDER[kind]))
                continue
            rank_i, rank_j = _stereo_rank(classes, degree, i, symbols), _stereo_rank(classes, degree, j, symbols)
            narrow, wide = (j, i) if rank_j > rank_i else (i, j)
            seen = int(classes[narrow, wide])
            bonds.append(Bond(narrow, wide, WEDGE if seen == 5 else HASH))
    return bonds


class OnnxRecognizer:
    def __init__(self, folder: str) -> None:
        import onnxruntime

        with open(os.path.join(folder, 'manifest.json'), encoding='utf-8') as f:
            self.manifest = json.load(f)
        with open(os.path.join(folder, 'vocab.json'), encoding='utf-8') as f:
            stoi = json.load(f)
        self.vocab = Vocabulary(stoi, self.manifest['coordBins'], self.manifest['special'])
        options = onnxruntime.SessionOptions()
        options.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        providers = ['CPUExecutionProvider']

        def session(name):
            return onnxruntime.InferenceSession(os.path.join(folder, name), options, providers=providers)

        self.encoder, self.decoder, self.edges = session('encoder.onnx'), session('decoder.onnx'), session('edges.onnx')
        self.white = preprocess.WHITE

    def decode(self, memory: np.ndarray) -> tuple[list[int], list[float], np.ndarray]:
        """Greedy decoding: the predicted tokens (without <sos>), their log probabilities, and
        the decoder's hidden state for every step."""
        vocab = self.vocab
        tokens = [vocab.sos]
        scores: list[float] = []
        hidden = np.zeros((0, 0), dtype=np.float32)
        for step in range(self.manifest['maxLength']):
            log_probs, hidden_all = self.decoder.run(
                None, {'tokens': np.array([tokens], dtype=np.int64), 'memory': memory})
            hidden = hidden_all[0]
            row = log_probs[0].astype(np.float64)
            mask = vocab.mask_after(tokens[-1])
            if mask is not None:
                row[mask] = -10000.0
            if len(tokens) <= 1:
                row[vocab.eos] = -1e20       # at least one token before the end
            choice = int(np.argmax(row))
            tokens.append(choice)
            scores.append(float(row[choice]))
            if choice == vocab.eos:
                break
        return tokens[1:], scores, hidden

    def read(self, data: bytes, crop: dict | None = None) -> 'Reading':
        """Everything recognition found, for tools that look behind the structure."""
        manifest = self.manifest
        image, box = preprocess.prepare(data, crop, manifest['inputSize'], white=self.white,
                                        mean=manifest['mean'], std=manifest['std'])
        (memory,) = self.encoder.run(None, {'image': image})
        sequence, scores, hidden = self.decode(memory)
        symbols, coords, indices = self.vocab.atoms(sequence)
        if not symbols:
            return Reading(Structure(), symbols, coords, np.zeros((0, 0), dtype=int), box)

        (probs,) = self.edges.run(None, {'atoms': hidden[indices][None].astype(np.float32)})
        probs = symmetrise(probs[0].astype(np.float64))
        classes = probs.argmax(axis=2)
        edge_scores = probs.max(axis=2)

        # Upstream multiplies the edge scores of every pair, which falls with size (a correct
        # morphine scored 0.52); a geometric mean over pairs does not. The token score is what
        # separates a structure (0.85–0.91 on clean drawings) from text or noise (0.4–0.67).
        token_score = math.exp(sum(scores) / len(scores))
        upper = np.triu_indices(len(symbols), 1)
        pairs = np.clip(edge_scores[upper], 1e-12, 1)
        edge_score = math.exp(float(np.log(pairs).mean())) if pairs.size else 1.0
        atoms = [Atom(symbol, *box.to_pixels(x, y)) for symbol, (x, y) in zip(symbols, coords)]
        structure = Structure(atoms, bonds_from(classes, symbols), confidence=token_score * edge_score)
        return Reading(structure, symbols, coords, classes, box)

    def recognise(self, data: bytes, crop: dict | None = None) -> Structure:
        return self.read(data, crop).structure


@dataclass(frozen=True)
class Reading:
    structure: Structure
    symbols: list[str]                     # as MolScribe spells them
    coords: list[tuple[float, float]]      # 0–1, within `box`
    classes: np.ndarray                    # bond class per atom pair, symmetrised
    box: preprocess.Box
