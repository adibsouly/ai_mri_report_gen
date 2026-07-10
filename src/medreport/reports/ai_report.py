"""AI-backed MRI report drafting service."""

from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, cast

import httpx
import numpy as np
from openai import OpenAI
from PIL import Image

from medreport.models import ImageVolume, Series
from medreport.viewer.windowing import normalize_to_uint8

DEFAULT_REPORT_MODEL = "gpt-5.5"
DEFAULT_LM_STUDIO_MODEL = "local-model"
DEFAULT_LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
DEFAULT_OLLAMA_MODEL = "llava"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_CLAUDE_MODEL = "claude-3-5-sonnet-latest"
DEFAULT_CLAUDE_BASE_URL = "https://api.anthropic.com/v1"
DEFAULT_GROK_MODEL = "grok-2-vision-latest"
DEFAULT_GROK_BASE_URL = "https://api.x.ai/v1"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_VLLM_MODEL = "local-model"
DEFAULT_VLLM_BASE_URL = "http://localhost:8000/v1"
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
    OLLAMA = "ollama"
    CLAUDE = "claude"
    GROK = "grok"
    GEMINI = "gemini"
    VLLM = "vllm"


@dataclass(frozen=True)
class AIProviderDefaults:
    """Default connection values for an AI backend."""

    label: str
    model: str
    base_url: str | None
    api_key: str
    needs_api_key: bool


PROVIDER_DEFAULTS: dict[AIProvider, AIProviderDefaults] = {
    AIProvider.LM_STUDIO: AIProviderDefaults(
        label="LM Studio",
        model=DEFAULT_LM_STUDIO_MODEL,
        base_url=DEFAULT_LM_STUDIO_BASE_URL,
        api_key="lm-studio",
        needs_api_key=False,
    ),
    AIProvider.OPENAI: AIProviderDefaults(
        label="OpenAI",
        model=DEFAULT_REPORT_MODEL,
        base_url=None,
        api_key="",
        needs_api_key=True,
    ),
    AIProvider.OLLAMA: AIProviderDefaults(
        label="Ollama",
        model=DEFAULT_OLLAMA_MODEL,
        base_url=DEFAULT_OLLAMA_BASE_URL,
        api_key="ollama",
        needs_api_key=False,
    ),
    AIProvider.CLAUDE: AIProviderDefaults(
        label="Claude",
        model=DEFAULT_CLAUDE_MODEL,
        base_url=DEFAULT_CLAUDE_BASE_URL,
        api_key="",
        needs_api_key=True,
    ),
    AIProvider.GROK: AIProviderDefaults(
        label="Grok",
        model=DEFAULT_GROK_MODEL,
        base_url=DEFAULT_GROK_BASE_URL,
        api_key="",
        needs_api_key=True,
    ),
    AIProvider.GEMINI: AIProviderDefaults(
        label="Gemini",
        model=DEFAULT_GEMINI_MODEL,
        base_url=DEFAULT_GEMINI_BASE_URL,
        api_key="",
        needs_api_key=True,
    ),
    AIProvider.VLLM: AIProviderDefaults(
        label="vLLM",
        model=DEFAULT_VLLM_MODEL,
        base_url=DEFAULT_VLLM_BASE_URL,
        api_key="vllm",
        needs_api_key=False,
    ),
}


OPENAI_COMPATIBLE_PROVIDERS = {
    AIProvider.LM_STUDIO,
    AIProvider.OLLAMA,
    AIProvider.GROK,
    AIProvider.VLLM,
}


@dataclass(frozen=True)
class AIProviderConfig:
    """Configuration for an AI report backend."""

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
        defaults = PROVIDER_DEFAULTS[provider]
        env_prefix = f"MEDREPORT_{provider.value.upper()}"
        return cls(
            provider=provider,
            model=os.environ.get(f"{env_prefix}_MODEL", defaults.model),
            base_url=os.environ.get(f"{env_prefix}_BASE_URL", defaults.base_url or ""),
            api_key=os.environ.get(f"{env_prefix}_API_KEY", defaults.api_key),
        )

    @property
    def label(self) -> str:
        """Return a user-facing backend label."""

        return PROVIDER_DEFAULTS[self.provider].label


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
        if PROVIDER_DEFAULTS[self._config.provider].needs_api_key:
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

        defaults = PROVIDER_DEFAULTS[self._config.provider]
        if defaults.needs_api_key and not self._config.api_key:
            return f"Enter a {defaults.label} API key before generating an AI report."
        if self._config.provider is AIProvider.LM_STUDIO:
            return (
                "Start LM Studio, load a vision-capable model, and enable the local server at "
                f"{self._config.base_url or DEFAULT_LM_STUDIO_BASE_URL}."
            )
        if self._config.provider is AIProvider.OLLAMA:
            return (
                "Start Ollama, pull a vision-capable model, and keep the local API running at "
                f"{self._config.base_url or DEFAULT_OLLAMA_BASE_URL}."
            )
        if self._config.provider is AIProvider.VLLM:
            return (
                "Start a vLLM OpenAI-compatible server with a vision-capable model at "
                f"{self._config.base_url or DEFAULT_VLLM_BASE_URL}."
            )
        return f"Configure {defaults.label} with a vision-capable model before generating a report."

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
        if self._client is None and self._config.provider is AIProvider.CLAUDE:
            return self._create_claude_response(prompt, images)
        if self._client is None and self._config.provider is AIProvider.GEMINI:
            return self._create_gemini_response(prompt, images)
        if self._client is None and self._config.provider in OPENAI_COMPATIBLE_PROVIDERS:
            return self._create_openai_compatible_response(
                cast(OpenAI, client),
                prompt,
                images,
            )

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

    def _create_openai_compatible_response(
        self,
        client: OpenAI,
        prompt: str,
        images: list[str],
    ) -> str:
        content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
        content.extend(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image}"},
            }
            for image in images
        )
        response = client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": cast(Any, content)}],
        )
        output_text = response.choices[0].message.content or ""
        if not output_text.strip():
            raise RuntimeError(f"{self._config.label} returned an empty report draft.")
        return output_text.strip()

    def _create_claude_response(self, prompt: str, images: list[str]) -> str:
        base_url = (self._config.base_url or DEFAULT_CLAUDE_BASE_URL).rstrip("/")
        content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
        content.extend(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image,
                },
            }
            for image in images
        )
        response = httpx.post(
            f"{base_url}/messages",
            headers={
                "x-api-key": self._config.api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": self._model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": content}],
            },
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
        output_text = "\n".join(
            item.get("text", "")
            for item in payload.get("content", [])
            if item.get("type") == "text"
        )
        if not output_text.strip():
            raise RuntimeError(f"{self._config.label} returned an empty report draft.")
        return output_text.strip()

    def _create_gemini_response(self, prompt: str, images: list[str]) -> str:
        base_url = (self._config.base_url or DEFAULT_GEMINI_BASE_URL).rstrip("/")
        parts: list[dict[str, object]] = [{"text": prompt}]
        parts.extend(
            {
                "inline_data": {
                    "mime_type": "image/png",
                    "data": image,
                }
            }
            for image in images
        )
        response = httpx.post(
            f"{base_url}/models/{self._model}:generateContent",
            params={"key": self._config.api_key},
            json={"contents": [{"role": "user", "parts": parts}]},
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
        output_text = "\n".join(
            part.get("text", "")
            for candidate in payload.get("candidates", [])
            for part in candidate.get("content", {}).get("parts", [])
            if "text" in part
        )
        if not output_text.strip():
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
