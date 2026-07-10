"""AI provider configuration dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from medreport.reports.ai_report import (
    PROVIDER_DEFAULTS,
    AIProvider,
    AIProviderConfig,
)


class AIConfigDialog(QDialog):
    """Dialog for selecting AI report generation providers."""

    def __init__(self, config: AIProviderConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Config")
        self._current_config = config
        self.provider_combo = QComboBox()
        for provider, defaults in PROVIDER_DEFAULTS.items():
            self.provider_combo.addItem(defaults.label, provider.value)
        self.model_edit = QLineEdit()
        self.base_url_edit = QLineEdit()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        fields = [self.provider_combo, self.model_edit, self.base_url_edit, self.api_key_edit]
        for field in fields:
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._build_layout()
        self._load_config(config)
        self.provider_combo.currentIndexChanged.connect(self._sync_provider_fields)
        self._sync_provider_fields()

    def config(self) -> AIProviderConfig:
        """Return the selected provider configuration."""

        provider = AIProvider(str(self.provider_combo.currentData()))
        defaults = PROVIDER_DEFAULTS[provider]
        return AIProviderConfig(
            provider=provider,
            model=self.model_edit.text().strip() or defaults.model,
            base_url=self.base_url_edit.text().strip() or defaults.base_url,
            api_key=self.api_key_edit.text().strip() or defaults.api_key,
        )

    def _build_layout(self) -> None:
        self.resize(520, 180)
        self.setMinimumWidth(420)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.addRow("Provider", self.provider_combo)
        form.addRow("Model", self.model_edit)
        form.addRow("Base URL", self.base_url_edit)
        form.addRow("API Key", self.api_key_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _load_config(self, config: AIProviderConfig) -> None:
        index = self.provider_combo.findData(config.provider.value)
        self.provider_combo.setCurrentIndex(max(0, index))
        self.model_edit.setText(config.model)
        self.base_url_edit.setText(config.base_url or "")
        self.api_key_edit.setText(config.api_key)

    def _sync_provider_fields(self) -> None:
        provider = AIProvider(str(self.provider_combo.currentData()))
        defaults = PROVIDER_DEFAULTS[provider]
        self.base_url_edit.setEnabled(defaults.base_url is not None)
        if self._current_config.provider is provider:
            return
        self.model_edit.setText(defaults.model)
        self.base_url_edit.setText(defaults.base_url or "")
        self.api_key_edit.setText(defaults.api_key)
