# Molion plugins

Plugins for the Molion chemical drawing app:

| Folder | Plugin | What it adds |
|---|---|---|
| `nmr-prediction` | NMR Prediction | a card with predicted ¹H and ¹³C spectra, linked to the drawn atoms |
| `pubchem` | PubChem | Search PubChem…, placing PubChem's own drawing of the compound |
| `tlc-plate` | TLC Plate | TLC plates, edited in a dialog |
| `orbitals` | Orbitals | s, p, sp, sp², sp³ and d orbitals on atoms, and orbital templates |
| `teaching` | Teaching | Newman, Fischer and Haworth projections, Disconnect Bond…, Present Mechanism |
| `picture-to-structure` | Picture to Structure | Convert to Structure: a picture of a molecule becomes the molecule |

Each folder is a separate program with its own README, licence files and tests. A plugin
talks to the app over newline-delimited JSON-RPC 2.0 on stdin and stdout, and its
`plugin.json` declares what it contributes and which capabilities it needs.

## Tests

One plugin at a time, from this folder (each has its own `tests/conftest.py`, so they are not
collected together):

```bash
for plugin in nmr-prediction pubchem tlc-plate orbitals teaching picture-to-structure; do
  python3 -m pytest -q "$plugin"
done
```

Most need only the standard library and pytest. Picture to Structure's recognition tests also
use numpy and Pillow and are skipped without them; its README explains its `.venv` and model.

## Releases

`p2s-model-v1` holds Picture to Structure's model files (MolScribe, MIT), which the plugin
downloads on first use; `picture-to-structure/tools/README.md` says how they are made.

## Licences

Each plugin's folder holds its licence and any notices for what it contains or downloads.
