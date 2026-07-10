"""Qt-backed settings service."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QSize

from medreport.reports.ai_report import (
    DEFAULT_LM_STUDIO_BASE_URL,
    DEFAULT_LM_STUDIO_MODEL,
    DEFAULT_REPORT_MODEL,
    AIProvider,
    AIProviderConfig,
)


class SettingsService:
    """Persist user preferences through QSettings."""

    def __init__(self) -> None:
        self._settings = QSettings("AI MRI Analyzer", "AI MRI Analyzer")

    def window_size(self, default: QSize) -> QSize:
        """Return the saved main window size."""

        value = self._settings.value("window/size", default)
        return value if isinstance(value, QSize) else default

    def save_window_size(self, size: QSize) -> None:
        """Persist the main window size."""

        self._settings.setValue("window/size", size)

    def add_recent_folder(self, folder: Path) -> None:
        """Store a recent import folder."""

        folders = self.recent_folders()
        folder_text = str(folder)
        if folder_text in folders:
            folders.remove(folder_text)
        self._settings.setValue("recent/folders", [folder_text, *folders[:9]])

    def recent_folders(self) -> list[str]:
        """Return recent import folders."""

        value = self._settings.value("recent/folders", [])
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            return [value]
        return []

    def ai_provider_config(self) -> AIProviderConfig:
        """Return saved AI provider configuration."""

        provider_text = str(self._settings.value("ai/provider", AIProvider.LM_STUDIO.value))
        provider = AIProvider(provider_text)
        if provider is AIProvider.OPENAI:
            return AIProviderConfig(
                provider=provider,
                model=str(self._settings.value("ai/openai/model", DEFAULT_REPORT_MODEL)),
                base_url=None,
                api_key=str(self._settings.value("ai/openai/api_key", "")),
            )
        return AIProviderConfig(
            provider=provider,
            model=str(self._settings.value("ai/lm_studio/model", DEFAULT_LM_STUDIO_MODEL)),
            base_url=str(
                self._settings.value("ai/lm_studio/base_url", DEFAULT_LM_STUDIO_BASE_URL)
            ),
            api_key=str(self._settings.value("ai/lm_studio/api_key", "lm-studio")),
        )

    def save_ai_provider_config(self, config: AIProviderConfig) -> None:
        """Persist AI provider configuration."""

        self._settings.setValue("ai/provider", config.provider.value)
        if config.provider is AIProvider.OPENAI:
            self._settings.setValue("ai/openai/model", config.model)
            self._settings.setValue("ai/openai/api_key", config.api_key)
            return
        self._settings.setValue("ai/lm_studio/model", config.model)
        self._settings.setValue("ai/lm_studio/base_url", config.base_url or "")
        self._settings.setValue("ai/lm_studio/api_key", config.api_key)
