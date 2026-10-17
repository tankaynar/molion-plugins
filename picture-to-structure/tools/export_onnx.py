#!/usr/bin/env python3
"""Exports MolScribe to the three ONNX files the plugin runs. Maintainers only: needs torch.

    python export_onnx.py --checkpoint swin_base_char_aux_1m680k.pth \
        --molscribe-src MolScribe/ --out out/ [--int8]

The checkpoint is MolScribe's own (huggingface.co/yujieq/MolScribe, MIT), and --molscribe-src
a clone of github.com/thomas0809/MolScribe. See README.md here for the environment.

What comes out, and the interface p2s/recognizer.py follows:

    encoder.onnx  image  float32 [1, 3, 384, 384]  →  memory  float32 [1, 144, 256]
                  (the Swin encoder and the decoder's projection of its features)
    decoder.onnx  tokens int64 [1, T], memory  →  log_probs float32 [1, V] (the next token),
                                                  hidden    float32 [1, T, 256]
                  (the whole sequence each call; no cache, so greedy decoding is T calls)
    edges.onnx    atoms  float32 [1, K, 256]   →  probs     float32 [1, K, K, 7]
                  (the bond head over the hidden states at each atom's y token)
    vocab.json    MolScribe's character vocabulary; coordinate bins follow it
    manifest.json the files' sizes and SHA-256, the vocabulary layout, and the tensor names

The decoder adds positional encodings for positions 0…T-1 itself. Upstream adds them
batch-first, which during its step-by-step inference amounts to exactly this; a plain
full-sequence call of the upstream module would not, so it is not exported as is.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import molscribe_loader  # noqa: E402

OPSET = 17


def _onnx_friendly_masks() -> None:
    """Upstream builds the causal mask by adding a uint8 triangle to a bool mask; ONNX has no
    boolean Add and onnxruntime no uint8 Trilu. The same mask, from a float triangle and an Or."""
    import torch
    from molscribe.transformer.decoder import TransformerDecoderLayerBase

    def compute(self, tgt_pad_mask, future):
        if future:
            return tgt_pad_mask
        length = tgt_pad_mask.size(-1)
        ahead = torch.triu(torch.ones((length, length), dtype=torch.float32), diagonal=1) > 0
        return torch.logical_or(tgt_pad_mask, ahead.unsqueeze(0))

    TransformerDecoderLayerBase._compute_dec_mask = compute


def build_modules(encoder, decoder):
    import torch
    import torch.nn as nn

    chartok = decoder.decoder['chartok_coords']
    edges = decoder.decoder['edges']

    class EncoderPart(nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = encoder
            self.chartok = chartok

        def forward(self, image):
            features, _ = self.encoder(image)
            return self.chartok.enc_transform(features)

    class DecoderPart(nn.Module):
        def __init__(self):
            super().__init__()
            self.chartok = chartok
            self.lut = chartok.embeddings.word_lut
            self.register_buffer('pe', chartok.embeddings.make_embedding.pe.pe[:, 0, :].clone())
            self.scale = math.sqrt(self.lut.embedding_dim)

        def forward(self, tokens, memory):
            length = tokens.shape[1]
            emb = self.lut(tokens) * self.scale + self.pe[:length].unsqueeze(0)
            pad = torch.zeros((1, 1, length), dtype=torch.bool)
            out, _, _ = self.chartok.decoder(tgt_emb=emb, memory_bank=memory, tgt_pad_mask=pad, step=None)
            logits = self.chartok.output_layer(out[:, -1])
            return torch.log_softmax(logits, dim=-1), out

    class EdgePart(nn.Module):
        def __init__(self):
            super().__init__()
            self.edges = edges

        def forward(self, atoms):
            # Every row is an atom already, so the indices are simply 0…K-1.
            logits = self.edges(atoms, torch.arange(atoms.shape[1]).unsqueeze(0))['edges']
            return torch.softmax(logits.permute(0, 2, 3, 1), dim=-1)

    return EncoderPart().eval(), DecoderPart().eval(), EdgePart().eval()


def export(args) -> None:
    import torch

    encoder, decoder, tokenizer, model_args = molscribe_loader.load(args.checkpoint, args.molscribe_src)
    _onnx_friendly_masks()
    encoder_part, decoder_part, edge_part = build_modules(encoder, decoder)
    os.makedirs(args.out, exist_ok=True)

    size = model_args.input_size
    image = torch.zeros((1, 3, size, size))
    with torch.no_grad():
        memory = encoder_part(image)
        tokens = torch.tensor([[1, 57, 101 + 10, 101 + 64 + 20]], dtype=torch.long)
        _, hidden = decoder_part(tokens, memory)

        def save(module, inputs, path, input_names, output_names, dynamic_axes):
            torch.onnx.export(module, inputs, path, input_names=input_names, output_names=output_names,
                              dynamic_axes=dynamic_axes, opset_version=OPSET, do_constant_folding=True,
                              dynamo=False)

        save(encoder_part, (image,), os.path.join(args.out, 'encoder.onnx'),
             ['image'], ['memory'], None)
        save(decoder_part, (tokens, memory), os.path.join(args.out, 'decoder.onnx'),
             ['tokens', 'memory'], ['log_probs', 'hidden'],
             {'tokens': {1: 'T'}, 'hidden': {1: 'T'}})
        save(edge_part, (hidden[:, 1:3],), os.path.join(args.out, 'edges.onnx'),
             ['atoms'], ['probs'], {'atoms': {1: 'K'}, 'probs': {1: 'K', 2: 'K'}})

    if args.int8:
        from onnxruntime.quantization import QuantType, quantize_dynamic
        for name in ('encoder', 'decoder'):
            plain = os.path.join(args.out, f'{name}.onnx')
            quantize_dynamic(plain, plain + '.int8', weight_type=QuantType.QInt8)
            os.replace(plain + '.int8', plain)

    vocab = dict(tokenizer.stoi)
    with open(os.path.join(args.out, 'vocab.json'), 'w', encoding='utf-8') as f:
        json.dump(vocab, f, ensure_ascii=False, sort_keys=True)
        f.write('\n')

    files = []
    for name in ('encoder.onnx', 'decoder.onnx', 'edges.onnx', 'vocab.json'):
        path = os.path.join(args.out, name)
        digest = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                digest.update(chunk)
        files.append({'name': name, 'size': os.path.getsize(path), 'sha256': digest.hexdigest()})

    manifest = {
        'model': 'MolScribe swin_base_char_aux_1m680k',
        'license': 'MIT',
        'int8': bool(args.int8),
        'inputSize': size,
        'symbols': tokenizer.offset,
        'coordBins': model_args.coord_bins,
        'maxLength': 480,
        'special': {'pad': 0, 'sos': 1, 'eos': 2, 'unk': 3, 'mask': 4},
        'mean': [0.485, 0.456, 0.406],
        'std': [0.229, 0.224, 0.225],
        'bondClasses': ['none', 'single', 'double', 'triple', 'aromatic', 'wedge', 'hash'],
        'tensors': {
            'encoder': {'inputs': ['image'], 'outputs': ['memory']},
            'decoder': {'inputs': ['tokens', 'memory'], 'outputs': ['log_probs', 'hidden']},
            'edges': {'inputs': ['atoms'], 'outputs': ['probs']},
        },
        'files': files,
    }
    with open(os.path.join(args.out, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
        f.write('\n')

    for entry in files:
        print(f"{entry['name']:14} {entry['size'] / 1e6:8.1f} MB  {entry['sha256']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--molscribe-src', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--int8', action='store_true', help='dynamic int8 quantisation of encoder and decoder')
    args = parser.parse_args()
    export(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
