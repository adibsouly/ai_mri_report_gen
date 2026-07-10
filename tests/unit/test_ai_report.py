"""Tests for AI-assisted report generation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import numpy as np

from medreport.models import ImageVolume, Series
from medreport.reports.ai_report import (
    PROVIDER_DEFAULTS,
    AIProvider,
    AIProviderConfig,
    AIReportRequest,
    AIReportService,
    AIStudyReportRequest,
    SeriesVolume,
    encode_diagnostic_slices,
    encode_representative_slices,
    select_diagnostic_slice_indexes,
)


class StubResponses:
    """Responses API test double."""

    def __init__(self) -> None:
        self.payload: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> SimpleNamespace:
        """Capture payload and return a report."""

        self.payload = kwargs
        return SimpleNamespace(output_text="# MRI Report\n\n## Impression\nNo focal abnormality.")


class StubClient:
    """OpenAI client test double."""

    def __init__(self) -> None:
        self.responses = StubResponses()


class StubActiveClient:
    """Closable provider transport used to verify active cancellation."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_encode_representative_slices_returns_base64_pngs() -> None:
    volume = ImageVolume(
        series_uid="series-1",
        pixels=np.arange(5 * 4 * 4, dtype=np.float32).reshape((5, 4, 4)),
        spacing=(1.0, 1.0, 1.0),
    )

    encoded = encode_representative_slices(volume, max_images=3)

    assert len(encoded) == 3
    assert all(isinstance(item, str) and item for item in encoded)


def test_diagnostic_slice_selection_prefers_informative_slices() -> None:
    pixels = np.zeros((5, 8, 8), dtype=np.float32)
    pixels[3, 2:6, 2:6] = np.arange(16, dtype=np.float32).reshape((4, 4))
    volume = ImageVolume(
        series_uid="series-1",
        pixels=pixels,
        spacing=(1.0, 1.0, 1.0),
    )

    indexes = select_diagnostic_slice_indexes(volume, max_images=2)
    encoded = encode_diagnostic_slices(volume, max_images=2)

    assert 3 in indexes
    assert len(encoded) == 2


def test_ai_report_service_defaults_to_lm_studio() -> None:
    service = AIReportService(config=AIProviderConfig())

    assert service.is_configured()
    assert "LM Studio" in service.configuration_hint()


def test_all_requested_ai_providers_are_registered() -> None:
    assert {
        AIProvider.LM_STUDIO,
        AIProvider.OPENAI,
        AIProvider.OLLAMA,
        AIProvider.CLAUDE,
        AIProvider.GROK,
        AIProvider.GEMINI,
        AIProvider.VLLM,
        AIProvider.APPLE_INTELLIGENCE,
    } == set(PROVIDER_DEFAULTS)


def test_apple_intelligence_requires_the_macos_foundation_model_cli() -> None:
    service = AIReportService(
        config=AIProviderConfig(
            provider=AIProvider.APPLE_INTELLIGENCE,
            model="on-device",
            base_url=None,
            api_key="",
        )
    )

    with patch("medreport.reports.ai_report.shutil.which", return_value=None):
        assert not service.is_configured()
        assert "macOS 27" in service.configuration_hint()


def test_apple_intelligence_sends_mri_images_to_fm_cli() -> None:
    service = AIReportService(
        config=AIProviderConfig(
            provider=AIProvider.APPLE_INTELLIGENCE,
            model="on-device",
            base_url=None,
            api_key="",
        )
    )
    series = Series(series_instance_uid="series-1", description="Sagittal PD", modality="MR")
    volume = ImageVolume(
        series_uid="series-1",
        pixels=np.zeros((2, 4, 4), dtype=np.float32),
        spacing=(1.0, 1.0, 1.0),
    )
    process = SimpleNamespace(
        returncode=0,
        communicate=lambda timeout: ("# MRI Report\n\nNo abnormality.", ""),
        poll=lambda: 0,
    )

    with (
        patch("medreport.reports.ai_report.shutil.which", return_value="/usr/bin/fm"),
        patch("medreport.reports.ai_report.subprocess.Popen", return_value=process) as popen,
    ):
        report = service.generate_mri_report(AIReportRequest(series=series, volume=volume))

    assert "MRI Report" in report
    command = popen.call_args.args[0]
    assert command[:2] == ["/usr/bin/fm", "respond"]
    assert command.count("--image") == 2


def test_cancel_active_request_closes_provider_transport() -> None:
    service = AIReportService(config=AIProviderConfig())
    transport = StubActiveClient()
    service._register_active_resource(transport)

    service.cancel_active_request()

    assert transport.closed


def test_api_key_providers_require_credentials() -> None:
    for provider in [AIProvider.OPENAI, AIProvider.CLAUDE, AIProvider.GROK, AIProvider.GEMINI]:
        service = AIReportService(
            config=AIProviderConfig(
                provider=provider,
                model=PROVIDER_DEFAULTS[provider].model,
                base_url=PROVIDER_DEFAULTS[provider].base_url,
                api_key="",
            )
        )

        assert not service.is_configured()
        assert PROVIDER_DEFAULTS[provider].label in service.configuration_hint()


def test_ai_report_service_sends_text_and_images() -> None:
    client = StubClient()
    service = AIReportService(
        client=client,
        config=AIProviderConfig(provider=AIProvider.LM_STUDIO, model="test-model"),
    )
    series = Series(series_instance_uid="series-1", description="Sagittal PD", modality="MR")
    volume = ImageVolume(
        series_uid="series-1",
        pixels=np.zeros((2, 4, 4), dtype=np.float32),
        spacing=(1.0, 1.0, 1.0),
    )

    report = service.generate_mri_report(
        AIReportRequest(series=series, volume=volume, max_images=2)
    )

    assert "MRI Report" in report
    assert client.responses.payload is not None
    assert client.responses.payload["model"] == "test-model"
    content = client.responses.payload["input"][0]["content"]
    assert content[0]["type"] == "input_text"
    assert content[1]["type"] == "input_image"
    assert str(content[1]["image_url"]).startswith("data:image/png;base64,")


def test_ai_report_service_sends_multiple_imported_series() -> None:
    client = StubClient()
    service = AIReportService(
        client=client,
        config=AIProviderConfig(provider=AIProvider.LM_STUDIO, model="test-model"),
    )
    series_volumes = [
        SeriesVolume(
            series=Series(series_instance_uid="series-1", description="Sagittal PD", modality="MR"),
            volume=ImageVolume(
                series_uid="series-1",
                pixels=np.zeros((3, 4, 4), dtype=np.float32),
                spacing=(1.0, 1.0, 1.0),
            ),
        ),
        SeriesVolume(
            series=Series(
                series_instance_uid="series-2",
                description="Coronal STIR",
                modality="MR",
            ),
            volume=ImageVolume(
                series_uid="series-2",
                pixels=np.ones((3, 4, 4), dtype=np.float32),
                spacing=(1.0, 1.0, 1.0),
            ),
        ),
    ]

    report = service.generate_study_mri_report(
        AIStudyReportRequest(series_volumes=series_volumes, max_total_images=4)
    )

    assert "MRI Report" in report
    assert client.responses.payload is not None
    content = client.responses.payload["input"][0]["content"]
    assert "Imported MRI series" in content[0]["text"]
    assert len([item for item in content if item["type"] == "input_image"]) == 4


def test_chat_about_report_grounds_follow_up_in_report_and_history() -> None:
    client = StubClient()
    service = AIReportService(
        client=client,
        config=AIProviderConfig(provider=AIProvider.LM_STUDIO, model="test-model"),
    )

    answer = service.chat_about_report(
        report="# MRI Report\n\n## Findings\nSmall joint effusion.",
        question="What does effusion mean?",
        conversation=[("Is this a final diagnosis?", "No, this is a draft.")],
    )

    assert "MRI Report" in answer
    assert client.responses.payload is not None
    prompt = client.responses.payload["input"][0]["content"][0]["text"]
    assert "Small joint effusion" in prompt
    assert "What does effusion mean?" in prompt
    assert "No, this is a draft" in prompt
    assert not any(
        item["type"] == "input_image"
        for item in client.responses.payload["input"][0]["content"]
    )
