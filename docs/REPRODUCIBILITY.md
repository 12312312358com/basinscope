# Reproducibility

## Requirements

- Windows 10/11 or Linux
- Python 3.10+
- MySQL 8.0+
- 16 GB RAM recommended for the complete retrieval and question-answering stack
- ffmpeg or imageio-ffmpeg for video audio processing
- Optional CUDA GPU
- Optional OpenAI-compatible credentials for language and vision services

## Environment

1. Create and activate a Python virtual environment.
2. Install `requirements.txt`.
3. Copy `.env.example` to `.env` and provide local database and optional API credentials.
4. Do not commit `.env`, credentials, raw platform records, or model weights.

## Database

Create the tables listed in `DATA_SETUP.md`, then import lawfully collected and
desensitized records. The repository does not redistribute raw platform records
or database dumps.

## Generation and launch

Run the data-generation sequence documented in `README.md`, then start:

```powershell
python app.py
```

Verify the health endpoint:

```text
http://127.0.0.1:5001/healthz
```

Open the dashboard:

```text
http://127.0.0.1:5001/page/dashboard
```

## Release verification

- Use the annotated Git tag for the manuscript version.
- Confirm that `README.md`, `LICENCE.txt`, and `CITATION.cff` exist at that tag.
- Confirm that code, templates, requirements, and documentation are present.
- Confirm that generated data, local models, logs, uploads, and credentials are absent.
- Record the tested Python and MySQL versions in the release notes.
