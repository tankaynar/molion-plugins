"""How each visualisation looks: the plate's background and the colour its spots take.

Colours are what a chemist would recognise on the bench, softened enough that a plate still
reads in a paper's figure. A stain that gives different compounds different colours
(p-anisaldehyde, vanillin) offers several swatches; the rest offer shades of their one colour.
"""

from __future__ import annotations

STAINS: list[dict] = [
    {'id': 'none', 'name': 'None', 'caption': '', 'keywords': 'silica plain blank',
     'description': 'A plain silica plate with grey spots',
     'background': '#F6F6F0', 'spot': '#6A6A72',
     'swatches': ['#6A6A72', '#3E3E46', '#9A9AA2']},
    {'id': 'uv254', 'pencil': '#3E4A3A', 'name': 'UV 254 nm', 'caption': 'UV 254 nm', 'keywords': 'uv light f254 fluorescent lamp',
     'description': 'Dark spots on the green glow of an F254 plate, circled in pencil',
     'background': '#D9EDD0', 'spot': '#3D3F5C', 'circled': True,
     'swatches': ['#3D3F5C', '#5A5C78', '#2A2B3D']},
    {'id': 'kmno4', 'pencil': '#33263A', 'name': 'KMnO₄', 'caption': 'KMnO₄', 'keywords': 'kmno4 permanganate potassium oxidising',
     'description': 'Yellow spots on a purple background',
     'background': '#B57FC4', 'spot': '#D9B640',
     'swatches': ['#D9B640', '#C99A2E', '#E8D27A', '#A8742A']},
    {'id': 'anisaldehyde', 'pencil': '#4A3A44', 'name': 'p-Anisaldehyde', 'caption': 'p-anisaldehyde',
     'keywords': 'anisaldehyde panisaldehyde para',
     'description': 'Spots in many colours on a pale pink background',
     'background': '#F4E6EA', 'spot': '#7A3E9D',
     'swatches': ['#7A3E9D', '#2F4FA8', '#C0392B', '#2E8B57', '#D98E2B', '#8B5A3C', '#C2477E']},
    {'id': 'vanillin', 'name': 'Vanillin', 'caption': 'vanillin', 'keywords': 'vanillin',
     'description': 'Spots in many colours on an off-white background',
     'background': '#F5F1E4', 'spot': '#4F5FA8',
     'swatches': ['#4F5FA8', '#7A3E9D', '#B23A48', '#3A8F6A', '#C27A2C', '#6B4A2F']},
    {'id': 'cam', 'pencil': '#2A3346', 'name': 'CAM (Hanessian’s)', 'caption': 'CAM', 'keywords': 'cam hanessian ceric ammonium molybdate cerium',
     'description': 'Dark blue spots on a light blue background',
     'background': '#DCE7F3', 'spot': '#1F3A80',
     'swatches': ['#1F3A80', '#33509E', '#152857']},
    {'id': 'pma', 'pencil': '#353A22', 'name': 'Phosphomolybdic Acid', 'caption': 'PMA', 'keywords': 'pma phosphomolybdic acid',
     'description': 'Dark green spots on a yellow-green background',
     'background': '#E6EBB4', 'spot': '#2F4D3A',
     'swatches': ['#2F4D3A', '#3F6B4E', '#1E3326']},
    {'id': 'ninhydrin', 'name': 'Ninhydrin', 'caption': 'ninhydrin', 'keywords': 'ninhydrin amine amino acid',
     'description': 'Pink to purple spots on a white background',
     'background': '#FAF8F6', 'spot': '#B0407A',
     'swatches': ['#B0407A', '#7E3A8F', '#D46A8C', '#C9A02A']},
    {'id': 'iodine', 'name': 'Iodine', 'caption': 'I₂', 'keywords': 'iodine i2 chamber vapour',
     'description': 'Brown spots on a pale yellow background',
     'background': '#F6F0D6', 'spot': '#8A5A20',
     'swatches': ['#8A5A20', '#A6742E', '#6B4415']},
]

BY_ID = {stain['id']: stain for stain in STAINS}
DEFAULT = 'uv254'


def get(stain_id: str) -> dict:
    return BY_ID.get(stain_id) or BY_ID[DEFAULT]


def matching(text: str) -> list[dict]:
    """Stains whose name or keywords contain every word typed, in catalogue order."""
    words = text.lower().replace('₄', '4').replace('₂', '2').split()
    found = []
    for stain in STAINS:
        haystack = ' '.join((stain['id'], stain['name'].lower().replace('₄', '4').replace('₂', '2'), stain['keywords']))
        if all(word in haystack for word in words):
            found.append(stain)
    return found
