"""Consent-gated installer for the local MedGemma 1.5 Ollama model."""

from __future__ import annotations

from PySide6.QtCore import QThreadPool, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from medreport.ui.medgemma_setup_worker import MedGemmaInstallWorker

MEDGEMMA_MODEL_PAGE = "https://huggingface.co/google/medgemma-1.5-4b-it"


class MedGemmaSetupDialog(QDialog):
    """Download a licensed GGUF and register it with the user's Ollama installation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set up Offline MedGemma 1.5")
        self.setMinimumWidth(540)
        self._worker: MedGemmaInstallWorker | None = None

        self.status_label = QLabel(
            "Downloads MedGemma 1.5 4B and its required vision projector, then registers it "
            "as medgemma-1.5 with Ollama. No Hugging Face account or access token is needed. "
            "A local Ollama installation is required."
        )
        self.status_label.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.install_button = QPushButton("Download and Enable")
        self.install_button.clicked.connect(self._install)
        terms_button = QPushButton("Review model terms…")
        terms_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(MEDGEMMA_MODEL_PAGE)))

        form = QFormLayout()
        form.addRow("Model information", terms_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addLayout(form)
        layout.addWidget(self.progress)
        layout.addWidget(self.install_button)
        layout.addWidget(buttons)

    def start_install(self) -> None:
        """Begin setup programmatically for first-run offline defaults."""

        self._install()

    def _install(self) -> None:
        if self._worker is not None:
            return
        self.install_button.setEnabled(False)
        self.status_label.setText("Preparing MedGemma download…")
        self._worker = MedGemmaInstallWorker()
        self._worker.signals.progress.connect(self._set_progress)
        self._worker.signals.finished.connect(self._finished)
        QThreadPool.globalInstance().start(self._worker)

    def _set_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(percent)
        self.status_label.setText(message)

    def _finished(self, message: str, error: bool) -> None:
        self._worker = None
        self.install_button.setEnabled(True)
        self.status_label.setText(message)
        if error:
            QMessageBox.warning(self, "MedGemma setup", message)
