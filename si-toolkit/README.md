# SI Toolkit

A Molion plugin that ships with Molion: the calculated numbers a paper's supporting
information prints for each compound, ready to paste.

Turn it on in **Settings → Plugins → Included with Molion**. Then press Space:

- **Copy HRMS Line…** lists the adducts at once: ESI [M+H]⁺, [M+Na]⁺, [M+K]⁺, [M+NH₄]⁺,
  [M−H]⁻ and [M+Cl]⁻, APCI [M+H]⁺, and EI M⁺·, each with its m/z. Type to narrow the list
  ("na", "neg", "m-h"). Choosing one copies
  `HRMS (ESI) m/z: [M+Na]⁺ calcd for C₁₅H₂₀NaO₃ 271.1305, found ` for each selected structure,
  ready for the measured value. The adduct chosen last is listed first next time.
- **Copy Elemental Analysis** copies `Anal. Calcd for C₁₅H₂₀O₃: C, 72.55; H, 8.12`, with C, H,
  N and S, which are what combustion analysis measures.
- **Copy SI Stub** copies a block for every compound in the drawing, for Word: its number and
  name, its formula and HRMS line, its SMILES and InChI. Numbered compounds come first, in
  number order (1, 2, 3a, 3b, 10), then the rest as drawn.
- **Export SI Stub as CSV…** saves the same as a CSV file: `number, name, formula, ionisation,
  adduct, mz, smiles, inchi`.

**Show SI Toolkit** shows the SI card, with the selection's HRMS line, elemental analysis and
stub, each with **Copy**.

Nothing is selected: all of the drawing. A structure drawn as an ion is measured as it is
([M]⁺), whatever adduct is chosen.

## How the numbers are made

Molion's chemistry server gives each structure's composition and exact mass: the most
abundant isotope of each element, a drawn isotope its own, with the electrons of a drawn ion
allowed for. The plugin adds the adduct's atoms (AME2020 nuclide masses) and takes away one
electron for each positive charge, or adds one for each negative charge, then divides by the
charge. m/z is given to four places, and percentages to two. Names are systematic names made on
this machine by Molion, never looked up online.

The plugin only reads the drawing. Its text reaches the clipboard and its file reaches the disk
through Molion (`clipboard` and `saveFile`), so it needs `scene:read` and `files`, and never
touches the filesystem itself.

## Tests

Standard library and pytest:

```bash
python3 -m pytest -q si-toolkit
```
