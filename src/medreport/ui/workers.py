"""Qt workers for background imports and volume loading."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from medreport.app.services import StudyImportService, VolumeService
from medreport.models import ImageVolume, Series, Study
from medreport.reports.ai_report import (
    AIReportRequest,
    AIReportService,
    AIStudyReportRequest,
    SeriesVolume,
)


class StudyImportSignals(QObject):
    """Signals emitted by DICOM import workers."""

    finished = Signal(object)
    failed = Signal(str)


class StudyImportWorker(QRunnable):
    """Run a study import use case on the global thread pool."""

    def __init__(self, service: StudyImportService, folder: Path) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.signals = StudyImportSignals()
        self._service = service
        self._folder = folder

    @Slot()
    def run(self) -> None:
        """Execute the import and emit a result."""

        try:
            studies: list[Study] = self._service.import_folder(self._folder)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
            return
        self.signals.finished.emit(studies)


class VolumeLoadSignals(QObject):
    """Signals emitted by volume loading workers."""

    finished = Signal(object, object)
    failed = Signal(str)


class VolumeLoadWorker(QRunnable):
    """Load series pixels on a background thread."""

    def __init__(self, service: VolumeService, series: Series) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.signals = VolumeLoadSignals()
        self._service = service
        self._series = series

    @Slot()
    def run(self) -> None:
        """Execute loading and emit the selected series with its volume."""

        try:
            volume: ImageVolume = self._service.load_series(self._series)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
            return
        self.signals.finished.emit(self._series, volume)


class AIReportSignals(QObject):
    """Signals emitted by AI report workers."""

    finished = Signal(str)
    failed = Signal(str)


class AIReportWorker(QRunnable):
    """Generate a report draft on a background thread."""

    def __init__(self, service: AIReportService, request: AIReportRequest) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.signals = AIReportSignals()
        self._service = service
        self._request = request

    @Slot()
    def run(self) -> None:
        """Execute report generation and emit the generated Markdown."""

        try:
            report = self._service.generate_mri_report(self._request)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
            return
        self.signals.finished.emit(report)


class AIChatWorker(QRunnable):
    """Answer a report follow-up question without blocking the UI thread."""

    def __init__(
        self,
        service: AIReportService,
        report: str,
        question: str,
        conversation: list[tuple[str, str]],
    ) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.signals = AIReportSignals()
        self._service = service
        self._report = report
        self._question = question
        self._conversation = conversation
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        """Request cancellation from both the worker and AI provider."""

        self._cancelled.set()
        self._service.cancel_active_request()

    @Slot()
    def run(self) -> None:
        """Generate and emit a report-grounded answer."""

        try:
            answer = self._service.chat_about_report(
                report=self._report,
                question=self._question,
                conversation=self._conversation,
            )
        except Exception as exc:
            if not self._cancelled.is_set():
                self.signals.failed.emit(str(exc))
            return
        if not self._cancelled.is_set():
            self.signals.finished.emit(answer)


class AIImportedStudyReportWorker(QRunnable):
    """Load imported MRI series and generate one report draft."""

    def __init__(
        self,
        volume_service: VolumeService,
        report_service: AIReportService,
        studies: list[Study],
        clinical_context: str = "",
    ) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.signals = AIReportSignals()
        self._volume_service = volume_service
        self._report_service = report_service
        self._studies = studies
        self._clinical_context = clinical_context
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        """Request cancellation from both the worker and AI provider."""

        self._cancelled.set()
        self._report_service.cancel_active_request()

    @Slot()
    def run(self) -> None:
        """Load MRI volumes and emit a study-level report."""

        try:
            series_volumes: list[SeriesVolume] = []
            for series in _mri_series(self._studies):
                if self._cancelled.is_set():
                    return
                series_volumes.append(
                    SeriesVolume(
                        series=series,
                        volume=self._volume_service.load_series(series),
                    )
                )
            if self._cancelled.is_set():
                return
            report = self._report_service.generate_study_mri_report(
                AIStudyReportRequest(
                    series_volumes=series_volumes,
                    clinical_context=self._clinical_context,
                )
            )
        except Exception as exc:
            if not self._cancelled.is_set():
                self.signals.failed.emit(str(exc))
            return
        if not self._cancelled.is_set():
            self.signals.finished.emit(report)


def _mri_series(studies: list[Study]) -> list[Series]:
    return [
        series
        for study in studies
        for series in study.series
        if series.modality.upper() in {"MR", "MRI"}
    ]
