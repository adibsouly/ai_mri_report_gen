"""Application use cases for study import and volume loading."""

from __future__ import annotations

from pathlib import Path

from medreport.app.ports import StudyRepository, VolumeRepository
from medreport.core.exceptions import DicomImportError
from medreport.models import ImageVolume, Series, Study


class StudyImportService:
    """Import studies while keeping DICOM details outside the UI layer."""

    def __init__(self, repository: StudyRepository) -> None:
        self._repository = repository

    def import_folder(self, folder: Path) -> list[Study]:
        """Import a folder of DICOM images."""

        if not folder.exists() or not folder.is_dir():
            raise DicomImportError(f"Folder does not exist: {folder}")
        return self._repository.import_folder(folder)


class VolumeService:
    """Load image volumes for viewer consumption."""

    def __init__(self, repository: VolumeRepository) -> None:
        self._repository = repository

    def load_series(self, series: Series) -> ImageVolume:
        """Load pixels for a selected series."""

        return self._repository.load_series(series)
