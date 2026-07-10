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
    DEFAULT_LM_STUDIO_BASE_URL,
    DEFAULT_LM_STUDIO_MODEL,
    DEFAULT_REPORT_MODEL,
    AIProvider,
    AIProviderConfig,
)


class AIConfigDialog(QDialog):
    """Dialog for selecting LM Studio or OpenAI report generation."""

    def __init__(self, config: AIProviderConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Config")
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("LM Studio", AIProvider.LM_STUDIO.value)
        self.provider_combo.addItem("OpenAI", AIProvider.OPENAI.value)
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
        if provider is AIProvider.OPENAI:
            return AIProviderConfig(
                provider=provider,
                model=self.model_edit.text().strip() or DEFAULT_REPORT_MODEL,
                base_url=None,
                api_key=self.api_key_edit.text().strip(),
            )
        return AIProviderConfig(
            provider=provider,
            model=self.model_edit.text().strip() or DEFAULT_LM_STUDIO_MODEL,
            base_url=self.base_url_edit.text().strip() or DEFAULT_LM_STUDIO_BASE_URL,
            api_key=self.api_key_edit.text().strip() or "lm-studio",
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
        is_lm_studio = provider is AIProvider.LM_STUDIO
        self.base_url_edit.setEnabled(is_lm_studio)
        if is_lm_studio:
            if not self.model_edit.text():
                self.model_edit.setText(DEFAULT_LM_STUDIO_MODEL)
            if not self.base_url_edit.text():
                self.base_url_edit.setText(DEFAULT_LM_STUDIO_BASE_URL)
            if not self.api_key_edit.text():
                self.api_key_edit.setText("lm-studio")
        elif self.model_edit.text() == DEFAULT_LM_STUDIO_MODEL:
            self.model_edit.setText(DEFAULT_REPORT_MODEL)
