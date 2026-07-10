# AI MRI Report Gen

AI MRI Report Gen is a local-first desktop workstation for importing DICOM MRI studies
and generating clinician-reviewable AI report drafts. It is built with Python 3.12,
PySide6, pydicom, SimpleITK, and configurable AI provider connections.

LM Studio is the default AI interpreter, so MRI slices can be analyzed through a local
vision-capable model at `http://localhost:1234/v1`. Apple Intelligence, OpenAI,
Ollama, Claude, Grok, Gemini, and vLLM can also be configured from the app.

## Features

- Import DICOM folders recursively.
- Group studies, series, and images.
- Load MRI volumes in the background.
- Select compact high-signal diagnostic slices to reduce local-model timeouts.
- Generate AI-assisted MRI report drafts.
- See a live activity indicator while MRI analysis and report generation are running.
- Stop an in-progress AI analysis and safely ignore late provider responses.
- Chat with the selected AI provider to ask report-grounded follow-up questions.
- Use the light interface by default or switch to dark mode from `Customize`.
- Configure `Apple Intelligence`, `LM Studio`, `OpenAI`, `Ollama`, `Claude`, `Grok`,
  `Gemini`, or `vLLM`
  from `AI Config > AI Config...`.
- Autosave generated reports to Markdown files.
- Save report drafts manually with `Report > Save Report As...`.
- Package a standalone macOS app with PyInstaller.

## Quick Start

```bash
git clone https://github.com/adibsouly/ai_mri_report_gen.git
cd ai_mri_report_gen
uv sync --extra dev
uv run python scripts/generate_icon.py
uv run medreport
```

## LM Studio Setup

1. Open LM Studio.
2. Load a vision-capable model.
3. Start the local server.
4. Keep the server URL at `http://localhost:1234/v1`.
5. In the app, open `AI Config > AI Config...`.
6. Set the model name to the model exposed by LM Studio.

## Other AI Providers

Open `AI Config > AI Config...`, choose a provider, enter the model, endpoint, and API key
where required, then save. Defaults:

- `Apple Intelligence`: on-device, no API key; requires macOS 27 or later and an
  Apple Intelligence-capable Mac with Apple Intelligence enabled
- `OpenAI`: API key required, model `gpt-5.5`
- `Ollama`: `http://localhost:11434/v1`, model `llava`
- `Claude`: API key required, `https://api.anthropic.com/v1`
- `Grok`: API key required, `https://api.x.ai/v1`
- `Gemini`: API key required, `https://generativelanguage.googleapis.com/v1beta`
- `vLLM`: `http://localhost:8000/v1`, model `local-model`

You can also use environment variables:

```bash
export MEDREPORT_AI_PROVIDER=openai
export OPENAI_API_KEY="your_key"
export MEDREPORT_OPENAI_MODEL="gpt-5.5"
uv run medreport
```

## Use

1. Click `Import Folder`.
2. Select a DICOM MRI folder.
3. Click `AI Report`.
4. Review the report in the bottom Report panel.

Reports are autosaved to:

```text
~/Library/Application Support/AI MRI Analyzer/reports/
```

## Build The App

```bash
uv sync --extra packaging
uv run python scripts/generate_icon.py
uv run --isolated --extra packaging python scripts/package_pyinstaller.py
```

The packaged macOS app will be created at:

```text
dist/AI MRI Analyzer.app
dist/AI-MRI-Analyzer-macOS-arm64-v0.1.0.zip
```

The default build is ad-hoc signed. Set `MEDREPORT_CODESIGN_IDENTITY` to a Developer ID
Application identity when preparing a notarized public distribution.

## Development

```bash
uv sync --extra dev
uv run ruff check .
uv run mypy src
uv run pytest
```

## Architecture

The app follows Clean Architecture:

```text
Presentation (Qt) -> Application -> Domain -> Infrastructure
```

The UI never manipulates DICOM files directly. It calls application services, which
depend on repository/provider interfaces. DICOM parsing and AI backend calls live behind
infrastructure-style adapters.

## Safety

Generated reports are drafts for clinician review. This software is not a standalone
diagnostic device and should not be used as the sole basis for medical decisions.

More detailed install instructions are in [docs/install.md](docs/install.md).
