# Install And Use

## Quick Start From Source

```bash
git clone https://github.com/adibsouly/ai_mri_report_gen.git
cd ai_mri_report_gen
uv sync --extra dev
uv run python scripts/generate_icon.py
uv run medreport
```

## Configure LM Studio

LM Studio is the default AI interpreter.

1. Install LM Studio.
2. Load a vision-capable local model.
3. Start the local server.
4. Keep the default server URL as `http://localhost:1234/v1`.
5. In MedReport, open `AI Config > AI Config...`.
6. Confirm:
   - Provider: `LM Studio`
   - Base URL: `http://localhost:1234/v1`
   - Model: the model name exposed by LM Studio

## Configure OpenAI

Open `AI Config > AI Config...`, choose `OpenAI`, enter the model and API key, then save.

Environment alternative:

```bash
export MEDREPORT_AI_PROVIDER=openai
export OPENAI_API_KEY="your_key"
export MEDREPORT_OPENAI_MODEL="gpt-5.5"
uv run medreport
```

## Generate A Report

1. Click `Import Folder`.
2. Choose a DICOM MRI folder.
3. Click `AI Report`.
4. Review the generated draft in the Report panel.

Reports are autosaved to:

```text
~/Library/Application Support/MedReport/reports/
```

Use `Report > Save Report As...` or `File > Save Report As...` to save another copy.

## Build A macOS App

```bash
uv sync --extra packaging
uv run python scripts/generate_icon.py
uv run python scripts/package_pyinstaller.py
```

The packaged app is created under:

```text
dist/MedReport.app
```

## Notes

MedReport creates clinician-reviewable AI report drafts. It is not a standalone
diagnostic device and generated reports must be reviewed by a qualified clinician.
