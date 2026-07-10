"""Tests for application services."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from medreport.app.services import StudyImportService, VolumeService
from medreport.core.exceptions import DicomImportError
from medreport.models import ImageVolume, Patient, Series, Study


class StubStudyRepository:
    """Repository test double."""

    def import_folder(self, folder: Path) -> list[Study]:
        """Return a fixed study."""

        return [
            Study(
                study_instance_uid="study-1",
                description="Knee",
                patient=Patient(patient_id="p-1", name="Test Patient"),
            )
        ]


class StubVolumeRepository:
    """Volume repository test double."""

    def load_series(self, series: Series) -> ImageVolume:
        """Return a fixed volume."""

        return ImageVolume(
            series_uid=series.series_instance_uid,
            pixels=np.zeros((1, 2, 2), dtype=np.float32),
            spacing=(1.0, 1.0, 1.0),
        )


def test_study_import_rejects_missing_folder(tmp_path: Path) -> None:
    service = StudyImportService(StubStudyRepository())

    with pytest.raises(DicomImportError):
        service.import_folder(tmp_path / "missing")


def test_study_import_returns_repository_studies(tmp_path: Path) -> None:
    service = StudyImportService(StubStudyRepository())

    studies = service.import_folder(tmp_path)

    assert studies[0].description == "Knee"


def test_volume_service_delegates_to_repository() -> None:
    service = VolumeService(StubVolumeRepository())
    series = Series(series_instance_uid="series-1", description="Sag PD", modality="MR")

    volume = service.load_series(series)

    assert volume.slice_count == 1
