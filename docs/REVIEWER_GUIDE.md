# Reviewer Guide

This guide provides a reproducible dashboard-only review path. It does not require private platform records, API keys, local model weights, or the original video files.

## Docker path

```powershell
docker compose up --build
```

Then open:

```text
http://127.0.0.1:5001/healthz
http://127.0.0.1:5001/readyz
http://127.0.0.1:5001/page/dashboard
```

The Compose setup creates a MySQL database, applies `sql/schema.sql`, loads `sql/demo_seed.sql`, and starts the Flask application.

## Local MySQL path

1. Create a review database named `db_weibo_basin_review`.
2. Copy `.env.reviewer.example` to `.env.reviewer`.
3. Set `DB_PASSWORD` in `.env.reviewer`.
4. Install the review dependencies:

```powershell
python -m venv .venv-review
.\.venv-review\Scripts\Activate.ps1
pip install -r requirements-review.txt
```

5. Initialize the synthetic database:

```powershell
python scripts/init_demo_db.py
```

6. Check the environment:

```powershell
python scripts/doctor.py
```

7. Start the application with the review environment:

```powershell
$env:DB_HOST='localhost'
$env:DB_PORT='3306'
$env:DB_USER='root'
$env:DB_PASSWORD='your-review-database-password'
$env:DB_NAME='db_weibo_basin_review'
python app.py
```

## Expected results

```text
/healthz  HTTP 200
/readyz   HTTP 200 and database=ok
/page/dashboard HTTP 200
```

`/readyz` verifies the database connection, required tables, and presence of demo articles. The dashboard generation may take several minutes on the first request.

## Optional features

The reviewer dashboard uses synthetic records only. Question answering, OCR, ASR, and the original video features are optional modules and require their corresponding local models or API credentials. Their absence does not prevent the dashboard review path.