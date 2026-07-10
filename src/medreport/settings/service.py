"""Qt-backed settings service."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QSize

from medreport.reports.ai_report import (
    PROVIDER_DEFAULTS,
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

    def theme(self) -> str:
        """Return the saved visual theme, defaulting to light."""

        value = str(self._settings.value("appearance/theme", "light"))
        return value if value in {"light", "dark"} else "light"

    def save_theme(self, theme: str) -> None:
        """Persist the selected visual theme."""

        if theme not in {"light", "dark"}:
            raise ValueError(f"Unsupported theme: {theme}")
        self._settings.setValue("appearance/theme", theme)

    def add_recent_folder(self, folder: Path) -> None:
        """Store a recent import folder."""

        folders = self.recent_folders()
        folder_text = str(folder)
        if folder_text in folders:
            folders.remove(folder_text)
        self._settings.setValue("recent/folders", [folder_text, *folders[:9]])

    def last_import_folder(self) -> Path | None:
        """Return the most recently imported folder when it still exists."""

        folders = self.recent_folders()
        if not folders:
            return None
        folder = Path(folders[0])
        return folder if folder.is_dir() else None

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
        try:
            provider = AIProvider(provider_text)
        except ValueError:
            provider = AIProvider.LM_STUDIO
        defaults = PROVIDER_DEFAULTS[provider]
        settings_key = provider.value
        return AIProviderConfig(
            provider=provider,
            model=str(self._settings.value(f"ai/{settings_key}/model", defaults.model)),
            base_url=_optional_settings_value(
                self._settings.value(f"ai/{settings_key}/base_url", defaults.base_url)
            ),
            api_key=str(self._settings.value(f"ai/{settings_key}/api_key", defaults.api_key)),
        )

    def save_ai_provider_config(self, config: AIProviderConfig) -> None:
        """Persist AI provider configuration."""

        self._settings.setValue("ai/provider", config.provider.value)
        settings_key = config.provider.value
        self._settings.setValue(f"ai/{settings_key}/model", config.model)
        self._settings.setValue(f"ai/{settings_key}/base_url", config.base_url or "")
        self._settings.setValue(f"ai/{settings_key}/api_key", config.api_key)


def _optional_settings_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None
