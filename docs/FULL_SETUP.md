# Full Application Setup

This guide is for a full local deployment of SOPRAS using lawfully collected data and optional API services. It is not required for the reviewer quick start in the repository README.

## Environment configuration

Copy the example environment file.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux:

```bash
cp .env.example .env
```

Edit `.env` and provide database credentials and optional API credentials. Never commit `.env`.

Important variables:

```text
DB_HOST
DB_PORT
DB_USER
DB_PASSWORD
DB_NAME
SECRET_KEY
HOST
PORT
XINGHUO_BASE_URL
XINGHUO_API_PASSWORD
XINGHUO_MODEL
VISION_BASE_URL
VISION_API_KEY
VISION_MODEL
```

## Data and model assets

See [Data setup](DATA_SETUP.md) for the required tables, fields, and data-governance rules. Raw platform records and model weights must not be committed to Git.

## Related documentation

- [Reproducibility](REPRODUCIBILITY.md)
- [Methods](METHODS.md)
- [Architecture](ARCHITECTURE.md)
