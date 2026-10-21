# NMR Prediction

A Molion plugin that ships with Molion: predicted ¹H and ¹³C spectra for the selection, in a
card at the bottom right of the canvas. Hovering a peak lights up its atoms; hovering an atom
lights up its peak. Copy gives an SI-style line marked "predicted".

Turn it on in **Settings → Plugins → Included with Molion**. Its card then follows the
selection; Space → **Hide NMR Prediction** or ✕ puts it away, **Show NMR Prediction** brings it
back.

## How it predicts

- **Shifts:** HOSE codes. Each atom's surroundings, one to five bonds out, are looked up in a
  table of measured shifts from nmrshiftdb2, using the deepest match there is (data/SOURCE.md
  has the accuracy). A shift matched only on its nearest neighbours is marked "rough".
- **Multiplets (¹H):** first order, with typical coupling constants (`nmr/multiplets.py`), at
  400 MHz (101 MHz for ¹³C). OH, NH and SH are broad singlets.
- **One peak per set of equivalent atoms**, from Molion's symmetry classes. With part of a
  molecule selected, only its peaks show, predicted from the whole molecule.

Labels (OMe, Ph, Boc) are predicted as the groups they stand for, and light up the label.
Groups without a structure (R, X) are not predicted.

## Calculated shifts, with ORCA

Where ORCA is set up in Molion (Settings → Calculations), the card offers **Calculate NMR with
ORCA** (also in the Space palette). Molion runs GIAO shieldings at TPSS/pcSseg-1 on the
optimised geometry, against TMS at the same level, and shows its progress in the card. Once
done, the peaks move to the calculated shifts (each class's mean, multiplets as before), the
card says "Calculated" and names the method, and Copy says "calculated". A shift the
calculation lacks stays predicted and says so. Without ORCA the card is exactly as above.

## How it talks to Molion

It declares one card (`contributes.cards` in plugin.json, `input: "structure"`). Molion sends a
`card` request with the selection's structures, already perceived
(aromaticity, hydrogens, symmetry, double-bond geometry), and draws the spectrum blocks this
answers with. The plugin never changes the drawing and needs no network.

- `scene:read`: the structures, and for its action the selection's (`get-structure`).
- `orca`: Molion's `calculate` (`nmr/calculated.py`). The card only asks what there is
  (`start: false`); the action **Calculate NMR with ORCA** starts the job. Molion runs ORCA, so
  the plugin never sees where it is installed.

Turn it on in Molion's Settings → Plugins.

Standard-library Python 3.9+ only. Packaged Molion builds run a frozen copy, so users need no
Python.

## Tests

```bash
python3 -m pytest -q nmr-prediction
```

They run on the standard library and pytest: the molecules in `tests/fixtures/structures.json`
are what Molion would send (regenerate with `tools/fixtures.py`, which needs RDKit).

## Licences

The code is MIT (LICENSE). The shift table is derived from nmrshiftdb2 and stays under the
nmrshiftdb2 Database License (NOTICE).
