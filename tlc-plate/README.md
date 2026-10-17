# TLC Plate

A Molion plugin that ships with Molion: thin-layer chromatography plates, drawn as pictures
that stay sharp at any zoom and export as vectors to SVG and PDF.

Turn it on in **Settings → Plugins → Included with Molion**. Then press Space and choose
**New TLC Plate**, and click where it goes. A new plate has three lanes: starting material
(SM), a co-spot of the two (Co) and the reaction (Rxn).

## Editing a plate

Double-click a plate, or select it and choose **Edit TLC…**. The plate opens in a dialog;
nothing on the canvas changes until **Done**, which is one undo step. On the canvas the plate
only moves, turns and is deleted, so it cannot be changed by accident.

In the dialog:

- **Click** in a lane to add a spot there, or on a spot to select it.
- **Drag** a spot to move it up the plate or to another lane.
- **Double-click** a spot to delete it.
- **Plate**: the stain, the eluent (shown under the plate) and whether Rf values are shown.
- **Lane** (click its label under the plate): its label, and whether it is a co-spot of two other lanes.
  A co-spot lane shows both samples' spots; two within 0.03 Rf run as one.
- **Spot**: its Rf, intensity (strong, medium, faint), shape (round, streak, tailing) and colour.

Stains: none, UV 254 nm (dark spots on green, circled in pencil), KMnO₄, p-anisaldehyde,
vanillin, CAM, phosphomolybdic acid, ninhydrin and iodine. Each colours the plate and its
spots; anisaldehyde and vanillin offer several spot colours, as compounds differ.

## In the palette

With a plate selected, Space offers its settings directly: **Set Stain…**, **Set Eluent…**
and **Label Lanes…** (type "SM, Co, Rxn, P"; extra labels add lanes), **Add Lane**,
**Remove Last Lane**, **Add Co-spot Lane** and **Show or Hide Rf Values**.

## How it works

The plate is a picture this plugin owns (`add-image` with `locks` and `pluginData`); the
plate's lanes and spots are its `pluginData`, and the picture is always redrawn from them.
Edit TLC… uses Molion's `dialog` request: Molion draws the dialog, and sends a `dialogEvent`
for every click, drag and change, which the plugin answers with the redrawn plate. The
settings are two-step actions (`query` on an `own-image` action).

Plates made with the earlier TLC Plate example plugin, before this one had an id of its own,
are read and kept.

```bash
python3 -m pytest -q tlc-plate      # standard library + pytest
```
