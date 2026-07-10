"""Domain models for DICOM study organization and image volumes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray


class Modality(StrEnum):
    """Common medical imaging modalities."""

    CT = "CT"
    MR = "MR"
    XR = "XR"
    CR = "CR"
    DX = "DX"
    US = "US"
    NM = "NM"
    OT = "OT"


@dataclass(frozen=True)
class Patient:
    """Patient demographics from a DICOM study."""

    patient_id: str
    name: str
    birth_date: date | None = None
    sex: str | None = None


@dataclass(frozen=True)
class DicomImage:
    """A single DICOM image instance."""

    sop_instance_uid: str
    instance_number: int
    path: Path
    rows: int | None = None
    columns: int | None = None
    acquisition_date: str | None = None
    image_position: tuple[float, ...] = field(default_factory=tuple)
    image_orientation: tuple[float, ...] = field(default_factory=tuple)


@dataclass
class Series:
    """A DICOM series containing sorted image instances."""

    series_instance_uid: str
    description: str
    modality: str
    number: int | None = None
    manufacturer: str | None = None
    repetition_time: float | None = None
    echo_time: float | None = None
    slice_thickness: float | None = None
    pixel_spacing: tuple[float, float] | None = None
    orientation: tuple[float, ...] = field(default_factory=tuple)
    images: list[DicomImage] = field(default_factory=list)

    def sorted_images(self) -> list[DicomImage]:
        """Return images in deterministic slice order."""

        return sorted(self.images, key=lambda image: (image.instance_number, str(image.path)))


@dataclass
class Study:
    """A DICOM study containing one or more series."""

    study_instance_uid: str
    description: str
    patient: Patient
    study_date: str | None = None
    accession_number: str | None = None
    series: list[Series] = field(default_factory=list)


@dataclass(frozen=True)
class ImageVolume:
    """Loaded pixel volume for a DICOM series."""

    series_uid: str
    pixels: NDArray[np.float32]
    spacing: tuple[float, float, float] | None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def slice_count(self) -> int:
        """Return number of available slices."""

        if self.pixels.ndim == 2:
            return 1
        return int(self.pixels.shape[0])

    def slice_at(self, index: int) -> NDArray[np.float32]:
        """Return a single 2D slice."""

        if self.pixels.ndim == 2:
            return self.pixels
        bounded = max(0, min(index, self.slice_count - 1))
        return np.asarray(self.pixels[bounded], dtype=np.float32)
