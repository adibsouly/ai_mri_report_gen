"""Main Qt window for AI MRI Analyzer."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThreadPool
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from medreport.app.services import StudyImportService, VolumeService
from medreport.database.sqlite import SQLiteDatabase
from medreport.models import ImageVolume, Series, Study
from medreport.reports.ai_report import AIReportService
from medreport.settings.service import SettingsService
from medreport.ui.ai_config_dialog import AIConfigDialog
from medreport.ui.viewer import ImageViewer
from medreport.ui.workers import (
    AIImportedStudyReportWorker,
    StudyImportWorker,
    VolumeLoadWorker,
)

SERIES_ROLE = Qt.ItemDataRole.UserRole
Worker = StudyImportWorker | VolumeLoadWorker | AIImportedStudyReportWorker


class MainWindow(QMainWindow):
    """Professional dock-based desktop workstation shell."""

    def __init__(
        self,
        study_import_service: StudyImportService,
        volume_service: VolumeService,
        settings: SettingsService,
        database: SQLiteDatabase,
        ai_report_service: AIReportService,
        report_dir: Path,
    ) -> None:
        super().__init__()
        self._study_import_service = study_import_service
        self._volume_service = volume_service
        self._settings = settings
        self._database = database
        self._ai_report_service = ai_report_service
        self._report_dir = report_dir
        self._thread_pool = QThreadPool.globalInstance()
        self._studies: list[Study] = []
        self._series_by_uid: dict[str, Series] = {}
        self._active_workers: set[Worker] = set()
        self._current_series: Series | None = None
        self._current_volume: ImageVolume | None = None
        self._last_report_path: Path | None = None

        self.viewer = ImageViewer()
        self.study_tree = QTreeWidget()
        self.metadata_table = QTableWidget(0, 2)
        self.report_editor = QTextEdit()

        self._build_window()
        self._build_actions()
        self._build_docks()

    def closeEvent(self, event: object) -> None:
        """Persist window size before closing."""

        self._settings.save_window_size(self.size())
        super().closeEvent(event)  # type: ignore[arg-type]

    def _build_window(self) -> None:
        self.setWindowTitle("AI MRI Analyzer")
        icon_path = _asset_path("icons/medreport_icon.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(self._settings.window_size(QSize(1440, 920)))
        self.setCentralWidget(self.viewer)
        self.statusBar().showMessage("Ready")

    def _build_actions(self) -> None:
        open_action = QAction("Import Folder", self)
        open_action.triggered.connect(self._choose_import_folder)

        ai_report_action = QAction("AI Report", self)
        ai_report_action.triggered.connect(self._generate_ai_report)

        save_report_action = QAction("Save Report As...", self)
        save_report_action.triggered.connect(self._save_report_as)

        ai_config_action = QAction("AI Config...", self)
        ai_config_action.triggered.connect(self._open_ai_config)

        about_me_action = QAction("About Me", self)
        about_me_action.triggered.connect(self._show_about_me)

        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        file_menu.addAction(save_report_action)

        report_menu = self.menuBar().addMenu("Report")
        report_menu.addAction(ai_report_action)
        report_menu.addAction(save_report_action)

        ai_menu = self.menuBar().addMenu("AI Config")
        ai_menu.addAction(ai_config_action)

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(about_me_action)

        toolbar = QToolBar("Workflow")
        toolbar.setMovable(False)
        for action in [open_action, ai_report_action, ai_config_action, save_report_action]:
            toolbar.addAction(action)
        self.addToolBar(toolbar)

    def _build_docks(self) -> None:
        self.study_tree.setHeaderLabels(["Study Explorer"])
        self.study_tree.itemDoubleClicked.connect(self._handle_tree_double_click)

        study_dock = QDockWidget("Study Explorer", self)
        study_dock.setWidget(self.study_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, study_dock)

        self.metadata_table.setHorizontalHeaderLabels(["Field", "Value"])
        self.metadata_table.horizontalHeader().setStretchLastSection(True)
        self.metadata_table.verticalHeader().setVisible(False)
        self.metadata_table.setAlternatingRowColors(True)

        metadata_dock = QDockWidget("Metadata", self)
        metadata_dock.setWidget(self.metadata_table)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, metadata_dock)

        self.report_editor.setPlaceholderText("AI-assisted report drafts will appear here.")
        report_dock = QDockWidget("Report", self)
        report_dock.setWidget(self.report_editor)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, report_dock)

    def _choose_import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Import DICOM Folder")
        if folder:
            self.import_folder(Path(folder))

    def import_folder(self, folder: Path) -> None:
        """Start background DICOM import."""

        self.statusBar().showMessage(f"Importing {folder}...")
        worker = StudyImportWorker(self._study_import_service, folder)
        worker.signals.finished.connect(
            lambda studies, active_worker=worker: self._handle_import_finished(
                folder,
                studies,
                active_worker,
            )
        )
        worker.signals.failed.connect(
            lambda message, active_worker=worker: self._handle_worker_error(
                message,
                active_worker,
            )
        )
        self._start_worker(worker)

    def _handle_import_finished(
        self,
        folder: Path,
        studies: object,
        worker: Worker,
    ) -> None:
        self._release_worker(worker)
        if not isinstance(studies, list):
            self._show_error("DICOM import returned an unexpected result.")
            return
        self._studies = studies
        self._series_by_uid = {
            series.series_instance_uid: series
            for study in self._studies
            for series in study.series
        }
        self._current_series = None
        self._current_volume = None
        self._settings.add_recent_folder(folder)
        self._database.add_recent_study(folder)
        self._populate_study_tree(self._studies)
        mri_count = self._mri_series_count()
        self.statusBar().showMessage(
            f"Imported {len(studies)} study/studies from {folder}. "
            f"AI Report will use {mri_count} MRI series."
        )

    def _populate_study_tree(self, studies: list[Study]) -> None:
        self.study_tree.clear()
        for study in studies:
            study_item = QTreeWidgetItem(
                [
                    f"{study.patient.name} - {study.description}",
                ]
            )
            for series in study.series:
                series_item = QTreeWidgetItem(
                    [
                        f"{series.modality} {series.number or ''} - "
                        f"{series.description} ({len(series.images)} images)"
                    ]
                )
                series_item.setData(0, SERIES_ROLE, series.series_instance_uid)
                study_item.addChild(series_item)
                for image in series.images[:50]:
                    image_item = QTreeWidgetItem([f"Image {image.instance_number}"])
                    series_item.addChild(image_item)
            self.study_tree.addTopLevelItem(study_item)
        self.study_tree.expandToDepth(1)

    def _handle_tree_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, SERIES_ROLE)
        if isinstance(data, str) and data in self._series_by_uid:
            self._load_series(self._series_by_uid[data])

    def _load_series(self, series: Series) -> None:
        self.statusBar().showMessage(f"Loading {series.description}...")
        self._populate_metadata(series)
        worker = VolumeLoadWorker(self._volume_service, series)
        worker.signals.finished.connect(
            lambda loaded_series, volume, active_worker=worker: self._handle_volume_loaded(
                loaded_series,
                volume,
                active_worker,
            )
        )
        worker.signals.failed.connect(
            lambda message, active_worker=worker: self._handle_worker_error(
                message,
                active_worker,
            )
        )
        self._start_worker(worker)

    def _handle_volume_loaded(
        self,
        series: Series,
        volume: ImageVolume,
        worker: Worker,
    ) -> None:
        self._release_worker(worker)
        self._current_series = series
        self._current_volume = volume
        self.viewer.set_volume(volume)
        self.statusBar().showMessage(
            f"Loaded {series.description}: {volume.slice_count} slice(s), spacing {volume.spacing}"
        )

    def _generate_ai_report(self) -> None:
        if not self._studies:
            QMessageBox.information(
                self,
                "AI MRI Analyzer",
                "Import a DICOM MRI folder before generating a report.",
            )
            return
        if not self._ai_report_service.is_configured():
            QMessageBox.information(
                self,
                "AI MRI Analyzer",
                self._ai_report_service.configuration_hint(),
            )
            return

        if self._mri_series_count() == 0:
            QMessageBox.information(
                self,
                "AI MRI Analyzer",
                "No MRI series were found in the imported DICOM studies.",
            )
            return

        worker = AIImportedStudyReportWorker(
            volume_service=self._volume_service,
            report_service=self._ai_report_service,
            studies=self._studies,
        )

        worker.signals.finished.connect(self._handle_ai_report_finished)
        worker.signals.finished.connect(
            lambda _report, active_worker=worker: self._release_worker(active_worker)
        )
        worker.signals.failed.connect(
            lambda message, active_worker=worker: self._handle_worker_error(
                message,
                active_worker,
            )
        )
        self.statusBar().showMessage(
            "Loading all imported MRI series and generating AI-assisted report..."
        )
        self._start_worker(worker)

    def _handle_ai_report_finished(self, report: str) -> None:
        report_path = self._save_report(report)
        self._last_report_path = report_path
        self.report_editor.setPlainText(report)
        self.statusBar().showMessage(
            f"AI-assisted report saved to {report_path.name}. Radiologist review required."
        )

    def _save_report_as(self) -> None:
        report = self.report_editor.toPlainText().strip()
        if not report:
            QMessageBox.information(
                self,
                "AI MRI Analyzer",
                "No report is available to save yet.",
            )
            return

        suggested = self._last_report_path or self._report_dir / "ai-report.md"
        path_text, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save AI Report",
            str(suggested),
            "Markdown (*.md);;Text (*.txt)",
        )
        if not path_text:
            return

        report_path = Path(path_text)
        report_path.write_text(report, encoding="utf-8")
        self._last_report_path = report_path
        self.statusBar().showMessage(f"Report saved to {report_path}")

    def _open_ai_config(self) -> None:
        dialog = AIConfigDialog(self._ai_report_service.config, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        config = dialog.config()
        self._settings.save_ai_provider_config(config)
        self._ai_report_service.update_config(config)
        self.statusBar().showMessage(f"AI provider set to {config.label}: {config.model}")

    def _show_about_me(self) -> None:
        QMessageBox.about(
            self,
            "About AI MRI Analyzer",
            (
                "<b>AI MRI Analyzer</b><br><br>"
                "Created by Adib Souly, the main developer of this app.<br><br>"
                "I built AI MRI Analyzer to help patients explore their MRI studies, "
                "ask better questions, and understand AI-assisted analysis in a more "
                "accessible way.<br><br>"
                "<b>Important:</b> This app is not medical-grade software and is not "
                "intended for diagnosis, treatment decisions, emergency use, or replacing "
                "a licensed radiologist or physician. All findings must be reviewed by a "
                "qualified medical professional."
            ),
        )

    def _populate_metadata(self, series: Series) -> None:
        rows = series.images[0].rows if series.images else None
        columns = series.images[0].columns if series.images else None
        acquisition_date = series.images[0].acquisition_date if series.images else None
        fields = [
            ("Series", series.description),
            ("Manufacturer", series.manufacturer),
            ("TR", series.repetition_time),
            ("TE", series.echo_time),
            ("Slice Thickness", series.slice_thickness),
            ("Pixel Size", series.pixel_spacing),
            ("Orientation", series.orientation),
            ("Modality", series.modality),
            ("Rows", rows),
            ("Columns", columns),
            ("Acquisition Date", acquisition_date),
            ("Images", len(series.images)),
        ]
        self.metadata_table.setRowCount(len(fields))
        for row, (field, value) in enumerate(fields):
            self.metadata_table.setItem(row, 0, QTableWidgetItem(field))
            self.metadata_table.setItem(
                row,
                1,
                QTableWidgetItem("" if value is None else str(value)),
            )

    def _show_error(self, message: str) -> None:
        self.statusBar().showMessage("Error")
        QMessageBox.critical(self, "AI MRI Analyzer", message)

    def _start_worker(self, worker: Worker) -> None:
        self._active_workers.add(worker)
        self._thread_pool.start(worker)

    def _release_worker(self, worker: Worker) -> None:
        self._active_workers.discard(worker)

    def _handle_worker_error(self, message: str, worker: Worker) -> None:
        self._release_worker(worker)
        self._show_error(message)

    def _save_report(self, report: str) -> Path:
        self._report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        patient_part = self._safe_filename_part(self._patient_label())
        report_path = self._report_dir / f"{timestamp}-{patient_part}-ai-report.md"
        report_path.write_text(report, encoding="utf-8")
        return report_path

    def _patient_label(self) -> str:
        if not self._studies:
            return "study"
        patient = self._studies[0].patient
        return patient.patient_id or patient.name or "study"

    @staticmethod
    def _safe_filename_part(value: str) -> str:
        normalized = "".join(character if character.isalnum() else "-" for character in value)
        cleaned = "-".join(part for part in normalized.split("-") if part)
        return cleaned[:48] or "study"

    def _mri_series_count(self) -> int:
        return sum(
            1
            for study in self._studies
            for series in study.series
            if series.modality.upper() in {"MR", "MRI"}
        )


def empty_widget() -> QWidget:
    """Return an empty QWidget for tests or layout placeholders."""

    return QWidget()


def _asset_path(relative_path: str) -> Path:
    """Resolve an asset path from source or a PyInstaller bundle."""

    bundle_root = getattr(sys, "_MEIPASS", None)
    if isinstance(bundle_root, str):
        return Path(bundle_root) / "assets" / relative_path
    return Path(__file__).resolve().parents[3] / "assets" / relative_path
