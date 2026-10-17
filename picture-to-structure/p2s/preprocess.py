"""A picture as MolScribe's encoder expects it, and the box its coordinates are relative to.

Follows MolScribe's own inference transforms: trim the white margin, stretch to 384 × 384
with bilinear interpolation as OpenCV does it (no antialiasing; the model was trained on
that), grey, then ImageNet normalisation. The trim treats near-white as white, so a JPEG's
faint noise around a drawing does not stop it, which upstream's exact-white test would.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps

WHITE = 245
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)


@dataclass(frozen=True)
class Box:
    """Where the model's 0–1 coordinates fall, in the picture's pixels."""
    left: float
    top: float
    width: float
    height: float

    def to_pixels(self, x: float, y: float) -> tuple[float, float]:
        return self.left + x * self.width, self.top + y * self.height


def load_rgb(data: bytes) -> np.ndarray:
    image = Image.open(io.BytesIO(data))
    image = ImageOps.exif_transpose(image)
    if image.mode in ('RGBA', 'LA', 'P'):
        image = image.convert('RGBA')
        white = Image.new('RGBA', image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(white, image)
    return np.asarray(image.convert('RGB'), dtype=np.uint8)


def crop_fractions(pixels: np.ndarray, crop: dict | None) -> tuple[np.ndarray, int, int]:
    """Molion's crop (fractions of the source), so only the part that shows is read."""
    if not crop:
        return pixels, 0, 0
    height, width = pixels.shape[:2]
    left = int(round(float(crop.get('left', 0)) * width))
    right = int(round(float(crop.get('right', 1)) * width))
    top = int(round(float(crop.get('top', 0)) * height))
    bottom = int(round(float(crop.get('bottom', 1)) * height))
    left, top = max(0, min(left, width - 1)), max(0, min(top, height - 1))
    right, bottom = max(left + 1, min(right, width)), max(top + 1, min(bottom, height))
    return pixels[top:bottom, left:right], left, top


def trim_white(pixels: np.ndarray, white: int = WHITE) -> tuple[int, int, int, int]:
    """(top, bottom, left, right) of everything darker than `white`; the whole picture if blank."""
    ink = (pixels < white).any(axis=2)
    rows, cols = np.flatnonzero(ink.any(axis=1)), np.flatnonzero(ink.any(axis=0))
    if rows.size == 0:
        return 0, pixels.shape[0], 0, pixels.shape[1]
    return int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1


def resize_linear(pixels: np.ndarray, size: int) -> np.ndarray:
    """OpenCV's INTER_LINEAR: pixel centres aligned, edges clamped, no antialiasing."""
    height, width = pixels.shape[:2]

    def axis(source: int):
        position = (np.arange(size, dtype=np.float64) + 0.5) * (source / size) - 0.5
        position = np.clip(position, 0, source - 1)
        low = np.floor(position).astype(np.int64)
        high = np.minimum(low + 1, source - 1)
        return low, high, (position - low)

    y0, y1, wy = axis(height)
    x0, x1, wx = axis(width)
    image = pixels.astype(np.float64)
    top = image[y0][:, x0] * (1 - wx)[None, :, None] + image[y0][:, x1] * wx[None, :, None]
    bottom = image[y1][:, x0] * (1 - wx)[None, :, None] + image[y1][:, x1] * wx[None, :, None]
    out = top * (1 - wy)[:, None, None] + bottom * wy[:, None, None]
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def to_tensor(pixels: np.ndarray, mean=MEAN, std=STD) -> np.ndarray:
    grey = np.rint(pixels[..., 0] * 0.299 + pixels[..., 1] * 0.587 + pixels[..., 2] * 0.114)
    grey = np.clip(grey, 0, 255).astype(np.float32) / 255.0
    channels = [(grey - m) / s for m, s in zip(mean, std)]
    return np.stack(channels)[None].astype(np.float32)


def prepare(data: bytes, crop: dict | None = None, size: int = 384, white: int = WHITE,
            mean=MEAN, std=STD) -> tuple[np.ndarray, Box]:
    pixels, offset_x, offset_y = crop_fractions(load_rgb(data), crop)
    top, bottom, left, right = trim_white(pixels, white)
    pixels = pixels[top:bottom, left:right]
    box = Box(offset_x + left, offset_y + top, right - left, bottom - top)
    return to_tensor(resize_linear(pixels, size), mean, std), box
