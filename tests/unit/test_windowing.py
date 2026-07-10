"""Tests for viewer windowing utilities."""

from __future__ import annotations

import numpy as np

from medreport.viewer.windowing import normalize_to_uint8


def test_normalize_to_uint8_scales_full_range() -> None:
    image = np.array([[0.0, 5.0], [10.0, 15.0]], dtype=np.float32)

    normalized = normalize_to_uint8(image)

    assert normalized.dtype == np.uint8
    assert int(normalized.min()) == 0
    assert int(normalized.max()) == 255


def test_normalize_to_uint8_inverts() -> None:
    image = np.array([[0.0, 10.0]], dtype=np.float32)

    normalized = normalize_to_uint8(image, invert=True)

    assert normalized.tolist() == [[255, 0]]
