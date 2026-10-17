#!/usr/bin/env python3
"""Checks the plugin's ONNX recognition against upstream MolScribe in torch. Maintainers only.

    python parity.py --checkpoint swin_base_char_aux_1m680k.pth --molscribe-src MolScribe/ \
        --model out/ [--images dir/]

For each picture (RDKit renders of SAMPLES, plus any PNG/JPEG in --images) it compares:

  preprocessing  the plugin's numpy/Pillow pipeline against upstream's OpenCV one
                 (both trimming exact white, as upstream does): the largest pixel difference
  tokens         upstream's step-by-step greedy decoding against the plugin's, given the same
                 input tensor: identical sequences, or where they first differ
  bonds          the bond classes from both bond heads
  result         the plugin's molfile read back by RDKit, against the SMILES drawn

and prints the time the plugin took. Exit status 1 if any token sequence differs.
"""

from __future__ import annotations

import argparse
import glob
import io
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import molscribe_loader  # noqa: E402

SAMPLES = {
    'ethanol': 'CCO',
    'aspirin': 'CC(=O)Oc1ccccc1C(=O)O',
    'caffeine': 'Cn1cnc2c1c(=O)n(C)c(=O)n2C',
    'ibuprofen': 'CC(C)Cc1ccc(cc1)C(C)C(=O)O',
    'paracetamol': 'CC(=O)Nc1ccc(O)cc1',
    'menthol': 'CC(C)[C@@H]1CC[C@@H](C)C[C@H]1O',
    'alanine': 'C[C@H](N)C(=O)O',
    'nicotine': 'CN1CCC[C@H]1c1cccnc1',
    'chlorobenzene': 'Clc1ccccc1',
    'zwitterion': 'C[N+](C)(C)CC(=O)[O-]',
    'anisole-ester': 'COc1ccc(cc1)C(=O)OCC',
    'morphine': 'CN1CC[C@]23c4c5ccc(O)c4O[C@H]2[C@@H](O)C=C[C@H]3[C@H]1C5',
}


def render(smiles: str, size: int = 500) -> bytes:
    from rdkit import Chem
    from rdkit.Chem.Draw import rdMolDraw2D
    mol = Chem.MolFromSmiles(smiles)
    drawer = rdMolDraw2D.MolDraw2DCairo(size, size)
    drawer.drawOptions().bondLineWidth = 2
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


def upstream_tensor(data: bytes, size: int) -> np.ndarray:
    """MolScribe's inference transforms with OpenCV, as albumentations applies them."""
    import cv2
    from p2s import preprocess
    pixels = preprocess.load_rgb(data)
    ink = (pixels != 255).any(axis=2)
    rows, cols = np.flatnonzero(ink.any(axis=1)), np.flatnonzero(ink.any(axis=0))
    if rows.size:
        pixels = pixels[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    pixels = cv2.resize(pixels, (size, size), interpolation=cv2.INTER_LINEAR)
    grey = cv2.cvtColor(cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)
    mean, std = np.array(preprocess.MEAN), np.array(preprocess.STD)
    return ((grey / 255.0 - mean) / std).transpose(2, 0, 1)[None].astype(np.float32)


def torch_predict(encoder, decoder, tensor):
    import torch
    from molscribe.utils import FORMAT_INFO  # noqa: F401  (decode reads it)
    with torch.no_grad():
        features, hiddens = encoder(torch.from_numpy(tensor))
        chartok = decoder.decoder['chartok_coords']
        outputs, _, _, hidden = chartok.decode(features, beam_size=1, n_best=1, max_length=480)
        sequence = outputs[0][0].tolist()
        prediction = decoder.decode(features, hiddens)[0]
    return sequence, prediction


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--molscribe-src', required=True)
    parser.add_argument('--model', required=True, help='a folder written by export_onnx.py')
    parser.add_argument('--images', help='a folder of extra PNG/JPEG pictures')
    args = parser.parse_args()

    from rdkit import Chem
    from p2s import molfile, preprocess
    from p2s.recognizer import OnnxRecognizer, symmetrise

    encoder, decoder, _, _ = molscribe_loader.load(args.checkpoint, args.molscribe_src)
    recognizer = OnnxRecognizer(args.model)
    size = recognizer.manifest['inputSize']

    pictures = [(name, render(smiles), smiles) for name, smiles in SAMPLES.items()]
    if args.images:
        for path in sorted(glob.glob(os.path.join(args.images, '*'))):
            if path.lower().endswith(('.png', '.jpg', '.jpeg')):
                with open(path, 'rb') as f:
                    pictures.append((os.path.basename(path), f.read(), None))

    failures = 0
    times = []
    print(f"{'picture':22} {'prep Δ':>7} {'tokens':>8} {'bonds':>6} {'conf':>5} {'time':>6}  result")
    for name, data, expected in pictures:
        mine, _ = preprocess.prepare(data, None, size, white=255)
        reference = upstream_tensor(data, size)
        prep_delta = float(np.abs(mine - reference).max())

        torch_sequence, torch_prediction = torch_predict(encoder, decoder, mine)
        (memory,) = recognizer.encoder.run(None, {'image': mine})
        sequence, _, hidden = recognizer.decode(memory)
        same = sequence == torch_sequence
        if not same:
            failures += 1
            first = next((i for i, (a, b) in enumerate(zip(sequence, torch_sequence)) if a != b),
                         min(len(sequence), len(torch_sequence)))
            token_text = f'differ@{first}'
        else:
            token_text = 'same'

        symbols, _, indices = recognizer.vocab.atoms(sequence)
        bond_text = '-'
        if symbols and same:
            (probs,) = recognizer.edges.run(None, {'atoms': hidden[indices][None].astype(np.float32)})
            classes = symmetrise(probs[0].astype(np.float64)).argmax(axis=2)
            bond_text = 'same' if classes.tolist() == torch_prediction['edges'] else 'differ'
            if bond_text == 'differ':
                failures += 1

        started = time.perf_counter()
        structure = recognizer.recognise(data)
        elapsed = time.perf_counter() - started
        times.append(elapsed)

        result = '(nothing)'
        if not structure.empty:
            mol = Chem.MolFromMolBlock(molfile.write(structure))
            if mol is not None:
                got = Chem.MolToSmiles(mol)
                if expected:
                    want = Chem.MolToSmiles(Chem.MolFromSmiles(expected))
                    result = 'match' if got == want else f'{got}  (drawn {want})'
                else:
                    result = got
            else:
                result = '(RDKit could not read it)'
        print(f'{name:22} {prep_delta:7.3f} {token_text:>8} {bond_text:>6} {structure.confidence:5.2f} '
              f'{elapsed:5.2f}s  {result}')

    print(f'\nplugin time per picture: median {sorted(times)[len(times) // 2]:.2f}s, max {max(times):.2f}s')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
