"""Convert to Structure: the selected picture becomes the molecule it shows, in one undo step.

The steps: read the picture (and its crop), make sure the model is here (asking before the
download), recognise, write a molfile, then remove the picture and add the molecule where it
was. A locked picture stays, and the molecule goes beside it.
"""

from __future__ import annotations

import base64
from typing import Callable, Protocol

from . import molfile
from .model_store import SOURCE, ModelError, ModelStore, size_text
from .rpc import Host, HostError
from .structure import Structure

# Below CONFIDENT the reply asks the user to check the drawing; below READABLE the picture is
# taken not to show a structure at all (text, a photo, a plot), rather than drawing nonsense.
# Measured on 5,772 readings of MolScribe's real-world benchmark (tools/README.md): below 0.6,
# 1 in 35 was right; below 0.85, 4 in 10 were wrong, against 1 in 6 overall.
CONFIDENT = 0.85
READABLE = 0.6


class Recognizer(Protocol):
    def recognise(self, data: bytes, crop: dict | None) -> Structure: ...


class Converter:
    def __init__(self, host: Host, store: ModelStore,
                 load_recognizer: Callable[[str], Recognizer]) -> None:
        self.host = host
        self.store = store
        self._load = load_recognizer
        self._recognizer: Recognizer | None = None
        self._loaded_from: str | None = None

    def invoke(self, params: dict) -> dict:
        images = ((params.get('context') or {}).get('images')) or []
        if len(images) != 1:
            return {'ok': False, 'error': 'Select one picture first.'}
        image_id = images[0]

        picture = self.host.scene('get-image', imageId=image_id, includeData=True)
        image = picture.get('image') or {}
        if not picture.get('data'):
            return {'ok': False, 'error': 'Convert to Structure reads bitmap pictures, not drawings.'}

        if not self.store.ready():
            try:
                if not self._ask_to_download():
                    return {'ok': False}
                self.store.download(self.host.progress)
            except ModelError as error:
                return {'ok': False, 'error': str(error)}

        # Before loading: the first load reads the whole model, which takes a few seconds.
        self.host.progress('Reading the structure')
        try:
            recognizer = self._recognizer_for(self.store.folder)
        except ImportError as error:
            return {'ok': False, 'error': f'Picture to Structure is missing a library it needs ({error.name}).'}

        structure = recognizer.recognise(base64.b64decode(picture['data']), image.get('crop'))
        if structure.empty or structure.confidence < READABLE:
            return {'ok': False,
                    'error': 'No structure found in this picture. Crop it to one molecule and try again.'}

        text = molfile.write(structure)
        x, y = image.get('centerX', 0.0), image.get('centerY', 0.0)
        kept = False
        try:
            self.host.scene('delete', images=[image_id])
        except HostError:
            # Locked by its owner: leave it, and put the molecule to its right.
            kept = True
            x += image.get('width', 0.0)
        self.host.scene('add-from-molfile', molfile=text, x=x, y=y)

        if structure.confidence < CONFIDENT:
            message = 'Converted. Check the structure: some of it was unclear.'
        elif kept:
            message = 'Converted. The picture is locked, so it stays.'
        else:
            message = 'Converted to a structure.'
        return {'ok': True, 'message': message}

    def _recognizer_for(self, folder: str) -> Recognizer:
        if self._recognizer is None or self._loaded_from != folder:
            self._recognizer = self._load(folder)
            self._loaded_from = folder
        return self._recognizer

    def _ask_to_download(self) -> bool:
        if not self.store.published and not self.store.override:
            raise ModelError('The recognition model is not published yet.')
        size = size_text(self.store.total_size)
        answer = self.host.dialog({
            'title': 'Download Recognition Model',
            'doneLabel': 'Download',
            'fields': [
                {'type': 'note',
                 'text': f'Picture to Structure needs its recognition model ({size}) from {SOURCE}.'},
                {'type': 'note',
                 'text': 'It is downloaded once and kept on this computer. Pictures never leave it.'},
            ],
        })
        return not answer.get('cancelled', True)
