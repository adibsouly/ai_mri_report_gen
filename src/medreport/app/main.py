"""Application composition root."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from medreport.app.services import StudyImportService, VolumeService
from medreport.core.logging import configure_logging
from medreport.database.sqlite import SQLiteDatabase
from medreport.dicom.repository import PydicomStudyRepository, SimpleITKVolumeRepository
from medreport.reports.ai_report import AIReportService
from medreport.settings.service import SettingsService
from medreport.ui.main_window import MainWindow
from medreport.ui.theme import DARK_THEME


def app_data_dir() -> Path:
    """Return the platform-appropriate application data directory."""

    return Path.home() / "Library" / "Application Support" / "MedReport"


def main() -> int:
    """Start the MedReport desktop application."""

    data_dir = app_data_dir()
    configure_logging(data_dir / "logs")
    database = SQLiteDatabase(data_dir / "medreport.sqlite3")
    database.initialize()

    application = QApplication(sys.argv)
    application.setApplicationName("MedReport")
    application.setOrganizationName("MedReport")
    application.setStyleSheet(DARK_THEME)
    settings = SettingsService()

    window = MainWindow(
        study_import_service=StudyImportService(PydicomStudyRepository()),
        volume_service=VolumeService(SimpleITKVolumeRepository()),
        settings=settings,
        database=database,
        ai_report_service=AIReportService(config=settings.ai_provider_config()),
        report_dir=data_dir / "reports",
    )
    window.show()
    return int(application.exec())
