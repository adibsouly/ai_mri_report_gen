"""Tests for AI provider configuration dialog behavior."""

from __future__ import annotations

from typing import Any

from medreport.reports.ai_report import (
    DEFAULT_LM_STUDIO_BASE_URL,
    DEFAULT_LM_STUDIO_MODEL,
    AIProvider,
    AIProviderConfig,
)
from medreport.ui.ai_config_dialog import AIConfigDialog


def test_switching_back_to_lm_studio_restores_parameters(qtbot: Any) -> None:
    dialog = AIConfigDialog(
        AIProviderConfig(
            provider=AIProvider.LM_STUDIO,
            model=DEFAULT_LM_STUDIO_MODEL,
            base_url=DEFAULT_LM_STUDIO_BASE_URL,
            api_key="lm-studio",
        )
    )
    qtbot.addWidget(dialog)

    dialog.provider_combo.setCurrentIndex(dialog.provider_combo.findData(AIProvider.OPENAI.value))
    dialog.provider_combo.setCurrentIndex(
        dialog.provider_combo.findData(AIProvider.LM_STUDIO.value)
    )

    assert dialog.model_edit.text() == DEFAULT_LM_STUDIO_MODEL
    assert dialog.base_url_edit.text() == DEFAULT_LM_STUDIO_BASE_URL
    assert dialog.api_key_edit.text() == "lm-studio"
