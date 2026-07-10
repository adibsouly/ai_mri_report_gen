"""OpenAI-backed MRI report drafting service."""

from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, cast

import numpy as np
from openai import OpenAI
from PIL import Image

from medreport.models import ImageVolume, Series
from medreport.viewer.windowing import normalize_to_uint8

DEFAULT_REPORT_MODEL = "gpt-5.5"
DEFAULT_LM_STUDIO_MODEL = "local-model"
DEFAULT_LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
MAX_REPORT_IMAGES = 4
MAX_STUDY_REPORT_IMAGES = 6
MAX_CANDIDATE_SLICES_PER_SERIES = 24


class ResponsesClient(Protocol):
    """Minimal OpenAI Responses API client shape used by this service."""

    responses: Any


class AIProvider(StrEnum):
    """Supported report-generation backends."""

    LM_STUDIO = "lm_studio"
    OPENAI = "openai"


@dataclass(frozen=True)
class AIProviderConfig:
    """Configuration for an OpenAI-compatible report backend."""

    provider: AIProvider = AIProvider.LM_STUDIO
    model: str = DEFAULT_LM_STUDIO_MODEL
    base_url: str | None = DEFAULT_LM_STUDIO_BASE_URL
    api_key: str = "lm-studio"

    @classmethod
    def from_environment(cls) -> AIProviderConfig:
        """Build provider config from environment variables."""

        provider = AIProvider(os.environ.get("MEDREPORT_AI_PROVIDER", AIProvider.LM_STUDIO))
        if provider is AIProvider.OPENAI:
            return cls(
                provider=provider,
                model=os.environ.get("MEDREPORT_OPENAI_MODEL", DEFAULT_REPORT_MODEL),
                base_url=None,
                api_key=os.environ.get("OPENAI_API_KEY", ""),
            )
        return cls(
            provider=provider,
            model=os.environ.get("MEDREPORT_LM_STUDIO_MODEL", DEFAULT_LM_STUDIO_MODEL),
            base_url=os.environ.get("MEDREPORT_LM_STUDIO_BASE_URL", DEFAULT_LM_STUDIO_BASE_URL),
            api_key=os.environ.get("MEDREPORT_LM_STUDIO_API_KEY", "lm-studio"),
        )

    @property
    def label(self) -> str:
        """Return a user-facing backend label."""

        if self.provider is AIProvider.OPENAI:
            return "OpenAI"
        return "LM Studio"


@dataclass(frozen=True)
class AIReportRequest:
    """Inputs for generating an AI-assisted MRI report draft."""

    series: Series
    volume: ImageVolume
    clinical_context: str = ""
    max_images: int = MAX_REPORT_IMAGES


@dataclass(frozen=True)
class SeriesVolume:
    """A loaded series paired with its volume for study-level reporting."""

    series: Series
    volume: ImageVolume


@dataclass(frozen=True)
class AIStudyReportRequest:
    """Inputs for generating an AI-assisted report from several MRI series."""

    series_volumes: list[SeriesVolume]
    clinical_context: str = ""
    max_total_images: int = MAX_STUDY_REPORT_IMAGES


class AIReportService:
    """Generate clinician-reviewable radiology report drafts from MRI slices."""

    def __init__(
        self,
        client: ResponsesClient | None = None,
        model: str | None = None,
        config: AIProviderConfig | None = None,
    ) -> None:
        self._config = config or AIProviderConfig.from_environment()
        self._client = client
        self._model = model or self._config.model

    def is_configured(self) -> bool:
        """Return whether the selected AI backend can be attempted."""

        if self._client is not None:
            return True
        if self._config.provider is AIProvider.OPENAI:
            return bool(self._config.api_key)
        return bool(self._config.base_url)

    @property
    def config(self) -> AIProviderConfig:
        """Return the active AI backend configuration."""

        return self._config

    def update_config(self, config: AIProviderConfig) -> None:
        """Update the active AI backend configuration."""

        self._config = config
        self._model = config.model

    def configuration_hint(self) -> str:
        """Return user-facing setup guidance for the selected backend."""

        if self._config.provider is AIProvider.OPENAI:
            return "Set OPENAI_API_KEY before generating an AI report."
        return (
            "Start LM Studio, load a vision-capable model, and enable the local server at "
            f"{self._config.base_url or DEFAULT_LM_STUDIO_BASE_URL}."
        )

    def generate_mri_report(self, request: AIReportRequest) -> str:
        """Generate a detailed MRI report draft from representative slices."""

        if not self.is_configured():
            raise RuntimeError(self.configuration_hint())

        return self._create_response(
            prompt=_build_report_prompt(request.series, request.clinical_context),
            images=encode_diagnostic_slices(request.volume, request.max_images),
        )

    def generate_study_mri_report(self, request: AIStudyReportRequest) -> str:
        """Generate a detailed MRI report draft from multiple imported MRI series."""

        if not request.series_volumes:
            raise RuntimeError("No MRI series were available for AI report generation.")
        if not self.is_configured():
            raise RuntimeError(self.configuration_hint())

        images_per_series = max(1, request.max_total_images // len(request.series_volumes))
        images: list[str] = []
        for series_volume in request.series_volumes:
            remaining = request.max_total_images - len(images)
            if remaining <= 0:
                break
            images.extend(
                encode_diagnostic_slices(
                    series_volume.volume,
                    max_images=min(images_per_series, remaining),
                )
            )

        return self._create_response(
            prompt=_build_study_report_prompt(request.series_volumes, request.clinical_context),
            images=images,
        )

    def _create_response(self, prompt: str, images: list[str]) -> str:
        client = self._client or self._create_client()
        content: list[dict[str, object]] = [
            {
                "type": "input_text",
                "text": prompt,
            }
        ]
        content.extend(
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{image}",
            }
            for image in images
        )

        response_input = cast(
            Any,
            [
                {
                    "role": "user",
                    "content": content,
                }
            ],
        )
        response = client.responses.create(
            model=self._model,
            input=response_input,
        )
        output_text = getattr(response, "output_text", "")
        if not isinstance(output_text, str) or not output_text.strip():
            raise RuntimeError(f"{self._config.label} returned an empty report draft.")
        return output_text.strip()

    def _create_client(self) -> OpenAI:
        if self._config.provider is AIProvider.OPENAI:
            return OpenAI(api_key=self._config.api_key)
        return OpenAI(
            base_url=self._config.base_url,
            api_key=self._config.api_key,
        )


def encode_representative_slices(volume: ImageVolume, max_images: int) -> list[str]:
    """Encode evenly sampled volume slices as Base64 PNG strings."""

    return _encode_slices(volume, _representative_indexes(volume, max_images))


def encode_diagnostic_slices(volume: ImageVolume, max_images: int) -> list[str]:
    """Encode a compact set of high-information slices as Base64 PNG strings."""

    return _encode_slices(volume, select_diagnostic_slice_indexes(volume, max_images))


def select_diagnostic_slice_indexes(volume: ImageVolume, max_images: int) -> list[int]:
    """Choose slices with more diagnostic signal while avoiding a huge prompt."""

    slice_count = volume.slice_count
    if max_images <= 0:
        return []
    if slice_count <= max_images:
        return list(range(slice_count))
    if slice_count == 1:
        return [0]

    candidate_indexes = _representative_indexes(
        volume,
        min(MAX_CANDIDATE_SLICES_PER_SERIES, slice_count),
    )
    scored = [
        (_slice_information_score(volume.slice_at(index)), index)
        for index in candidate_indexes
    ]
    selected = [index for _score, index in sorted(scored, reverse=True)[:max_images]]
    return sorted(selected)


def _representative_indexes(volume: ImageVolume, max_images: int) -> list[int]:
    slice_count = volume.slice_count
    if max_images <= 0:
        return []
    if slice_count <= max_images:
        return list(range(slice_count))
    if slice_count == 1:
        indexes = [0]
    else:
        image_count = min(max_images, slice_count)
        step = (slice_count - 1) / max(1, image_count - 1)
        indexes = sorted({round(index * step) for index in range(image_count)})
    return indexes


def _slice_information_score(image: np.ndarray[Any, np.dtype[np.float32]]) -> float:
    finite_image = np.nan_to_num(image, copy=False)
    contrast = float(np.std(finite_image))
    if min(finite_image.shape) < 2:
        edge_energy = 0.0
    else:
        gradient_y, gradient_x = np.gradient(finite_image)
        edge_energy = float(np.mean(np.abs(gradient_x)) + np.mean(np.abs(gradient_y)))
    non_empty_fraction = float(np.count_nonzero(finite_image) / max(1, finite_image.size))
    return contrast + edge_energy + non_empty_fraction


def _encode_slices(volume: ImageVolume, indexes: list[int]) -> list[str]:
    encoded: list[str] = []
    for index in indexes:
        pixels = normalize_to_uint8(volume.slice_at(index))
        image = Image.fromarray(pixels, mode="L")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        encoded.append(base64.b64encode(buffer.getvalue()).decode("ascii"))
    return encoded


def _build_report_prompt(series: Series, clinical_context: str) -> str:
    context = clinical_context.strip() or "No additional clinical history was provided."
    return f"""
You are assisting a radiologist by drafting a detailed MRI report from representative
image slices and DICOM metadata. This is not a final diagnosis. Be careful, specific,
and transparent about uncertainty.

Create a structured report with:
- Exam
- Technique
- Image Quality / Limitations
- Findings by anatomy
- Impression
- Confidence and recommended radiologist review points

Do not invent findings that are not visible. If the provided slice sample is incomplete,
state that limitation. Avoid urgent clinical directives unless the image evidence is clear.

Series metadata:
- Modality: {series.modality}
- Series description: {series.description}
- Manufacturer: {series.manufacturer or "Unknown"}
- TR: {series.repetition_time or "Unknown"}
- TE: {series.echo_time or "Unknown"}
- Slice thickness: {series.slice_thickness or "Unknown"}
- Pixel spacing: {series.pixel_spacing or "Unknown"}
- Image count: {len(series.images)}

Clinical context:
{context}
""".strip()


def _build_study_report_prompt(
    series_volumes: list[SeriesVolume],
    clinical_context: str,
) -> str:
    context = clinical_context.strip() or "No additional clinical history was provided."
    series_lines = "\n".join(
        _format_series_metadata(index + 1, series_volume.series, series_volume.volume)
        for index, series_volume in enumerate(series_volumes)
    )
    return f"""
You are assisting a radiologist by drafting a detailed MRI report from representative
image slices sampled across all imported MRI series and their DICOM metadata. This is
not a final diagnosis. Be careful, specific, and transparent about uncertainty.

Create a structured report with:
- Exam
- Technique
- Image Quality / Limitations
- Findings by anatomy
- Impression
- Confidence and recommended radiologist review points

Correlate findings across the provided series when possible. Do not invent findings
that are not visible. If the provided slice sample is incomplete, state that limitation.
Avoid urgent clinical directives unless the image evidence is clear.

Imported MRI series:
{series_lines}

Clinical context:
{context}
""".strip()


def _format_series_metadata(index: int, series: Series, volume: ImageVolume) -> str:
    return f"""
Series {index}
- Modality: {series.modality}
- Series description: {series.description}
- Manufacturer: {series.manufacturer or "Unknown"}
- TR: {series.repetition_time or "Unknown"}
- TE: {series.echo_time or "Unknown"}
- Slice thickness: {series.slice_thickness or "Unknown"}
- Pixel spacing: {series.pixel_spacing or "Unknown"}
- DICOM image count: {len(series.images)}
- Loaded slice count: {volume.slice_count}
- Spacing: {volume.spacing or "Unknown"}
""".strip()
