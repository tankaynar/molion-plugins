import io

import pytest

np = pytest.importorskip('numpy')
Image = pytest.importorskip('PIL.Image')

from p2s import preprocess  # noqa: E402


def png(pixels):
    out = io.BytesIO()
    Image.fromarray(pixels).save(out, format='PNG')
    return out.getvalue()


def drawing():
    pixels = np.full((100, 200, 3), 255, dtype=np.uint8)
    pixels[20:40, 50:150] = 0          # the "molecule"
    return pixels


def test_the_white_margin_is_trimmed_and_the_box_says_where():
    tensor, box = preprocess.prepare(png(drawing()), size=64)
    assert tensor.shape == (1, 3, 64, 64)
    assert (box.left, box.top, box.width, box.height) == (50, 20, 100, 20)
    assert box.to_pixels(0.5, 1.0) == (100.0, 40.0)


def test_near_white_noise_does_not_stop_the_trim():
    pixels = drawing()
    pixels[0:5, 0:5] = 250
    _, box = preprocess.prepare(png(pixels), size=32)
    assert (box.left, box.top) == (50, 20)


def test_molions_crop_is_applied_first():
    pixels = drawing()
    pixels[80:90, 0:10] = 0            # outside the crop
    _, box = preprocess.prepare(png(pixels), {'left': 0.2, 'top': 0, 'right': 1, 'bottom': 0.5}, size=32)
    assert (box.left, box.top, box.width, box.height) == (50, 20, 100, 20)


def test_transparency_reads_as_white():
    pixels = np.zeros((50, 50, 4), dtype=np.uint8)   # fully transparent black
    pixels[10:20, 10:20] = (0, 0, 0, 255)
    out = io.BytesIO()
    Image.fromarray(pixels, 'RGBA').save(out, format='PNG')
    _, box = preprocess.prepare(out.getvalue(), size=32)
    assert (box.left, box.top, box.width, box.height) == (10, 10, 10, 10)


def test_a_blank_picture_keeps_its_whole_box():
    _, box = preprocess.prepare(png(np.full((30, 40, 3), 255, dtype=np.uint8)), size=16)
    assert (box.width, box.height) == (40, 30)


def test_resizing_matches_opencvs_bilinear_at_the_corners():
    pixels = np.zeros((2, 2, 3), dtype=np.uint8)
    pixels[0, 0] = 255
    out = preprocess.resize_linear(pixels, 4)
    assert out[0, 0, 0] == 255 and out[3, 3, 0] == 0
    assert out[0, 1, 0] == 191                       # 0.75 · 255, as cv2.INTER_LINEAR gives
