"""Ports used by application services."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from medreport.models import ImageVolume, Series, Study


class StudyRepository(Protocol):
    """Repository able to discover studies from a filesystem location."""

    def import_folder(self, folder: Path) -> list[Study]:
        """Import DICOM studies from a folder."""


class VolumeRepository(Protocol):
    """Repository able to load a pixel volume for a series."""

    def load_series(self, series: Series) -> ImageVolume:
        """Load pixels for a DICOM series."""
