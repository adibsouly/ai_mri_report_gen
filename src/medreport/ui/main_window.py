"""Main Qt window for DecodeMRI."""

from __future__ import annotations

import platform
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from medreport.app.services import StudyImportService, VolumeService
from medreport.database.sqlite import SQLiteDatabase
from medreport.models import ImageVolume, Series, Study
from medreport.reports.ai_report import (
    PROVIDER_DEFAULTS,
    AIProvider,
    AIProviderConfig,
    AIReportService,
)
from medreport.reports.pdf import save_markdown_pdf
from medreport.settings.service import SettingsService
from medreport.ui.ai_config_dialog import AIConfigDialog
from medreport.ui.medgemma_setup_dialog import MedGemmaSetupDialog
from medreport.ui.theme import DARK_THEME, LIGHT_THEME
from medreport.ui.viewer import ImageViewer
from medreport.ui.welcome_dialog import WelcomeDialog
from medreport.ui.workers import (
    AIChatWorker,
    AIImportedStudyReportWorker,
    StudyImportWorker,
    VolumeLoadWorker,
)

SERIES_ROLE = Qt.ItemDataRole.UserRole
IMAGE_INDEX_ROLE = Qt.ItemDataRole.UserRole + 1
Worker = StudyImportWorker | VolumeLoadWorker | AIImportedStudyReportWorker | AIChatWorker


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
        self._pending_slice_index: int | None = None
        self._last_report_path: Path | None = None
        self._chat_conversation: list[tuple[str, str]] = []
        self._pending_chat_question = ""
        self._ai_busy = False
        self._current_ai_worker: AIImportedStudyReportWorker | AIChatWorker | None = None
        self._offline_setup_dialog: MedGemmaSetupDialog | None = None

        self.viewer = ImageViewer()
        self.study_tree = QTreeWidget()
        self.metadata_table = QTableWidget(0, 2)
        self.report_editor = QTextEdit()
        self.analysis_label = QLabel("AI analysis in progress…")
        self.analysis_detail_label = QLabel()
        self.analysis_progress = QProgressBar()
        self.stop_analysis_button = QPushButton("Stop Analysis")
        self.chat_transcript = QTextEdit()
        self.chat_input = QLineEdit()
        self.chat_send_button = QPushButton("Ask AI")

        self._build_window()
        self._build_actions()
        self._build_docks()
        QTimer.singleShot(0, self._show_first_run_welcome)

    def closeEvent(self, event: object) -> None:
        """Persist window size before closing."""

        self._settings.save_window_size(self.size())
        super().closeEvent(event)  # type: ignore[arg-type]

    def _build_window(self) -> None:
        self.setWindowTitle("DecodeMRI")
        icon_path = _asset_path("icons/decodemri_icon.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(self._settings.window_size(QSize(1440, 920)))
        self.setCentralWidget(self.viewer)
        self.statusBar().showMessage("Ready")

    def _build_actions(self) -> None:
        open_action = QAction("Import MRI", self)
        open_action.triggered.connect(self._choose_import_folder)

        self.ai_report_action = QAction("Decode MRI", self)
        self.ai_report_action.triggered.connect(self._generate_ai_report)

        save_report_action = QAction("Save Report As...", self)
        save_report_action.triggered.connect(self._save_report_as)

        ai_config_action = QAction("Config AI...", self)
        ai_config_action.triggered.connect(self._open_ai_config)

        about_me_action = QAction("About Me", self)
        about_me_action.triggered.connect(self._show_about_me)

        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        self.light_theme_action = QAction("Light Theme", self, checkable=True)
        self.dark_theme_action = QAction("Dark Theme", self, checkable=True)
        theme_group.addAction(self.light_theme_action)
        theme_group.addAction(self.dark_theme_action)
        self.light_theme_action.triggered.connect(lambda: self._apply_theme("light"))
        self.dark_theme_action.triggered.connect(lambda: self._apply_theme("dark"))
        selected_theme = self._settings.theme()
        self.light_theme_action.setChecked(selected_theme == "light")
        self.dark_theme_action.setChecked(selected_theme == "dark")

        previous_slice_action = QAction(_app_icon("go-previous"), "Previous Image", self)
        previous_slice_action.triggered.connect(self._previous_slice)

        next_slice_action = QAction(_app_icon("go-next"), "Next Image", self)
        next_slice_action.triggered.connect(self._next_slice)

        zoom_in_action = QAction(_app_icon("zoom-in"), "Zoom In", self)
        zoom_in_action.triggered.connect(self.viewer.zoom_in)

        zoom_out_action = QAction(_app_icon("zoom-out"), "Zoom Out", self)
        zoom_out_action.triggered.connect(self.viewer.zoom_out)

        fit_action = QAction(_app_icon("zoom-fit-best"), "Fit", self)
        fit_action.triggered.connect(self.viewer.fit_to_window)

        export_jpeg_action = QAction(_asset_icon("icons/export_jpeg_icon.png"), "Export JPEG", self)
        export_jpeg_action.triggered.connect(self._export_viewer_jpeg)

        export_pdf_action = QAction(_asset_icon("icons/export_pdf_icon.png"), "Export PDF", self)
        export_pdf_action.triggered.connect(self._export_viewer_pdf)

        action_descriptions = {
            open_action: "Import a folder containing DICOM MRI images.",
            self.ai_report_action: "Analyze the imported MRI study and generate a report draft.",
            save_report_action: "Save the current report draft to a file.",
            ai_config_action: "Choose and configure the AI service provider and model.",
            about_me_action: "Show information and safety guidance about this app.",
            self.light_theme_action: "Use the light appearance for the app.",
            self.dark_theme_action: "Use the dark appearance for the app.",
            previous_slice_action: "Show the previous MRI image in the current series.",
            next_slice_action: "Show the next MRI image in the current series.",
            zoom_in_action: "Zoom in on the displayed MRI image.",
            zoom_out_action: "Zoom out from the displayed MRI image.",
            fit_action: "Fit the MRI image to the available viewer area.",
            export_jpeg_action: "Export the displayed MRI image as a JPEG file.",
            export_pdf_action: "Export the displayed MRI image as a PDF file.",
        }
        for action, description in action_descriptions.items():
            action.setToolTip(description)
            action.setStatusTip(description)

        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        file_menu.addAction(save_report_action)
        file_menu.addSeparator()
        file_menu.addAction(export_jpeg_action)
        file_menu.addAction(export_pdf_action)

        report_menu = self.menuBar().addMenu("Report")
        report_menu.addAction(self.ai_report_action)
        report_menu.addAction(save_report_action)

        ai_menu = self.menuBar().addMenu("Config AI")
        ai_menu.addAction(ai_config_action)

        customize_menu = self.menuBar().addMenu("Customize")
        customize_menu.addAction(self.light_theme_action)
        customize_menu.addAction(self.dark_theme_action)

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(about_me_action)

        toolbar = QToolBar("Workflow")
        toolbar.setMovable(False)
        for action in [open_action, self.ai_report_action, ai_config_action, save_report_action]:
            toolbar.addAction(action)
        self.addToolBar(toolbar)

        viewer_toolbar = QToolBar("Image Viewer")
        viewer_toolbar.setMovable(False)
        viewer_toolbar.setIconSize(QSize(20, 20))
        for action in [
            previous_slice_action,
            next_slice_action,
            zoom_in_action,
            zoom_out_action,
            fit_action,
            export_jpeg_action,
            export_pdf_action,
        ]:
            viewer_toolbar.addAction(action)
        self.addToolBar(viewer_toolbar)

    def _show_first_run_welcome(self) -> None:
        """Show first-run guidance and default compatible Macs to offline AI."""

        if self._settings.has_completed_welcome():
            return
        use_offline_default = (
            _has_apple_silicon_gpu() and not self._settings.has_ai_provider_config()
        )
        WelcomeDialog(offline_setup_available=use_offline_default, parent=self).exec()
        self._settings.mark_welcome_completed()
        if not use_offline_default:
            return
        defaults = PROVIDER_DEFAULTS[AIProvider.MEDGEMMA]
        config = AIProviderConfig(
            provider=AIProvider.MEDGEMMA,
            model=defaults.model,
            base_url=defaults.base_url,
            api_key=defaults.api_key,
        )
        self._settings.save_ai_provider_config(config)
        self._ai_report_service.update_config(config)
        self.statusBar().showMessage("Offline MedGemma selected. Downloading the local model…")
        self._offline_setup_dialog = MedGemmaSetupDialog(self)
        self._offline_setup_dialog.show()
        self._offline_setup_dialog.start_install()

    def _build_docks(self) -> None:
        self.study_tree.setHeaderLabels(["Study Explorer"])
        self.study_tree.itemClicked.connect(self._handle_tree_click)
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
        self.analysis_label.setVisible(False)
        self.analysis_detail_label.setWordWrap(True)
        self.analysis_detail_label.setVisible(False)
        self.analysis_progress.setRange(0, 0)
        self.analysis_progress.setTextVisible(False)
        self.analysis_progress.setVisible(False)
        self.stop_analysis_button.setVisible(False)
        self.stop_analysis_button.setToolTip(
            "Stop the current analysis and signal the AI provider to cancel its request."
        )
        self.stop_analysis_button.clicked.connect(self._stop_ai_operation)

        self.chat_transcript.setReadOnly(True)
        self.chat_transcript.setPlaceholderText(
            "After generating a report, ask the AI to explain findings or medical terms."
        )
        self.chat_input.setPlaceholderText("Ask a question about this report…")
        self.chat_input.setEnabled(False)
        self.chat_send_button.setEnabled(False)
        self.chat_send_button.setToolTip(
            "Ask the selected AI provider a question grounded in the generated report."
        )
        self.chat_input.returnPressed.connect(self._send_chat_question)
        self.chat_send_button.clicked.connect(self._send_chat_question)

        chat_input_layout = QHBoxLayout()
        chat_input_layout.addWidget(self.chat_input)
        chat_input_layout.addWidget(self.chat_send_button)

        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.addWidget(QLabel("Chat with this AI report"))
        chat_layout.addWidget(self.chat_transcript)
        chat_layout.addLayout(chat_input_layout)

        report_splitter = QSplitter(Qt.Orientation.Horizontal)
        report_splitter.addWidget(self.report_editor)
        report_splitter.addWidget(chat_widget)
        report_splitter.setSizes([760, 520])

        report_widget = QWidget()
        report_layout = QVBoxLayout(report_widget)
        report_layout.setContentsMargins(6, 6, 6, 6)
        progress_header = QHBoxLayout()
        progress_header.addWidget(self.analysis_label, 1)
        progress_header.addWidget(self.stop_analysis_button)
        report_layout.addLayout(progress_header)
        report_layout.addWidget(self.analysis_detail_label)
        report_layout.addWidget(self.analysis_progress)
        report_layout.addWidget(report_splitter)

        report_dock = QDockWidget("Report", self)
        report_dock.setWidget(report_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, report_dock)

    def _choose_import_folder(self) -> None:
        last_folder = self._settings.last_import_folder()
        folder = QFileDialog.getExistingDirectory(
            self,
            "Import DICOM Folder",
            str(last_folder) if last_folder is not None else "",
        )
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
                for image_index, image in enumerate(series.sorted_images()):
                    image_item = QTreeWidgetItem([f"Image {image.instance_number}"])
                    image_item.setData(0, SERIES_ROLE, series.series_instance_uid)
                    image_item.setData(0, IMAGE_INDEX_ROLE, image_index)
                    series_item.addChild(image_item)
            self.study_tree.addTopLevelItem(study_item)
        self.study_tree.expandToDepth(1)

    def _handle_tree_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, SERIES_ROLE)
        if isinstance(data, str) and data in self._series_by_uid:
            image_index = item.data(0, IMAGE_INDEX_ROLE)
            initial_slice = image_index if isinstance(image_index, int) else None
            self._load_series(self._series_by_uid[data], initial_slice=initial_slice)

    def _handle_tree_click(self, item: QTreeWidgetItem, _column: int) -> None:
        image_index = item.data(0, IMAGE_INDEX_ROLE)
        series_uid = item.data(0, SERIES_ROLE)
        if not isinstance(series_uid, str) or not isinstance(image_index, int):
            return
        series = self._series_by_uid.get(series_uid)
        if series is None:
            return
        if self._current_series and self._current_series.series_instance_uid == series_uid:
            self.viewer.set_slice_index(image_index)
            self.statusBar().showMessage(f"Showing image {image_index + 1}")
            return
        self._load_series(series, initial_slice=image_index)

    def _load_series(self, series: Series, initial_slice: int | None = None) -> None:
        self.statusBar().showMessage(f"Loading {series.description}...")
        self._populate_metadata(series)
        self._pending_slice_index = initial_slice
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
        if self._pending_slice_index is not None:
            self.viewer.set_slice_index(self._pending_slice_index)
            self._pending_slice_index = None
        self.statusBar().showMessage(
            f"Loaded {series.description}: image {self.viewer.slice_index + 1} of "
            f"{volume.slice_count}, spacing {volume.spacing}"
        )

    def _generate_ai_report(self) -> None:
        if not self._studies:
            QMessageBox.information(
                self,
                "DecodeMRI",
                "Import a DICOM MRI folder before generating a report.",
            )
            return
        if not self._ai_report_service.is_configured():
            QMessageBox.information(
                self,
                "DecodeMRI",
                self._ai_report_service.configuration_hint(),
            )
            return

        if self._mri_series_count() == 0:
            QMessageBox.information(
                self,
                "DecodeMRI",
                "No MRI series were found in the imported DICOM studies.",
            )
            return

        clinical_context, _ = QInputDialog.getMultiLineText(
            self,
            "Clinical Context (Optional)",
            (
                "Add any helpful educational-analysis context: pain location, "
                "injury mechanism, when symptoms began, prior injury or surgery, and relevant "
                "history. This is optional: leave it blank or choose Cancel to continue without "
                "context. Do not include identifying information."
            ),
        )

        worker = AIImportedStudyReportWorker(
            volume_service=self._volume_service,
            report_service=self._ai_report_service,
            studies=self._studies,
            clinical_context=clinical_context,
        )

        worker.signals.finished.connect(
            lambda report, active_worker=worker: self._handle_ai_report_finished(
                report,
                active_worker,
            )
        )
        worker.signals.failed.connect(
            lambda message, active_worker=worker: self._handle_ai_operation_error(
                message,
                active_worker,
            )
        )
        self.statusBar().showMessage(
            "Loading all imported MRI series and generating AI-assisted report..."
        )
        self._current_ai_worker = worker
        self._set_ai_busy(
            True,
            "Analyzing MRI images and generating the report…",
            (
                f"Loading and reviewing {self._mri_series_count()} MRI series with "
                f"{self._ai_report_service.config.label} ({self._ai_report_service.config.model}). "
                "The time required depends on the speed of the AI service provider and model."
            ),
        )
        self._start_worker(worker)

    def _handle_ai_report_finished(
        self,
        report: str,
        worker: AIImportedStudyReportWorker,
    ) -> None:
        if worker is not self._current_ai_worker:
            self._release_worker(worker)
            return
        self._release_worker(worker)
        self._current_ai_worker = None
        self._set_ai_busy(False)
        report_path = self._save_report(report)
        self._last_report_path = report_path
        self.report_editor.setMarkdown(report)
        self._chat_conversation.clear()
        self.chat_transcript.clear()
        self._update_chat_controls()
        self.statusBar().showMessage(
            f"Detailed MRI analysis saved to {report_path.name}."
        )

    def _send_chat_question(self) -> None:
        if self._ai_busy:
            return
        report = self.report_editor.toPlainText().strip()
        question = self.chat_input.text().strip()
        if not report:
            QMessageBox.information(
                self,
                "DecodeMRI",
                "Generate an AI report before starting a chat.",
            )
            return
        if not question:
            return
        if not self._ai_report_service.is_configured():
            QMessageBox.information(
                self,
                "DecodeMRI",
                self._ai_report_service.configuration_hint(),
            )
            return

        self._pending_chat_question = question
        self.chat_input.clear()
        self._render_chat_transcript(pending_question=question)
        worker = AIChatWorker(
            service=self._ai_report_service,
            report=report,
            question=question,
            conversation=list(self._chat_conversation),
        )
        worker.signals.finished.connect(
            lambda answer, active_worker=worker: self._handle_chat_finished(
                answer,
                active_worker,
            )
        )
        worker.signals.failed.connect(
            lambda message, active_worker=worker: self._handle_ai_operation_error(
                message,
                active_worker,
            )
        )
        self._current_ai_worker = worker
        self._set_ai_busy(
            True,
            "AI is reviewing the report and preparing an answer…",
            (
                f"Sending your report-grounded question to {self._ai_report_service.config.label} "
                f"({self._ai_report_service.config.model}). The time required depends on the "
                "speed of the AI service provider and model."
            ),
        )
        self.statusBar().showMessage("Answering your question about the AI report...")
        self._start_worker(worker)

    def _handle_chat_finished(self, answer: str, worker: AIChatWorker) -> None:
        if worker is not self._current_ai_worker:
            self._release_worker(worker)
            return
        self._release_worker(worker)
        self._current_ai_worker = None
        question = self._pending_chat_question
        self._pending_chat_question = ""
        self._chat_conversation.append((question, answer))
        self._render_chat_transcript()
        self._set_ai_busy(False)
        self.statusBar().showMessage(
            "Detailed MRI analysis response ready."
        )

    def _render_chat_transcript(self, pending_question: str = "") -> None:
        messages: list[str] = []
        for question, answer in self._chat_conversation:
            messages.extend([f"You\n{question}", f"AI\n{answer}"])
        if pending_question:
            messages.extend([f"You\n{pending_question}", "AI\nAnalyzing…"])
        self.chat_transcript.setPlainText("\n\n".join(messages))
        scroll_bar = self.chat_transcript.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def _set_ai_busy(self, busy: bool, message: str = "", detail: str = "") -> None:
        self._ai_busy = busy
        self.analysis_label.setText(message or "AI analysis in progress…")
        self.analysis_detail_label.setText(detail)
        self.analysis_label.setVisible(busy)
        self.analysis_detail_label.setVisible(busy)
        self.analysis_progress.setVisible(busy)
        self.stop_analysis_button.setVisible(busy)
        self.ai_report_action.setEnabled(not busy)
        self._update_chat_controls()

    def _stop_ai_operation(self) -> None:
        worker = self._current_ai_worker
        if worker is None:
            return
        worker.cancel()
        self._release_worker(worker)
        self._current_ai_worker = None
        self._pending_chat_question = ""
        self._render_chat_transcript()
        self._set_ai_busy(False)
        self.statusBar().showMessage(
            "AI analysis stopped. A cancellation signal was sent to the AI service provider."
        )

    def _apply_theme(self, theme: str) -> None:
        application = QApplication.instance()
        if isinstance(application, QApplication):
            application.setStyleSheet(DARK_THEME if theme == "dark" else LIGHT_THEME)
        self._settings.save_theme(theme)
        self.light_theme_action.setChecked(theme == "light")
        self.dark_theme_action.setChecked(theme == "dark")
        self.statusBar().showMessage(f"{theme.title()} theme applied.")

    def _update_chat_controls(self) -> None:
        can_chat = bool(self.report_editor.toPlainText().strip()) and not self._ai_busy
        self.chat_input.setEnabled(can_chat)
        self.chat_send_button.setEnabled(can_chat)

    def _save_report_as(self) -> None:
        report = self._report_markdown()
        if not report:
            QMessageBox.information(
                self,
                "DecodeMRI",
                "No report is available to save yet.",
            )
            return

        suggested = self._last_report_path or self._report_dir / "ai-report.pdf"
        path_text, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save AI Report",
            str(suggested),
            "PDF Document (*.pdf);;Markdown (*.md);;Text (*.txt)",
        )
        if not path_text:
            return

        report_path = Path(path_text)
        if "*.pdf" in selected_filter:
            report_path = report_path.with_suffix(".pdf")
            try:
                save_markdown_pdf(report, report_path)
            except OSError as error:
                self._show_error(f"Could not save the PDF report: {error}")
                return
        else:
            suffix = ".md" if "*.md" in selected_filter else ".txt"
            report_path = report_path.with_suffix(suffix)
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

    def _previous_slice(self) -> None:
        self.viewer.previous_slice()
        self._show_slice_status()

    def _next_slice(self) -> None:
        self.viewer.next_slice()
        self._show_slice_status()

    def _show_slice_status(self) -> None:
        if self._current_volume is None:
            return
        self.statusBar().showMessage(
            f"Showing image {self.viewer.slice_index + 1} of {self._current_volume.slice_count}"
        )

    def _export_viewer_jpeg(self) -> None:
        self._export_viewer_image("JPEG Image", "JPEG Images (*.jpg *.jpeg)", "jpg")

    def _export_viewer_pdf(self) -> None:
        self._export_viewer_image("PDF Document", "PDF Documents (*.pdf)", "pdf")

    def _export_viewer_image(self, label: str, file_filter: str, suffix: str) -> None:
        if not self.viewer.has_image:
            QMessageBox.information(
                self,
                "DecodeMRI",
                "Load an image before exporting.",
            )
            return
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        suggested = self._report_dir / f"mri-image-{timestamp}.{suffix}"
        path_text, _selected_filter = QFileDialog.getSaveFileName(
            self,
            f"Export {label}",
            str(suggested),
            file_filter,
        )
        if not path_text:
            return
        export_path = Path(path_text)
        if export_path.suffix.lower() != f".{suffix}":
            export_path = export_path.with_suffix(f".{suffix}")
        exported = (
            self.viewer.export_pdf(export_path)
            if suffix == "pdf"
            else self.viewer.export_jpeg(export_path)
        )
        if not exported:
            self._show_error(f"Could not export {label}.")
            return
        self.statusBar().showMessage(f"Exported {label} to {export_path}")

    def _show_about_me(self) -> None:
        QMessageBox.about(
            self,
            "About DecodeMRI",
            (
                "<b>DecodeMRI</b><br><br>"
                "Created by Adib Souly, the main developer of this app.<br><br>"
                "I built DecodeMRI to help patients explore their MRI studies, "
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
        QMessageBox.critical(self, "DecodeMRI", message)

    def _start_worker(self, worker: Worker) -> None:
        self._active_workers.add(worker)
        self._thread_pool.start(worker)

    def _release_worker(self, worker: Worker) -> None:
        self._active_workers.discard(worker)

    def _handle_worker_error(self, message: str, worker: Worker) -> None:
        self._release_worker(worker)
        self._show_error(message)

    def _handle_ai_operation_error(self, message: str, worker: Worker) -> None:
        self._release_worker(worker)
        if worker is not self._current_ai_worker:
            return
        self._current_ai_worker = None
        self._pending_chat_question = ""
        self._render_chat_transcript()
        self._set_ai_busy(False)
        self._show_error(message)

    def _save_report(self, report: str) -> Path:
        self._report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        patient_part = self._safe_filename_part(self._patient_label())
        report_path = self._report_dir / f"{timestamp}-{patient_part}-ai-report.md"
        report_path.write_text(report, encoding="utf-8")
        return report_path

    def _report_markdown(self) -> str:
        """Return the formatted report editor contents as Markdown."""

        return self.report_editor.toMarkdown().strip()

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


def _has_apple_silicon_gpu() -> bool:
    """Return whether this macOS host has the integrated Apple Silicon GPU path."""

    return sys.platform == "darwin" and platform.machine().lower() in {"arm64", "aarch64"}


def _asset_path(relative_path: str) -> Path:
    """Resolve an asset path from source or a PyInstaller bundle."""

    bundle_root = getattr(sys, "_MEIPASS", None)
    if isinstance(bundle_root, str):
        return Path(bundle_root) / "assets" / relative_path
    return Path(__file__).resolve().parents[3] / "assets" / relative_path


def _app_icon(theme_name: str) -> QIcon:
    """Return a themed icon with a Qt standard fallback."""

    icon = QIcon.fromTheme(theme_name)
    if not icon.isNull():
        return icon

    style = QApplication.style()
    fallback_icons = {
        "go-previous": QStyle.StandardPixmap.SP_ArrowBack,
        "go-next": QStyle.StandardPixmap.SP_ArrowForward,
        "zoom-in": QStyle.StandardPixmap.SP_TitleBarMaxButton,
        "zoom-out": QStyle.StandardPixmap.SP_TitleBarMinButton,
        "zoom-fit-best": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    }
    fallback = fallback_icons.get(theme_name, QStyle.StandardPixmap.SP_FileIcon)
    return style.standardIcon(fallback)


def _asset_icon(relative_path: str) -> QIcon:
    """Return a small icon from bundled assets."""

    icon_path = _asset_path(relative_path)
    if icon_path.exists():
        return QIcon(str(icon_path))
    return _app_icon("fallback")
