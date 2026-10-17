# Picture to Structure

A Molion plugin, included with Molion and off until turned on in Settings → Plugins. Select a
picture of a molecule (pasted from a paper, a screenshot, a scan), press Space and choose
**Convert to Structure**: the picture is replaced by the molecule, laid out as it was drawn,
in one undo step. A locked picture stays, and the molecule goes beside it. Crop a picture to
one molecule first for the best result; the crop is what gets read.

Recognition is [MolScribe](https://github.com/thomas0809/MolScribe) (MIT), exported to ONNX and
run by onnxruntime on this computer.

## What goes online

Only the model, once. The first conversion asks before downloading it from
github.com/tankaynar/molion-plugins and keeps it in the plugin's data folder
(`~/.molion/plugin-data/molion.picture-to-structure/`). Pictures never leave the computer.
Deleting that folder deletes the model; it is downloaded again on the next conversion.

## Development

The protocol, molfile and download code are standard library. Recognition needs onnxruntime,
numpy and Pillow; put them in a `.venv` here and the plugin restarts itself with it:

```bash
python3 -m venv picture-to-structure/.venv
picture-to-structure/.venv/bin/pip install -r picture-to-structure/requirements.txt
```

Until the model is published, point `MOLION_P2S_MODEL_DIR` at a folder exported with
`tools/export_onnx.py`.

Tests need neither the libraries nor the model, and reach no network:

```bash
python3 -m pytest -q picture-to-structure
```
