# PubChem

A Molion plugin that ships with Molion: **Search PubChem…** in the Space palette, and
PubChem's own drawing of the compound you choose, placed like a template.

Turn it on in **Settings → Plugins → Included with Molion**. Then press Space and choose
**Search PubChem…**. The palette stays open and searches PubChem as you type a name, a CID or an
InChIKey. Enter places the highlighted compound, and Escape goes back to the search. Typing a
name in the ordinary search also offers **Search PubChem for “…”**, which carries the text
across.

## What leaves your computer

This plugin is the only part of Molion that goes online, and only while it is turned on. It
sends nothing until you use Search PubChem…. After that, it sends:

- what you type after Search PubChem…, from two characters on, once you pause typing;
- the compound number (CID) of the result you place.

Everything goes to `pubchem.ncbi.nlm.nih.gov` and nowhere else. Nothing is sent about your
drawing. Answers are kept for five minutes, so repeating a search sends nothing.
PubChem asks for no more than five requests a second, and the plugin stays under that.

## How it works

The plugin declares one two-step command (`contributes.commands[].query` in plugin.json).
Molion sends a `query` request for each pause in typing and shows the rows that come back:
name, IUPAC name, formula, molecular weight and CID. It draws each row's thumbnail itself,
offline, from the SMILES in that row.

When you choose a row, Molion sends `invoke` with that row's id. The plugin fetches PubChem's
2D record and answers with
`place: {molfile, hydrogens: "fold"}`. Molion folds the record's hydrogens and scales it, then
places it. A SMILES cannot say where a disconnected ion sits, but the record can: heme keeps
its iron inside the porphyrin. If PubChem has no record, the plugin falls back to the row's
SMILES.

It is written for the standard library only, with no RDKit.

    python3 -m pytest -q pubchem
