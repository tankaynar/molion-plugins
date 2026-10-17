# Exporting the recognition model

For maintainers. The plugin runs MolScribe from three ONNX files on onnxruntime; these tools
make them from MolScribe's own checkpoint and check them against upstream torch. Nothing here
ships with Molion.

## Environment

A scratch venv of its own, not the plugin's `.venv` (Python 3.12):

```bash
python3.12 -m venv /tmp/p2s-venv
/tmp/p2s-venv/bin/pip install torch "numpy<2" timm==0.4.12 SmilesPE==0.0.3 onnx onnxruntime \
    onnxscript Pillow opencv-python-headless rdkit configargparse pytest
/tmp/p2s-venv/bin/pip install --no-deps OpenNMT-py==2.2.0     # its __init__ needs torchtext; skipped
git clone --depth 1 https://github.com/thomas0809/MolScribe.git /tmp/MolScribe
curl -L -o /tmp/swin_base_char_aux_1m680k.pth \
    https://huggingface.co/yujieq/MolScribe/resolve/main/swin_base_char_aux_1m680k.pth   # 1.1 GB, MIT
```

## Export

```bash
/tmp/p2s-venv/bin/python export_onnx.py --checkpoint /tmp/swin_base_char_aux_1m680k.pth \
    --molscribe-src /tmp/MolScribe --out out --int8
```

`out/` is gitignored. Its five files go, as they are, to the GitHub release `p2s-model-v1` of tankaynar/molion-plugins;
`p2s/model_store.py` pins each one's size and SHA-256, so a new export means new pins (and a
new release tag and folder version, so an old download is never mixed with new files).

| File | int8 | fp32 |
|---|---|---|
| encoder.onnx | 123.3 MB | 382.2 MB |
| decoder.onnx | 11.9 MB | 31.0 MB |
| edges.onnx | 0.5 MB | 0.5 MB |
| vocab.json, manifest.json | 2 KB | 2 KB |

## The interface `p2s/recognizer.py` follows

| File | Inputs | Outputs |
|---|---|---|
| encoder.onnx | `image` float32 [1, 3, 384, 384] | `memory` float32 [1, 144, 256] |
| decoder.onnx | `tokens` int64 [1, T], `memory` | `log_probs` float32 [1, 229] (next token), `hidden` float32 [1, T, 256] |
| edges.onnx | `atoms` float32 [1, K, 256] | `probs` float32 [1, K, K, 7] |

Tokens: ids 0–4 are `<pad> <sos> <eos> <unk> <mask>`, then MolScribe's characters up to
`symbols` (101), then 64 x bins and 64 y bins. Each atom is its characters followed by its x
and y bin; the bond head reads the hidden state of the step whose input was the atom's y bin.
Bond classes: none, single, double, triple, aromatic, and two wedge classes that say which atom
of the pair is in front (`symmetrise` swaps them for the reversed pair).

The decoder takes the whole sequence each call (no cache): greedy decoding is one call per
token, about 0.2–0.5 s per picture on an M-series CPU, so a cache was not worth its export.

## Parity

```bash
/tmp/p2s-venv/bin/python parity.py --checkpoint /tmp/swin_base_char_aux_1m680k.pth \
    --molscribe-src /tmp/MolScribe --model out [--images more-pictures/]
```

Results on the twelve RDKit renders in `SAMPLES` (October 2026, Apple M-series CPU):

- **fp32**: token sequences and bond classes identical to upstream torch on all twelve; all
  twelve read back as the SMILES drawn (stereo included); median 0.45 s, morphine 0.84 s.
- **int8** (shipped): all twelve read back as the SMILES drawn. Tokens differ from torch on
  six: coordinate bins one step apart, and in two (caffeine, the zwitterion) the molecule
  walked in another order. Median 0.24 s, morphine 0.49 s.
- Preprocessing (numpy and Pillow against upstream's OpenCV): at most 0.018 after
  normalisation, about one grey level.
- Confidence (token score × geometric mean of bond scores): 0.85–0.91 on the twelve; 0.40–0.67
  on a circle, a line of text and noise.

## Accuracy on real pictures

```bash
/tmp/p2s-venv/bin/python evaluate.py --bench real/ --molscribe-src /tmp/MolScribe \
    --model int8=out --model fp32=out-fp32 --sets acs --sample 0 --variants plain,jpeg40,half \
    --results results.jsonl
```

`real/` is MolScribe's `real.zip` (huggingface.co/yujieq/MolScribe): ACS (331 pictures cut from
journal articles), CLEF, UOB and USPTO (patents, catalogues) and Staker (low resolution). Each
picture goes through the plugin's own path to a molfile, read back with RDKit and scored as
MolScribe scores (canonical SMILES ignoring cis/trans; "graph" ignores stereo too). "Upstream" is
the same model output through MolScribe's own RDKit post-processing, for reference. Two scoring
fixes: upstream's abbreviation expansion fails on current RDKit (bond orders were carried in
radical counts), so the evaluator expands with the orders in a dict; and the ACS gold writes aryl
as `[Ar]`, which RDKit reads as argon, so `[Ar]` scores as any substituent on both sides.

October 2026, int8, plain pictures (ACS all 331, the others 150 each, seed 0):

| Set | Exact | Graph | Stereo (with stereocentres) | Upstream exact | Upstream stereo | Time |
|---|---|---|---|---|---|---|
| ACS | 71.6% | 77.0% | 35.9% | 72.5% | 40.6% | 0.28 s |
| CLEF | 92.7% | 93.3% | 93.2% | 92.7% | 93.2% | 0.63 s |
| UOB | 87.3% | 87.3% | – | 87.3% | – | 0.31 s |
| USPTO | 95.3% | 96.7% | 93.3% | 94.0% | 86.7% | 0.70 s |
| Staker | 89.3% | 97.3% | 45.5% | 89.3% | 45.5% | 0.60 s |

What the numbers settled:

- **int8 stays.** On ACS fp32 read 70.7% exact against int8's 69.8% (75.5% and 75.2% graph),
  on USPTO 93.3% against 94.0%, the rest equal; int8 is about twice as fast and a third the size.
- **The trim threshold stays at 245.** On ACS damaged to JPEG quality 40 and to half size,
  thresholds 230, 245 and 255 came within 1.5 points of each other (one picture is 0.3 points),
  and damage itself cost nothing measurable (ACS graph 75–79% throughout).
- **Wedges follow the model's own stereocentre marks.** Taking the atom with more bonds as the
  narrow end lost stereo on CLEF (84.1% against upstream's 93.2%); the model spells
  stereocentres `[C@@H]`, and preferring them brought CLEF level and USPTO above upstream.
  ACS keeps a gap of four molecules (35.9% against 40.6%).
- **Labels that spell elements.** `[Ts]` had become tennessine and `[2*]` a literal label;
  checking MolScribe's abbreviation and R-group names first, and `[n*]` as `Rn`, brought CLEF
  from 86.7% to 92.7% exact.
- **Confidence thresholds.** Over 5,772 readings: below 0.6, 1 of 35 was right, so nothing is
  placed. Warning below 0.85 instead of 0.8 flags 10% of results instead of 3.6%, with the same
  4 in 10 of them wrong, and catches 24% of all wrong results instead of 8%.

Not measured: photographs of pages, hand drawing, and pictures holding more than one molecule
(MolScribe reads one; the user crops first). Molion expands labels by its own rules, not
MolScribe's, so a label one knows and the other does not can score differently in the app.
