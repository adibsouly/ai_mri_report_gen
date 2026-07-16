"""Background downloader and Ollama importer for MedGemma."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

HF_OLLAMA_MODEL = "hf.co/gguf-org/medgemma-1.5-4b-it-gguf:Q4_0"
OLLAMA_MODEL_NAME = "medgemma-1.5"


class MedGemmaInstallSignals(QObject):
    progress = Signal(int, str)
    finished = Signal(str, bool)


@dataclass
class MedGemmaInstallWorker(QRunnable):
    """Install MedGemma through Ollama so its vision projector is preserved."""

    def __post_init__(self) -> None:
        super().__init__()
        self.signals = MedGemmaInstallSignals()

    def run(self) -> None:
        try:
            ollama = find_ollama_executable()
            if not ollama:
                raise RuntimeError("Ollama is not installed. Install Ollama, then run setup again.")
            self.signals.progress.emit(1, "Downloading MedGemma and its vision projector…")
            result = subprocess.run(
                [ollama, "pull", HF_OLLAMA_MODEL],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or "Ollama could not download MedGemma.")
            self.signals.progress.emit(96, "Registering the complete vision model with Ollama…")
            subprocess.run([ollama, "rm", OLLAMA_MODEL_NAME], capture_output=True, check=False)
            result = subprocess.run(
                [ollama, "cp", HF_OLLAMA_MODEL, OLLAMA_MODEL_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or "Ollama could not register MedGemma.")
            self.signals.progress.emit(100, "MedGemma 1.5 is ready for offline use.")
            self.signals.finished.emit(
                "MedGemma 1.5 is ready. Select MedGemma 1.5 (Offline) in AI Config.", False
            )
        except (OSError, RuntimeError) as error:
            self.signals.finished.emit(str(error), True)


def find_ollama_executable() -> str | None:
    """Locate either a future bundled runtime or Ollama's normal macOS installation."""

    candidates = [
        os.environ.get("MEDREPORT_OLLAMA_BIN", ""),
        str(Path(sys.executable).parent.parent / "Resources" / "ollama"),
        "/Applications/Ollama.app/Contents/Resources/ollama",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return shutil.which("ollama")
