"""One-time DecodeMRI welcome guide."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget


class WelcomeDialog(QDialog):
    """Introduce first-time users to the DecodeMRI workflow."""

    def __init__(self, offline_setup_available: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to DecodeMRI")
        self.setMinimumWidth(590)
        offline_note = (
            "This Apple Silicon Mac supports local AI. DecodeMRI will select MedGemma 1.5 "
            "as the default and begin its offline setup after this guide. Ollama must be "
            "installed; you can change the provider at any time in Config AI."
            if offline_setup_available
            else "Choose a provider at any time in Config AI. Local MedGemma setup is offered "
            "on compatible Apple Silicon Macs."
        )
        guide = QLabel(
            "<h2>Welcome to DecodeMRI</h2>"
            "<p>DecodeMRI is an educational MRI-learning workspace that helps you explore "
            "studies and generate detailed, structured image analysis.</p>"
            "<h3>How it works</h3>"
            "<ol>"
            "<li>Select <b>Import MRI</b> and choose a folder containing DICOM MRI files.</li>"
            "<li>Review images in the viewer; use the Study Explorer to move through series.</li>"
            "<li>Select <b>Decode MRI</b>. You may optionally add context, such as: "
            "&quot;twisted right knee while skiing, lateral pain for two weeks&quot;.</li>"
            "<li>Explore the findings, injury assessment, impression, sequence evidence, and "
            "image limitations.</li>"
            "</ol>"
            "<p><b>Privacy:</b> offline MedGemma keeps MRI image processing on this Mac. "
            "Cloud providers can be selected only in Config AI.</p>"
            f"<p><b>Offline AI:</b> {offline_note}</p>"
        )
        guide.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addWidget(guide)
        layout.addWidget(buttons)
