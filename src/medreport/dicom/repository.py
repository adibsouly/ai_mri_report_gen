"""DICOM filesystem repositories built on pydicom and SimpleITK."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import pydicom
import SimpleITK as sitk
import structlog
from pydicom.dataset import FileDataset

from medreport.core.exceptions import DicomImportError, VolumeLoadError
from medreport.models import DicomImage, ImageVolume, Patient, Series, Study

LOGGER = structlog.get_logger(__name__)


class PydicomStudyRepository:
    """Discover DICOM studies from folders using pydicom metadata parsing."""

    def import_folder(self, folder: Path) -> list[Study]:
        """Scan a folder recursively and return grouped studies."""

        datasets = list(self._iter_dicom_headers(folder))
        if not datasets:
            raise DicomImportError(f"No DICOM files found in {folder}")

        studies_by_uid: dict[str, Study] = {}
        series_by_uid: dict[str, Series] = {}
        series_paths: dict[str, list[DicomImage]] = defaultdict(list)

        for path, dataset in datasets:
            study_uid = str(getattr(dataset, "StudyInstanceUID", "unknown-study"))
            series_uid = str(getattr(dataset, "SeriesInstanceUID", f"series-{path}"))

            if study_uid not in studies_by_uid:
                studies_by_uid[study_uid] = Study(
                    study_instance_uid=study_uid,
                    description=str(getattr(dataset, "StudyDescription", "Untitled Study")),
                    patient=Patient(
                        patient_id=str(getattr(dataset, "PatientID", "Unknown")),
                        name=str(getattr(dataset, "PatientName", "Unknown")),
                    ),
                    study_date=str(getattr(dataset, "StudyDate", "")) or None,
                    accession_number=str(getattr(dataset, "AccessionNumber", "")) or None,
                )

            if series_uid not in series_by_uid:
                series = Series(
                    series_instance_uid=series_uid,
                    description=str(getattr(dataset, "SeriesDescription", "Untitled Series")),
                    modality=str(getattr(dataset, "Modality", "OT")),
                    number=_optional_int(getattr(dataset, "SeriesNumber", None)),
                    manufacturer=_optional_str(getattr(dataset, "Manufacturer", None)),
                    repetition_time=_optional_float(getattr(dataset, "RepetitionTime", None)),
                    echo_time=_optional_float(getattr(dataset, "EchoTime", None)),
                    slice_thickness=_optional_float(getattr(dataset, "SliceThickness", None)),
                    pixel_spacing=_pixel_spacing(getattr(dataset, "PixelSpacing", None)),
                    orientation=_float_tuple(getattr(dataset, "ImageOrientationPatient", [])),
                )
                series_by_uid[series_uid] = series
                studies_by_uid[study_uid].series.append(series)

            series_paths[series_uid].append(
                DicomImage(
                    sop_instance_uid=str(getattr(dataset, "SOPInstanceUID", path.name)),
                    instance_number=_optional_int(getattr(dataset, "InstanceNumber", None)) or 0,
                    path=path,
                    rows=_optional_int(getattr(dataset, "Rows", None)),
                    columns=_optional_int(getattr(dataset, "Columns", None)),
                    acquisition_date=str(getattr(dataset, "AcquisitionDate", "")) or None,
                    image_position=_float_tuple(getattr(dataset, "ImagePositionPatient", [])),
                    image_orientation=_float_tuple(getattr(dataset, "ImageOrientationPatient", [])),
                )
            )

        for series_uid, images in series_paths.items():
            series_by_uid[series_uid].images = sorted(
                images,
                key=lambda image: (
                    image.image_position[-1] if image.image_position else image.instance_number,
                    image.instance_number,
                    str(image.path),
                ),
            )

        LOGGER.info("dicom_import_complete", folder=str(folder), studies=len(studies_by_uid))
        return list(studies_by_uid.values())

    def _iter_dicom_headers(self, folder: Path) -> Iterable[tuple[Path, FileDataset]]:
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            try:
                dataset = pydicom.dcmread(path, stop_before_pixels=True, force=True)
            except Exception as exc:
                LOGGER.debug("dicom_header_skip", path=str(path), error=str(exc))
                continue

            if _is_dicom_dataset(dataset):
                yield path, dataset


class SimpleITKVolumeRepository:
    """Load DICOM series pixels into numpy volumes."""

    def load_series(self, series: Series) -> ImageVolume:
        """Load image pixels for a series using SimpleITK, with pydicom fallback."""

        paths = [str(image.path) for image in series.sorted_images()]
        if not paths:
            raise VolumeLoadError(f"Series has no images: {series.series_instance_uid}")

        try:
            reader = sitk.ImageSeriesReader()  # type: ignore[no-untyped-call]
            reader.SetFileNames(paths)  # type: ignore[no-untyped-call]
            image = reader.Execute()  # type: ignore[no-untyped-call]
            pixels = sitk.GetArrayFromImage(image).astype(np.float32)
            spacing = tuple(float(value) for value in image.GetSpacing())
            return ImageVolume(
                series_uid=series.series_instance_uid,
                pixels=pixels,
                spacing=(spacing[2], spacing[1], spacing[0]) if len(spacing) == 3 else None,
                metadata={"loader": "SimpleITK"},
            )
        except Exception as exc:
            LOGGER.warning(
                "simpleitk_volume_load_failed",
                series=series.series_instance_uid,
                error=str(exc),
            )
            return self._load_with_pydicom(series)

    def _load_with_pydicom(self, series: Series) -> ImageVolume:
        arrays: list[np.ndarray[Any, np.dtype[np.float32]]] = []
        for image in series.sorted_images():
            try:
                dataset = pydicom.dcmread(image.path)
                arrays.append(dataset.pixel_array.astype(np.float32))
            except Exception as exc:
                raise VolumeLoadError(f"Could not load DICOM pixels from {image.path}") from exc

        pixels = arrays[0] if len(arrays) == 1 else np.stack(arrays)
        spacing = None
        if series.pixel_spacing:
            z_spacing = series.slice_thickness or 1.0
            spacing = (
                float(z_spacing),
                float(series.pixel_spacing[0]),
                float(series.pixel_spacing[1]),
            )
        return ImageVolume(
            series_uid=series.series_instance_uid,
            pixels=pixels.astype(np.float32),
            spacing=spacing,
            metadata={"loader": "pydicom"},
        )


def _is_dicom_dataset(dataset: FileDataset) -> bool:
    return bool(
        getattr(dataset, "SOPInstanceUID", None)
        or getattr(dataset, "StudyInstanceUID", None)
        or getattr(dataset, "SeriesInstanceUID", None)
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    try:
        return int(str(value)) if value is not None and str(value) != "" else None
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    try:
        return float(str(value)) if value is not None and str(value) != "" else None
    except (TypeError, ValueError):
        return None


def _float_tuple(value: object) -> tuple[float, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        return ()
    values = cast(Sequence[object], value)
    try:
        return tuple(float(str(item)) for item in values)
    except (TypeError, ValueError):
        return ()


def _pixel_spacing(value: object) -> tuple[float, float] | None:
    values = _float_tuple(value)
    if len(values) >= 2:
        return (values[0], values[1])
    return None
