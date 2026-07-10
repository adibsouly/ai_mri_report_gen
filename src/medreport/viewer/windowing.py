"""Image windowing utilities."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def normalize_to_uint8(
    image: NDArray[np.float32],
    window_center: float | None = None,
    window_width: float | None = None,
    invert: bool = False,
) -> NDArray[np.uint8]:
    """Normalize a floating point image to 8-bit grayscale."""

    if image.size == 0:
        return np.zeros((1, 1), dtype=np.uint8)

    if window_center is None or window_width is None or window_width <= 0:
        low = float(np.nanmin(image))
        high = float(np.nanmax(image))
    else:
        low = window_center - window_width / 2.0
        high = window_center + window_width / 2.0

    if high <= low:
        high = low + 1.0

    clipped = np.clip(image, low, high)
    normalized = ((clipped - low) / (high - low) * 255.0).astype(np.uint8)
    if invert:
        return 255 - normalized
    return normalized
