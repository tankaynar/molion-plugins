"""Loads upstream MolScribe (torch) for the export and parity tools. Maintainers only.

MolScribe's package __init__ pulls in its drawing interface (albumentations, matplotlib), and
OpenNMT-py's __init__ pulls in torchtext, which no longer installs on current Python. Neither
is needed to run the model, so both packages are registered here without running their
__init__ files, and only the modules the model uses are imported.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import types


def _register_package(name: str, path: str) -> None:
    if name in sys.modules:
        return
    package = types.ModuleType(name)
    package.__path__ = [path]
    sys.modules[name] = package


def _defaults() -> argparse.Namespace:
    # MolScribe's interface._get_args defaults; the checkpoint's own args override them.
    return argparse.Namespace(
        encoder='swin_base', decoder='transformer', trunc_encoder=False, no_pretrained=False,
        use_checkpoint=True, dropout=0.5, embed_dim=256, enc_pos_emb=False,
        dec_num_layers=6, dec_hidden_size=256, dec_attn_heads=8, dec_num_queries=128,
        hidden_dropout=0.1, attn_dropout=0.1, max_relative_positions=0,
        continuous_coords=False, compute_confidence=False,
        input_size=384, vocab_file=None, coord_bins=64, sep_xy=True)


def load(checkpoint: str, molscribe_src: str):
    """Returns (encoder, decoder, tokenizer, args) in eval mode on the CPU."""
    import torch

    _register_package('molscribe', os.path.join(molscribe_src, 'molscribe'))
    onmt = importlib.util.find_spec('onmt')
    if onmt is None:
        raise SystemExit('OpenNMT-py is missing: pip install --no-deps OpenNMT-py==2.2.0')
    _register_package('onmt', onmt.submodule_search_locations[0])

    from molscribe.model import Decoder, Encoder
    from molscribe.tokenizer import get_tokenizer

    states = torch.load(checkpoint, map_location='cpu', weights_only=False)
    args = _defaults()
    for key, value in states['args'].items():
        setattr(args, key, value)
    # Checkpointing is a training memory trick; it also gets in the way of tracing.
    args.use_checkpoint = False

    tokenizer = get_tokenizer(args)
    encoder = Encoder(args, pretrained=False)
    args.encoder_dim = encoder.n_features
    decoder = Decoder(args, tokenizer)

    def strip(state):
        return {k.replace('module.', ''): v for k, v in state.items()}

    for module, key in ((encoder, 'encoder'), (decoder, 'decoder')):
        missing, unexpected = module.load_state_dict(strip(states[key]), strict=False)
        missing = [k for k in missing if 'relative_position_index' not in k and 'attn_mask' not in k]
        if missing:
            raise SystemExit(f'{key}: weights missing from the checkpoint: {missing[:5]}')

    encoder.eval()
    decoder.eval()
    return encoder, decoder, tokenizer['chartok_coords'], args
