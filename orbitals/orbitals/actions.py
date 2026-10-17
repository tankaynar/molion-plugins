"""What each contribution in plugin.json does.

An orbital is a picture this plugin owns, with the orbital as pluginData, so it is redrawn
from data rather than edited as pixels. It is locked against being replaced, cropped or turned
by Molion's own commands (its angle is the plugin's, so its signs stay upright); it moves,
resizes and deletes like any picture. Every edit is one `update-image`: one undo step.
"""

from __future__ import annotations

from . import drawing, model
from .dialog import Session
from .rpc import Host

LOCKS = ['replace', 'crop', 'rotate']
NO_ORBITAL = 'Select one orbital first.'

# Toolbar tools and Place commands, by contribution id → orbital type.
TOOLS = {'tool-s': 's', 'tool-p': 'p', 'tool-sp3': 'sp3', 'tool-d': 'dx2y2'}
PLACE = {f'place-{kind}': kind for kind in model.TYPES}


class Actions:
    def __init__(self, host: Host) -> None:
        self.host = host

    def invoke(self, params: dict) -> dict:
        contribution = params.get('contributionId')
        if contribution in TOOLS:
            return self.place(TOOLS[contribution], params.get('gesture') or {})
        if contribution in PLACE:
            return self.place_asking(PLACE[contribution])
        handler = {
            'edit': self.edit,
            'flip-phase': self.flip_phase,
            'rotate-90': self.rotate_90,
        }.get(contribution)
        if handler is None:
            return {'ok': False, 'error': f"Unknown contribution '{contribution}'."}
        loaded = self.load(params.get('context') or {})
        if loaded is None:
            return {'ok': False, 'error': NO_ORBITAL}
        try:
            return handler(*loaded)
        except model.OrbitalError as error:
            return {'ok': False, 'error': str(error)}

    # ── Placing ──────────────────────────────────────────────────────────

    def place_asking(self, kind: str) -> dict:
        orbital = model.new_orbital(kind)
        gesture = self.host.gesture('vector', f'Click an atom for the {model.NAMES[kind]} orbital, or drag to aim it',
                                    click=True, preview=drawing.preview(orbital))
        return self.place(kind, gesture)

    def place(self, kind: str, gesture: dict) -> dict:
        """An orbital where the gesture was: on the atom pressed, else the press point; along
        the drag, or (a click) at the orbital's own default angle."""
        if gesture.get('cancelled') or 'start' not in gesture:
            return {'ok': True}
        at = gesture.get('startAtom') or gesture['start']
        dragged = (gesture.get('length') or 0) > 0
        orbital = model.new_orbital(kind, gesture.get('angleDegrees') if dragged else None)
        picture = drawing.drawing(orbital)
        self.host.scene('add-image', vector=picture, x=at['x'], y=at['y'],
                        width=picture['width'], height=picture['height'],
                        locks=LOCKS, pluginData=model.dump(orbital))
        return {'ok': True}

    # ── The orbital on the canvas ────────────────────────────────────────

    def load(self, context: dict) -> tuple[dict, dict] | None:
        images = context.get('images') or []
        if len(images) != 1:
            return None
        detail = self.host.scene('get-image', imageId=images[0])
        orbital = model.load(detail.get('pluginData'))
        return (detail['image'], orbital) if orbital is not None else None

    def save(self, image: dict, before: dict, after: dict) -> None:
        # Kept at the size it was given (the user may have resized it): the same scale on
        # the new drawing, whose box changes as the orbital turns.
        old = drawing.drawing(before)
        scale = image['height'] / old['height'] if old['height'] else 1.0
        picture = drawing.drawing(after)
        self.host.scene('update-image', imageId=image['id'], vector=picture,
                        width=picture['width'] * scale, height=picture['height'] * scale,
                        pluginData=model.dump(after))

    def edited(self, image: dict, orbital: dict, change) -> dict:
        after = model.copy_of(orbital)
        change(after)
        self.save(image, orbital, after)
        return {'ok': True}

    def edit(self, image: dict, orbital: dict) -> dict:
        session = Session(orbital)
        result = self.host.dialog(session.request(), session.handle)
        if result.get('cancelled'):
            return {'ok': True}
        if session.orbital != orbital:
            self.save(image, orbital, session.orbital)
        return {'ok': True}

    def flip_phase(self, image: dict, orbital: dict) -> dict:
        return self.edited(image, orbital, lambda o: o.update(flip=not o['flip']))

    def rotate_90(self, image: dict, orbital: dict) -> dict:
        return self.edited(image, orbital, lambda o: o.update(angle=model.normal_angle(o['angle'] + 90)))
