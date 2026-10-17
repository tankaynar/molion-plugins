"""What each contribution in plugin.json does.

The plate is a picture this plugin owns: placed with locks, so Molion's own image commands
cannot replace, stretch or fade it, and with the plate as pluginData, so it is redrawn from
data rather than edited as pixels. Every action edits the plate it is given and saves it in
one `update-image`, so each is one undo step.
"""

from __future__ import annotations

import json

from . import drawing, model, stains
from .dialog import Session
from .rpc import Host

LOCKS = ['replace', 'resize', 'opacity']

ELUENTS = [
    '10% EtOAc/hexanes', '20% EtOAc/hexanes', '30% EtOAc/hexanes', '50% EtOAc/hexanes',
    'Hexanes/EtOAc 4:1', 'Hexanes/EtOAc 1:1', '100% EtOAc', '5% MeOH/DCM', '10% MeOH/DCM',
    'DCM', '5% Et₂O/pentane', 'Toluene', 'EtOAc/MeOH/H₂O 8:1:1',
]
LABEL_PRESETS = [['SM', 'Co', 'Rxn'], ['SM', 'Rxn'], ['A', 'B', 'C'], ['1', '2', '3', '4']]
NO_PLATE = 'Select one TLC plate first.'


class Actions:
    def __init__(self, host: Host) -> None:
        self.host = host

    # ── Dispatch ─────────────────────────────────────────────────────────

    def invoke(self, params: dict) -> dict:
        contribution = params.get('contributionId')
        context = params.get('context') or {}
        chosen = (params.get('result') or {}).get('id')
        if contribution == 'new-plate':
            return self.new_plate()
        handler = {
            'edit': self.edit,
            'set-stain': lambda image, plate: self.set_stain(image, plate, chosen),
            'set-eluent': lambda image, plate: self.set_eluent(image, plate, chosen),
            'label-lanes': lambda image, plate: self.label_lanes(image, plate, chosen),
            'add-lane': self.add_lane,
            'remove-lane': self.remove_lane,
            'add-cospot': self.add_cospot,
            'toggle-rf': self.toggle_rf,
        }.get(contribution)
        if handler is None:
            return {'ok': False, 'error': f"Unknown contribution '{contribution}'."}
        loaded = self.load(context)
        if loaded is None:
            return {'ok': False, 'error': NO_PLATE}
        try:
            return handler(*loaded)
        except model.PlateError as error:
            return {'ok': False, 'error': str(error)}

    # ── The plate on the canvas ──────────────────────────────────────────

    def load(self, context: dict) -> tuple[dict, dict] | None:
        images = context.get('images') or []
        if len(images) != 1:
            return None
        detail = self.host.scene('get-image', imageId=images[0])
        plate = model.load(detail.get('pluginData'))
        return (detail['image'], plate) if plate is not None else None

    def save(self, image: dict, before: dict, after: dict) -> None:
        # Kept at the scale it was placed at; width and height are the owner's to set,
        # whatever the resize lock says to everyone else.
        scale = image['height'] / drawing.height(before)
        picture = drawing.drawing(after)
        self.host.scene('update-image', imageId=image['id'], vector=picture,
                        width=picture['width'] * scale, height=picture['height'] * scale,
                        pluginData=model.dump(after))

    def edited(self, image: dict, plate: dict, change, message: str | None = None) -> dict:
        after = model.copy_of(plate)
        change(after)
        self.save(image, plate, after)
        return {'ok': True, 'message': message} if message else {'ok': True}

    # ── Contributions ────────────────────────────────────────────────────

    def new_plate(self) -> dict:
        plate = model.new_plate()
        picked = self.host.gesture('point', 'Click where the plate goes', preview=drawing.preview(plate))
        if picked.get('cancelled'):
            return {'ok': True}
        point, picture = picked['point'], drawing.drawing(plate)
        self.host.scene('add-image', vector=picture, x=point['x'], y=point['y'],
                        width=picture['width'], height=picture['height'],
                        locks=LOCKS, pluginData=model.dump(plate))
        return {'ok': True, 'message': 'Double-click the plate to edit it.'}

    def edit(self, image: dict, plate: dict) -> dict:
        session = Session(plate)
        result = self.host.dialog(session.request(), session.handle)
        if result.get('cancelled'):
            return {'ok': True}
        if session.plate != plate:
            self.save(image, plate, session.plate)
        return {'ok': True}

    def set_stain(self, image: dict, plate: dict, chosen: str | None) -> dict:
        if chosen not in stains.BY_ID:
            return {'ok': False, 'error': 'Choose a stain from the list.'}
        return self.edited(image, plate, lambda p: p.update(stain=chosen),
                           f"Stained with {stains.get(chosen)['name']}.")

    def set_eluent(self, image: dict, plate: dict, chosen: str | None) -> dict:
        eluent = (chosen or '').removeprefix('eluent:')[:model.MAX_ELUENT]
        return self.edited(image, plate, lambda p: p.update(eluent=eluent))

    def label_lanes(self, image: dict, plate: dict, chosen: str | None) -> dict:
        try:
            labels = json.loads((chosen or '').removeprefix('labels:'))
        except json.JSONDecodeError:
            return {'ok': False, 'error': 'Type the labels, separated by commas.'}
        if not isinstance(labels, list) or not labels:
            return {'ok': False, 'error': 'Type the labels, separated by commas.'}
        return self.edited(image, plate, lambda p: model.set_labels(p, [str(label) for label in labels]))

    def add_lane(self, image: dict, plate: dict) -> dict:
        return self.edited(image, plate, model.add_lane)

    def remove_lane(self, image: dict, plate: dict) -> dict:
        return self.edited(image, plate, lambda p: model.remove_lane(p, len(p['lanes']) - 1))

    def add_cospot(self, image: dict, plate: dict) -> dict:
        return self.edited(image, plate, model.add_cospot_lane)

    def toggle_rf(self, image: dict, plate: dict) -> dict:
        return self.edited(image, plate, lambda p: p.update(showRf=not p['showRf']))

    # ── Two-step actions: what the palette lists as the user types ─────────

    def query(self, params: dict) -> dict:
        contribution = params.get('contributionId')
        text = (params.get('text') or '').strip()
        if contribution == 'set-stain':
            found = stains.matching(text)
            return {'results': [{'id': stain['id'], 'title': stain['name'], 'subtitle': stain['description']}
                                for stain in found],
                    'message': None if found else 'No stain by that name.'}
        if contribution == 'set-eluent':
            rows = [{'id': 'eluent:' + text[:model.MAX_ELUENT], 'title': f'Set Eluent to “{text[:model.MAX_ELUENT]}”'}]
            lowered = text.lower()
            rows += [{'id': 'eluent:' + eluent, 'title': eluent, 'section': 'Common Eluents'}
                     for eluent in ELUENTS if lowered in eluent.lower() and eluent != text]
            return {'results': rows}
        if contribution == 'label-lanes':
            rows = []
            labels = model.parse_labels(text)[:model.MAX_LANES]
            if labels:
                rows.append({'id': 'labels:' + json.dumps(labels), 'title': ' · '.join(labels),
                             'subtitle': f'{len(labels)} lane{"" if len(labels) == 1 else "s"}, from the left'})
            lowered = text.lower()
            rows += [{'id': 'labels:' + json.dumps(preset), 'title': ' · '.join(preset), 'section': 'Common Labels'}
                     for preset in LABEL_PRESETS
                     if preset != labels and lowered in ' '.join(preset).lower()]
            return {'results': rows}
        return {'results': [], 'message': f"Unknown search '{contribution}'."}
