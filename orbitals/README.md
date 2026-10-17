# Orbitals

A Molion plugin that ships with Molion: atomic and hybrid orbitals (s, p, sp, sp², sp³ and the
five d orbitals), drawn as pictures that stay sharp at any zoom and export as vectors to SVG
and PDF.

Turn it on in **Settings → Plugins → Included with Molion**.

## Placing an orbital

The **ORBITALS** group in the tool panel has s, p, sp³ and d. Choose one, then:

- **click an atom** to put the orbital on it (a p orbital stands upright, the others point
  right), or click anywhere to put it there;
- **drag** from an atom to aim the orbital along the drag.

Every orbital is also a palette command: press Space and type "orbital" for **Place sp²
Orbital**, **Place dz² Orbital** and the rest. Like every placement tool, a tool returns to
Select afterwards unless Shift is held.

## Editing one

Double-click an orbital, or select it and choose **Edit Orbital…**. In the dialog:

- **Orbital**: which one it is.
- **Phase**: lobes **shaded** in two colours, **+ and −** written in outlined lobes, or the
  **outline** alone.
- **Positive** and **Negative**: the shaded lobes' colours.
- **Angle**: its axis, in degrees clockwise from pointing right; **Turn Left/Right 90°**.
- **Swap signs**: the positive and negative lobes change places.

Nothing on the canvas changes until **Done**, which is one undo step. On the canvas an
orbital moves, resizes and deletes like any picture. It turns only through the plugin, so its
signs stay upright. With an orbital selected, the palette also offers **Swap Signs** and
**Turn Orbital 90°**.

## Templates

Six drawings come with the plugin. They are in Insert Template's Molecules tab and in palette
search, and they need no process at all:

- sp³ Hybrid Set
- sp² Hybrids and p
- sp Hybrids and p
- H₂ σ Bond
- Ethylene π Bond
- Benzene p Orbitals

Their orbitals are the plugin's own, so each one can be edited by double-clicking it.
Templates with a molecule are placed by Molion, as every structure is.

## How the drawings are made

Each orbital is a polar plot of its angular part, r = L·f(θ)², which gives the teardrop
lobes of the p and d orbitals. The hybrids are drawn as textbooks draw them: f = a + cos θ,
plotted unsquared, so the back lobe grows with p character (sp < sp² < sp³). Lobes are the
regions where f keeps one sign. The picture's box is centred on the nucleus, so the
picture's centre is the atom it sits on.

`templates/*.json` are written by `tools/build_templates.py` from the same drawing code. Run
it after changing a drawing; the tests fail while a file is out of date.

## Files

| | |
|---|---|
| `main.py` | the JSON-RPC loop |
| `orbitals/model.py` | the orbital as pluginData |
| `orbitals/drawing.py` | lobes, pictures and previews |
| `orbitals/dialog.py` | Edit Orbital |
| `orbitals/actions.py` | what each contribution does |
| `orbitals/rpc.py` | the host connection (a `dialog` call serves `dialogEvent`s while it waits) |
| `tools/build_templates.py` | writes `templates/` |

Standard library only. Tests: `python3 -m pytest -q orbitals`.
