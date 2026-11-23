# Reviewer Guide

Unless stated otherwise, run all commands from the repository root.

Clone the manuscript version and enter the repository:

```text
git clone --branch v1.0 --depth 1 https://github.com/12312312358com/basinscope.git
cd basinscope
```

This guide provides a reproducible reviewer path for the synthetic SOPRAS demo. It does not require private platform records, API keys, model weights, or original video files.

## What the demo verifies

The committed fixture contains only synthetic records. It verifies that:

- Flask starts and serves the reviewer dashboard;
- the required MySQL schema can be created;
- synthetic Weibo, Xiaohongshu, Zhihu, and Douyin records can be loaded;
- the Yellow River scope is selected correctly;
- `/readyz` reports the expected database contents;
- all 17 dashboard views can be opened;
- no real platform URLs, credentials, or private identifiers are included.

The synthetic demo does not reproduce the manuscript's research estimates. Those estimates require the original platform records, which are not redistributed for platform-term and privacy reasons.

## Requirements

- Python 3.10 or later
- MySQL 8.0 or later for the local installation path
- Docker Desktop or Docker Engine with Compose for the container path
- Approximately 2 GB of free disk space for dependencies and generated files

## Option A: Docker

From the repository root:

```text
docker compose up --build
```

Wait until the database and application are ready, then open:

```text
http://127.0.0.1:5001/healthz
http://127.0.0.1:5001/readyz
http://127.0.0.1:5001/page/dashboard
```

After testing, stop and remove the containers and reviewer database volume:

```text
docker compose down -v
```

## Option B: Local MySQL

### 1. Prepare MySQL

Start MySQL 8.0 and make sure a database account is available. The default example uses `root`.

Copy the reviewer environment template.

Windows PowerShell:

```powershell
Copy-Item .env.reviewer.example .env.reviewer
```

Linux:

```bash
cp .env.reviewer.example .env.reviewer
```

Edit `.env.reviewer` and set at least:

```text
DB_HOST
DB_PORT
DB_USER
DB_PASSWORD
DB_NAME
```

Keep `DB_NAME` ending in `_review`. The default value `db_weibo_basin_review` enables the committed reviewer dashboard snapshot. If a `.env` file also exists, it takes precedence over `.env.reviewer`.

### 2. Install dependencies

Windows PowerShell:

```powershell
python -m venv .venv-review
.\.venv-review\Scripts\Activate.ps1
pip install -r requirements-review.txt
```

Linux:

```bash
python3 -m venv .venv-review
source .venv-review/bin/activate
pip install -r requirements-review.txt
```

### 3. Initialize the synthetic database

```text
python scripts/init_demo_db.py
```

The initializer creates the database when the configured MySQL account has `CREATE` privilege. If it does not, create the database first as a MySQL administrator:

```text
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS db_weibo_basin_review CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
```

### 4. Run preflight checks

```text
python scripts/doctor.py
python scripts/verify_reviewer_demo.py --repo-root . --json
```

Both commands must exit successfully.

### 5. Start the application

```text
python app.py
```

Open:

```text
http://127.0.0.1:5001/page/dashboard
```

In another terminal, run the full database and HTTP validation:

```text
python scripts/verify_reviewer_demo.py --repo-root . --db --env-file .env.reviewer --url http://127.0.0.1:5001
```

## Expected reviewer data counts

`init_demo_db.py` expands the committed synthetic templates into a rich reviewer profile:

| Table | Total rows | Yellow River rows |
|---|---:|---:|
| `t_article` | 2,430 | N/A |
| `t_comment` | 140 | N/A |
| `t_basin_article` | 2,430 | 1,097 |
| `t_basin_comment` | 140 | 59 |
| `t_xhs_article` | 3,358 | N/A |
| `t_xhs_comment` | 669 | N/A |
| `t_zhihu_article` | 950 | N/A |
| `t_zhihu_comment` | 740 | N/A |
| `t_douyin_article` | 18 | N/A |
| `t_douyin_comment` | 18 | N/A |

`N/A` means that the table is stored globally and does not have a Yellow River-specific subset column.

Expected `/readyz` result:

```json
{"article_count": 1097, "comment_count": 59, "database": "ok"}
```

The reviewer mode serves `reviewer_snapshot/dashboard.html`, a pre-generated synthetic dashboard with a visible `Synthetic reviewer demo` banner. It does not require a full analysis build on first access.

## Optional features

OCR, ASR, original-video review, and live OpenAI-compatible model calls require optional model files or credentials. Their absence does not prevent the core synthetic reviewer dashboard from starting.

## Troubleshooting

### Database access denied

Check `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` in `.env.reviewer`. Do not point the reviewer demo at a production database.

### Dashboard generation fails

Run the application from the repository root. Confirm that `src/dashboard_gen/_unified_tpl.html` exists. Reviewer mode normally serves the committed snapshot immediately; a fresh non-reviewer dashboard build may take several minutes.

### Port already in use

Change `PORT` in `.env.reviewer` and use the same port in the verification URL.

### Optional short-video data are absent

The core reviewer dashboard still runs. To validate an available local short-video feature set:

```text
python scripts/verify_video_subset.py --repo-root . --json
```

If the optional files are absent, the command reports `status: skipped` and exits successfully. `--require-data` turns this into exit code 2.
