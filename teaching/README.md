# Teaching

A Molion plugin that ships with Molion, for teaching organic chemistry: projections,
retrosynthetic disconnections, mechanisms presented one arrow at a time, and worksheets.
Atomic and hybrid orbitals are a plugin of their own, **Orbitals**.

Turn it on in **Settings → Plugins → Included with Molion**. Everything it adds is in the
palette (press Space). It acts on what is selected and is one undo step each time.

## Projections

- **Newman Projection** (select one bond): looking down the bond, from its first atom to its
  second. The back carbon is the circle. It is placed right of the molecule, as a picture.
  Double-click it, or choose **Edit Newman…**, to turn the bond: staggered anti or gauche,
  eclipsed, or any dihedral. A ring bond or a multiple bond does not turn.
- **Fischer Projection** (select the molecule): its carbon chain upright, the most oxidised end
  on top (CHO above CH2OH). It is drawn as atoms and bonds, so the formula and analysis still
  read it. **Fischer Projection with Wedges** wedges the horizontal bonds toward the viewer,
  which is what the cross means, so Molion keeps the stereo. The plain cross is how textbooks
  print it, and its stereocentres read as unspecified.
- **Haworth Projection** (select a sugar): the ring flat, with the oxygen at the back right and
  the front edge bold. Each group points straight up or down. It is also drawn as atoms and
  bonds, and the toast names the anomer and series (β, D).

Which group sits where comes from Molion, through `get-projection`. It
reads each centre's configuration from a 3D model, so a projection agrees with the wedges
drawn. A stereocentre the drawing leaves open is shown one way and said in the toast.

## Retrosynthetic Disconnect

Select a single bond and choose **Disconnect Bond…**. The dialog offers each way of cutting it:

- the less electronegative end positive (C⁺ and O⁻);
- the reverse;
- radicals.

Each option shows its synthons. **Disconnect** places them right of the target after the
retrosynthetic arrow (⇒), and puts a wavy line across the bond. The line is grouped with the
target, so it moves with it.

## Present Mechanism

Draw a mechanism, with curved arrows and the reaction arrows between its stages. Then choose
**Present Mechanism**. The drawing fills the screen:

- it opens on the first stage without its curved arrows;
- each step adds one curved arrow;
- after a stage's arrows, the next reaction arrow comes with the next stage.

Keys: → or Space steps on, ← steps back, Home and End jump, Esc ends. A click steps on, a
right-click steps back.

Arrows appear in reading order of their tails. To choose the order, select arrows and use
**Set Step…** with a number and, if you like, a caption ("2 Proton transfer"). The caption
shows while that step is on screen. **Clear Steps** returns the selected arrows to reading
order.

## Worksheets

Select what the answer is: a product, a reagent, a curved arrow, some text. Then choose **Mark
as Answer**. A dashed rose outline labelled "Answer" shows it on screen, never in an export.

**Export Question (answers left out)…** opens Export with Content set to the question. The
picture, and the editable copy inside it, leave the answers out but keep the whole drawing's
size, so the question and the answer key line up. **Unmark Answer** takes the mark off.

## Files

| | |
|---|---|
| `main.py` | the JSON-RPC loop |
| `teaching/actions.py` | what each contribution does |
| `teaching/newman.py` | the Newman picture and its dialog |
| `teaching/projections.py` | Fischer and Haworth layouts |
| `teaching/retro.py` | disconnection options and the wavy mark |
| `teaching/mechanism.py` | the presentation's steps (pure) |
| `teaching/geometry.py` | boxes and reading order (pure) |
| `teaching/rpc.py` | the host connection |

Standard library only. Tests: `python3 -m pytest -q teaching`.
