"""What each contribution in plugin.json does.

Every action is one invocation, so whatever it adds is one undo step. The chemistry —
which group sits where in a projection, what a cut bond leaves — is Molion's (get-projection,
get-fragments); this plugin decides how it is laid out and when it is shown.
"""

from __future__ import annotations

from . import geometry, mechanism, newman, projections, retro
from .geometry import BOND
from .rpc import Host, HostError, present

ANSWER = 'answer'
STEP = 'step'
SELECTION_KINDS = ('atoms', 'bonds', 'arrows', 'annotations', 'curvedArrows', 'brackets', 'images', 'shapes')
NO_NEWMAN = 'Select one Newman projection first.'


class Actions:
    def __init__(self, host: Host) -> None:
        self.host = host

    def invoke(self, params: dict) -> dict:
        contribution = params.get('contributionId')
        context = params.get('context') or {}
        chosen = (params.get('result') or {}).get('id')
        handler = {
            'newman': lambda: self.newman(context),
            'edit-newman': lambda: self.edit_newman(context),
            'fischer': lambda: self.fischer(context, wedges=False),
            'fischer-wedges': lambda: self.fischer(context, wedges=True),
            'haworth': lambda: self.haworth(context),
            'disconnect': lambda: self.disconnect(context),
            'mark-answer': lambda: self.mark_answer(context, True),
            'unmark-answer': lambda: self.mark_answer(context, False),
            'set-step': lambda: self.set_step(context, chosen),
            'clear-steps': lambda: self.clear_steps(context),
            'present-mechanism': self.present_mechanism,
        }.get(contribution)
        if handler is None:
            return {'ok': False, 'error': f"Unknown contribution '{contribution}'."}
        try:
            return handler()
        except HostError as error:
            # Molion's refusal ("there is no open carbon chain…") is the user's answer.
            text = str(error)
            return {'ok': False, 'error': text[:1].upper() + text[1:]}

    # ── Where to put things ──────────────────────────────────────────────

    def _beside(self, molecule_id: str) -> tuple[float, float]:
        """A point clear of the molecule on its right, level with its middle."""
        scene = self.host.scene('get-scene')
        mol = geometry.molecule(scene, molecule_id)
        if mol is None or not mol['atoms']:
            return (0.0, 0.0)
        box = geometry.molecule_box(mol)
        return (geometry.right_of(box, 2 * BOND), geometry.centre(box)[1])

    def _draw(self, atoms: list[dict], bonds: list[dict]) -> None:
        """Atoms and bonds laid out by projections.py, as one new molecule."""
        ids: dict[str, str] = {}
        first = None
        for atom in atoms:
            payload = {'element': atom['element'], 'x': atom['x'], 'y': atom['y']}
            if atom.get('label'):
                payload['label'] = atom['label']
            if first is not None:
                payload['attachTo'] = first
            added = self.host.scene('add-atom', **payload)['result']
            ids[atom['key']] = added['id']
            first = first or added['id']
        for bond in bonds:
            self.host.scene('add-bond', atomA=ids[bond['a']], atomB=ids[bond['b']],
                            order=bond['order'], stereo=bond['stereo'])

    @staticmethod
    def _warned(answer: dict, made: str) -> dict:
        warnings = answer.get('warnings') or []
        return {'ok': True, 'message': f'{made} {warnings[0][:1].upper() + warnings[0][1:]}.' if warnings else None}

    # ── Projections ──────────────────────────────────────────────────────

    def newman(self, context: dict) -> dict:
        bonds = context.get('bonds') or []
        if len(bonds) != 1:
            return {'ok': False, 'error': 'Select one bond: the one to look down.'}
        answer = self.host.scene('get-projection', kind='newman', bondId=bonds[0])
        model = newman.from_projection(answer)
        picture = newman.drawing(model)
        x, y = self._beside(answer['moleculeId'])
        self.host.scene('add-image', vector=picture, x=x + picture['width'] / 2, y=y,
                        width=picture['width'], height=picture['height'],
                        locks=['replace', 'crop'], pluginData=newman.dump(model))
        return self._warned(answer, 'Double-click the projection to turn the bond.') \
            if answer.get('warnings') else {'ok': True, 'message': 'Double-click the projection to turn the bond.'}

    def edit_newman(self, context: dict) -> dict:
        images = context.get('images') or []
        if len(images) != 1:
            return {'ok': False, 'error': NO_NEWMAN}
        detail = self.host.scene('get-image', imageId=images[0])
        model = newman.load(detail.get('pluginData'))
        if model is None:
            return {'ok': False, 'error': NO_NEWMAN}
        session = newman.Session(model)
        result = self.host.dialog(session.request(), session.handle)
        if result.get('cancelled') or session.newman == model:
            return {'ok': True}
        image = detail['image']
        before = newman.drawing(model)
        scale = image['height'] / before['height'] if before['height'] else 1.0
        picture = newman.drawing(session.newman)
        self.host.scene('update-image', imageId=image['id'], vector=picture,
                        width=picture['width'] * scale, height=picture['height'] * scale,
                        pluginData=newman.dump(session.newman))
        return {'ok': True}

    def _molecule_atom(self, context: dict) -> str | None:
        atoms = context.get('atoms') or []
        return atoms[0] if atoms else None

    def fischer(self, context: dict, wedges: bool) -> dict:
        atom = self._molecule_atom(context)
        if atom is None:
            return {'ok': False, 'error': 'Select the molecule to project.'}
        answer = self.host.scene('get-projection', kind='fischer', atoms=[atom])
        atoms, bonds = projections.fischer(answer, wedges)
        x, y = self._beside(answer['moleculeId'])
        low, _ = projections.width(atoms)
        height = (len(answer['chain']) + 1) * BOND
        self._draw(projections.offset(atoms, x - low + BOND * 0.5, y - height / 2), bonds)
        return self._warned(answer, 'Drew the Fischer projection.')

    def haworth(self, context: dict) -> dict:
        atom = self._molecule_atom(context)
        if atom is None:
            return {'ok': False, 'error': 'Select the sugar to project.'}
        answer = self.host.scene('get-projection', kind='haworth', atoms=[atom])
        atoms, bonds = projections.haworth(answer)
        x, y = self._beside(answer['moleculeId'])
        low, _ = projections.width(atoms)
        self._draw(projections.offset(atoms, x - low + BOND * 0.5, y), bonds)
        parts = [part for part in (answer.get('anomer'), answer.get('series')) if part]
        made = f"Drew the Haworth projection ({', '.join(parts)})." if parts else 'Drew the Haworth projection.'
        return self._warned(answer, made)

    # ── Retrosynthetic Disconnect ────────────────────────────────────────

    def disconnect(self, context: dict) -> dict:
        bonds = context.get('bonds') or []
        if len(bonds) != 1:
            return {'ok': False, 'error': 'Select one bond: the one to disconnect.'}
        bond = self.host.scene('get-bond', bondId=bonds[0])
        ends = [self.host.scene('get-atom', atomId=bond[end]) for end in ('atomA', 'atomB')]
        elements = {atom['id']: atom['element'] for atom in ends}

        # Every way of cutting it, worked out before the dialog: its handler may not call Molion.
        tried = []
        first = self._fragments(bonds[0], 'heterolytic')
        if first is not None:
            tried.append(('heterolytic', first))
            positive = first['polarity'][0]['negative']
            reverse = self._fragments(bonds[0], 'heterolytic', positive)
            if reverse is not None:
                tried.append(('heterolytic', reverse))
        radicals = self._fragments(bonds[0], 'homolytic')
        if radicals is not None:
            tried.append(('homolytic', radicals))
        offered = retro.options(tried, elements)
        if not offered:
            return {'ok': False, 'error': 'This bond cannot be disconnected.'}

        def note(option: dict) -> str:
            return 'Synthons: ' + ' + '.join(f['smiles'] for f in option['answer']['fragments'])

        state = {'value': offered[0]['value']}

        def fields() -> list[dict]:
            chosen = next(o for o in offered if o['value'] == state['value'])
            return [{'type': 'choice', 'id': 'cut', 'label': 'Cut into', 'value': state['value'],
                     'options': [{'value': o['value'], 'label': o['label']} for o in offered]},
                    {'type': 'note', 'text': note(chosen)}]

        def handle(params: dict) -> dict:
            event = params.get('event') or {}
            if event.get('type') == 'change' and event.get('field') == 'cut' and any(o['value'] == event.get('value') for o in offered):
                state['value'] = event['value']
                return {'fields': fields()}
            return {}

        result = self.host.dialog({'title': 'Disconnect Bond', 'doneLabel': 'Disconnect', 'fields': fields(),
                                   'message': None}, handle)
        if result.get('cancelled'):
            return {'ok': True}
        value = (result.get('values') or {}).get('cut', state['value'])
        chosen = next((o for o in offered if o['value'] == value), offered[0])
        self._place_disconnection(chosen['answer'], ends)
        return {'ok': True}

    def _fragments(self, bond_id: str, mode: str, positive: str | None = None) -> dict | None:
        payload = {'bondIds': [bond_id], 'mode': mode}
        if positive is not None:
            payload['positive'] = [positive]
        try:
            return self.host.scene('get-fragments', **payload)
        except HostError:
            return None

    def _place_disconnection(self, answer: dict, ends: list[dict]) -> None:
        x, y = self._beside(answer['moleculeId'])
        start = x - BOND
        self.host.scene('add-arrow', kind='Retro', x1=start, y1=y, x2=start + 1.8 * BOND, y2=y)
        cursor = start + 1.8 * BOND + 0.8 * BOND
        for n, fragment in enumerate(answer['fragments']):
            if n > 0:
                self.host.scene('add-annotation', text='+', x=cursor + 0.3 * BOND, y=y)
                cursor += 0.8 * BOND
            added = self.host.scene('add-from-molfile', molfile=fragment['molblock'], x=cursor + BOND, y=y)
            placed = added['result']['molecules']
            box = geometry.box([(a['x'], a['y']) for m in placed for a in m['atoms']])
            # Shift it so its left edge sits at the cursor, then move on past it.
            shift = cursor - box[0]
            if abs(shift) > 0.5:
                self.host.scene('move', atoms=[a['id'] for m in placed for a in m['atoms']], dx=shift, dy=0)
            cursor += (box[2] - box[0]) + 0.4 * BOND

        mark = retro.bond_mark(ends[0], ends[1])
        picture = retro.wavy()
        added = self.host.scene('add-image', vector=picture, x=mark['x'], y=mark['y'],
                                width=picture['width'], height=picture['height'], rotation=mark['rotation'])
        # The mark moves with the target.
        self.host.scene('group', atoms=[ends[0]['id']], images=[added['result']['id']])

    # ── Worksheets ───────────────────────────────────────────────────────

    def mark_answer(self, context: dict, mark: bool) -> dict:
        selection = {kind: list(context.get(kind) or []) for kind in SELECTION_KINDS}
        if not any(selection.values()):
            return {'ok': False, 'error': 'Select what the answer is first.'}
        # A structure selected as atoms takes its bonds too, so none is left behind in the question.
        if selection['atoms']:
            chosen = set(selection['atoms'])
            scene = self.host.scene('get-scene')
            for mol in scene.get('molecules') or []:
                for bond in mol['bonds']:
                    if bond['atomA'] in chosen and bond['atomB'] in chosen and bond['id'] not in selection['bonds']:
                        selection['bonds'].append(bond['id'])
        payload = {kind: ids for kind, ids in selection.items() if ids}
        changed = self.host.scene('set-marks', key=ANSWER, value='1' if mark else None, **payload)['result']['changed']
        if not mark:
            return {'ok': True, 'message': 'No longer an answer.' if changed else 'That was not marked as an answer.'}
        return {'ok': True, 'message': 'Marked as the answer. Export Question (answers left out)… leaves it out.'}

    # ── Mechanisms ───────────────────────────────────────────────────────

    def set_step(self, context: dict, chosen: str | None) -> dict:
        arrows = context.get('curvedArrows') or []
        if not arrows:
            return {'ok': False, 'error': 'Select the curved arrows first.'}
        number, _ = mechanism.step_value(chosen)
        if number == mechanism.UNNUMBERED:
            return {'ok': False, 'error': 'Type a step number, then a caption if you like.'}
        self.host.scene('set-marks', key=STEP, value=chosen, curvedArrows=arrows)
        return {'ok': True}

    def clear_steps(self, context: dict) -> dict:
        arrows = context.get('curvedArrows') or []
        if not arrows:
            return {'ok': False, 'error': 'Select the curved arrows first.'}
        self.host.scene('set-marks', key=STEP, value=None, curvedArrows=arrows)
        return {'ok': True}

    def present_mechanism(self) -> dict:
        scene = self.host.scene('get-scene')
        marks = self.host.scene('get-marks', key=STEP).get('marks') or []
        steps = {mark['id']: mark['value'] for mark in marks if mark['kind'] == 'curvedArrow'}
        try:
            request = mechanism.plan(scene, steps)
        except ValueError as error:
            return {'ok': False, 'error': str(error)}
        present(self.host, request)
        return {'ok': True}

    def query(self, params: dict) -> dict:
        contribution = params.get('contributionId')
        text = (params.get('text') or '').strip()
        if contribution == 'set-step':
            number_text, _, caption = text.partition(' ')
            try:
                number = int(number_text)
            except ValueError:
                return {'results': [], 'message': 'Type a step number, then a caption if you like.'}
            if not 1 <= number <= 999:
                return {'results': [], 'message': 'Steps are numbered from 1.'}
            caption = caption.strip()[:120]
            value = f'{number}|{caption}' if caption else str(number)
            title = f'Step {number} — {caption}' if caption else f'Step {number}'
            return {'results': [{'id': value, 'title': title, 'subtitle': 'For the selected curved arrows'}]}
        return {'results': [], 'message': f"Unknown search '{contribution}'."}
