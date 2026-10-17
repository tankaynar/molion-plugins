# Where shifts.bin.gz comes from

| | |
|---|---|
| Source | nmrshiftdb2, `nmrshiftdb2withsignals.sd`, https://sourceforge.net/projects/nmrshiftdb2/files/data/ |
| Source date | 2026-03-15 (the file's date on SourceForge) |
| Source SHA-256 | `0e86688360e23c88ccf0eb82a1251315fa57ec6f5b376dc8886f3311793a0afe` |
| Licence | nmrshiftdb2 Database License (see ../NOTICE) |
| Built with | `tools/build_table.py`, RDKit 2025.9.2 |
| Records read | 57,363 |
| Environments | 532,690 for ¹³C, 179,177 for ¹H (HOSE codes of 1–5 spheres) |

Only measured spectra are used: spectra a record lists as predicted (ACD/Labs, CSEARCH,
nmrshiftdb2's own HOSE predictor) or calculated (Hartree–Fock) are skipped. ¹H shifts are
averaged per atom and spectrum (a CH₂'s two hydrogens are one value). Each code keeps the
median of its shifts, after dropping values more than three robust deviations (1.4826 × MAD,
at least 1 ppm for ¹³C and 0.05 ppm for ¹H) from it, the spread of the rest and their number.

## Accuracy

With every 20th record (by nmrshiftdb2 ID) left out of the table and predicted from it
(`--holdout 20`), mean absolute error of the deepest match:

| | all atoms | 5 spheres | 4 | 3 | 2 | 1 |
|---|---|---|---|---|---|---|
| ¹³C (18,480 atoms) | 2.38 ppm | 0.90 | 1.34 | 2.43 | 4.99 | 10.7 |
| ¹H (6,701 atoms) | 0.25 ppm | 0.12 | 0.21 | 0.30 | 0.53 | 0.74 |

nmrshiftdb2 holds some compounds more than once, so a held-out record may have a twin in the
table; the deep-match figures are therefore somewhat optimistic. The card calls a shift
matched on two spheres or fewer "rough".

## Rebuilding

```bash
curl -L -o nmrshiftdb2withsignals.sd \
  https://sourceforge.net/projects/nmrshiftdb2/files/data/nmrshiftdb2withsignals.sd/download
../../src/chem_server/.venv/bin/python ../tools/build_table.py --sd nmrshiftdb2withsignals.sd --holdout 20  # to measure
../../src/chem_server/.venv/bin/python ../tools/build_table.py --sd nmrshiftdb2withsignals.sd               # to ship
```

The output is deterministic for a given source file, so an unchanged source gives an
unchanged file. Update this page with each rebuild.
