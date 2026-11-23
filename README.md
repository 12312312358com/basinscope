# SOPRAS

SOPRAS is a standalone Flask application for public-opinion analysis of ecological governance, cultural tourism, and healthcare disputes in the Yellow River Basin.

The software integrates topic-targeted acquisition, desensitized multi-source storage, Chinese-language text analytics, event monitoring, rule-based risk screening, cross-platform comment clustering, interactive visualization, and short-video analysis.

Public GitHub repository: https://github.com/12312312358com/basinscope

## Scope

This repository provides the Yellow River reference configuration. The dashboard is restricted to the 17 `hh-*` views and their supporting acquisition, storage, analytical, and visualization components. Platform connectors, topic and event dictionaries, and risk thresholds are configurable without modifying the core implementation; applying SOPRAS to another basin or domain requires supplying the corresponding data and configuration.

## Main features

- Topic-targeted collection from Weibo, Xiaohongshu, Zhihu, and Douyin adapters.
- Separate article and comment tables for each text platform.
- Author identifiers and personal information masking or hashing during ingestion.
- jieba Chinese word segmentation and event-cluster matching.
- SnowNLP baseline sentiment analysis with a calibration view.
- TF-IDF and K-means exploratory comment clustering.
- Four-factor rule-based risk screening with an explicit sample gate.
- Interactive dashboard with overview, topic, comment, propagation, event, risk, calibration, and method views.
- Three-layer short-video analysis: metadata, keyframes, and in-memory ASR.
- No original video or audio retention and no face, voiceprint, or speaker recognition.

## Architecture

The application uses four layers:

1. **Acquisition**: platform-specific collectors in `src/spider/`.
2. **Storage**: MySQL article and comment tables organized by platform.
3. **Analytics**: data-generation and analysis scripts in `src/dashboard_gen/` and `src/service/`.
4. **Presentation**: a Flask application in `app.py` serving the generated dashboard.

The data-generation pipeline is dependency-aware and uses stale-while-revalidate caching. Each product has an explicit dependency and cache lifetime, as defined in `src/service/dashboard.py`.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Data setup](docs/DATA_SETUP.md)
- [Methods](docs/METHODS.md)
- [Reproducibility](docs/REPRODUCIBILITY.md)
- [SoftwareX metadata](docs/SOFTWARE_METADATA.md)
- [SoftwareX release checklist](docs/SOFTWAREX_RELEASE_CHECKLIST.md)
- [Changelog](CHANGELOG.md)

## Repository layout

| Path | Purpose |
|---|---|
| `app.py` | Root compatibility launcher for the application |
| `src/app.py` | Flask application entry point |
| `src/spider/` | Platform collection adapters and collection utilities |
| `src/dashboard_gen/` | Analytical data products and dashboard generation |
| `src/service/` | Reports and video workflows |
| `src/dao/`, `src/entity/`, `src/util/` | Database access, domain models, and shared utilities |
| `src/view/`, `src/templates/`, `src/static/` | Server-rendered pages and front-end assets |
| `docs/` | Architecture, methods, reproducibility, and release documentation |
| `scripts/`, `sql/`, `tests/` | Reviewer utilities, database fixtures, and automated tests |

## Reviewer quick start

All commands below must be run from the repository root.

### Clone the manuscript version

```text
git clone --branch v1.0 --depth 1 https://github.com/12312312358com/basinscope.git
cd basinscope
```

The `v1.0` tag corresponds to the submitted manuscript.

## Option A: Docker (recommended)

Use this option if Docker Desktop or Docker Engine is installed. No separate Python or MySQL installation is required.

### Step 1. Check Docker

Start Docker Desktop or the Docker service, then run:

```text
docker --version
docker compose version
```

Both commands must return a version number.

### Step 2. Build and start the system

```text
docker compose up --build -d
```

The first build may take several minutes while Docker downloads the required images.

Check the container status:

```text
docker compose ps
```

The `db` and `app` containers should be running.

### Step 3. Verify the system

Open in a browser:

```text
http://127.0.0.1:5001/healthz
http://127.0.0.1:5001/readyz
http://127.0.0.1:5001/page/dashboard
```

The expected `/readyz` result is:

```json
{
  "article_count": 1097,
  "comment_count": 59,
  "database": "ok",
  "scope": "yellow-river",
  "status": "ok",
  "tables": 13
}
```

The dashboard should display the `Synthetic reviewer demo` banner and all 17 views.

### Step 4. If the containers do not start

Inspect the logs:

```text
docker compose logs --tail=200
docker compose logs --tail=200 app
```

Common checks:

- Docker Desktop or the Docker service must be running.
- Port `5001` must not be occupied by another application.
- Wait until the database health check has completed.

### Step 5. Stop and clean up

```text
docker compose down -v
```

## Option B: Local MySQL

Use this option only if Docker is unavailable. It requires Python 3.10+ and MySQL 8.0+.

### Step 1. Check Python and Git

```text
python --version
git --version
```

On Linux, use `python3 --version` if `python` is unavailable.

### Step 2. Create and edit the reviewer environment file

Windows PowerShell:

```powershell
Copy-Item .env.reviewer.example .env.reviewer
notepad .env.reviewer
```

Linux:

```bash
cp .env.reviewer.example .env.reviewer
nano .env.reviewer
```

The file must be in the repository root, beside `README.md` and `app.py`. Enter the local MySQL settings:

```text
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-mysql-password
DB_NAME=db_weibo_basin_review
```

Replace `your-mysql-password` with the actual password for the local MySQL account. Do not keep that placeholder. Do not add spaces around the equals signs.

Example: suppose the MySQL password is abc123456. The file should then contain:

```text
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=abc123456
DB_NAME=db_weibo_basin_review
```

If the password contains spaces or `#`, wrap it in quotes. If the account has no password, use `DB_PASSWORD=` with nothing after it.

Keep `DB_NAME` ending in `_review`. If a `.env` file also exists, it takes precedence over `.env.reviewer`.

### Step 3. Install the reviewer dependencies

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

### Step 4. Initialize the reviewer database

```text
python scripts/init_demo_db.py
```

If the configured MySQL account cannot create databases, create it first as an administrator:

```text
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS db_weibo_basin_review CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
```

A successful initialization ends with output similar to:

```text
Review database ready: db_weibo_basin_review
t_basin_article=2430, t_basin_comment=140
```

### Step 5. Run preflight checks

```text
python scripts/doctor.py
python scripts/verify_reviewer_demo.py --repo-root . --json
```

Both commands must exit successfully.

### Step 6. Start the application

Keep the terminal open and run:

```text
python app.py
```

Open:

```text
http://127.0.0.1:5001/page/dashboard
```

In another activated terminal, run:

```text
python scripts/verify_reviewer_demo.py --repo-root . --db --env-file .env.reviewer --url http://127.0.0.1:5001
```

The expected `/readyz` values are the same as in Option A.

### Step 7. Stop or restart

Stop the application with `Ctrl+C`. To start it again, reactivate the environment and run:

```text
python app.py
```

### Common local MySQL problems

- `mysql` not found: install the MySQL client/server and add its `bin` directory to `PATH`.
- `Access denied`: check `DB_USER` and `DB_PASSWORD` in `.env.reviewer`.
- Unknown database: run the administrator database-creation command from Step 4.
- Port in use: change `PORT` in `.env.reviewer` and update the verification URL.
- Dashboard generation fails: confirm that `src/dashboard_gen/_unified_tpl.html` exists.
- Wrong database used: remove or rename `.env` when using `.env.reviewer`.

## Reviewer data note

The public reviewer profile is synthetic. It contains no private platform records and does not reproduce the manuscript's research estimates. Its purpose is to verify installation, database setup, dashboard rendering, and the 17 analysis views.

## Requirements

- Windows 10/11 or Linux.
- Python 3.10 or later.
- MySQL 8.0 or later.
- 16 GB RAM recommended for the complete local-model and video-processing stack.
- Optional CUDA GPU.
- ffmpeg or the bundled `imageio-ffmpeg` package for audio processing.
- Optional OpenAI-compatible credentials for language and vision services.

Install dependencies.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For development and browser tests:

```powershell
pip install -r requirements-dev.txt
python -m playwright install
```

## Full application configuration (not reviewer demo)

This section applies to a normal local/full installation that uses `.env`. It does not apply to Option A or Option B of the reviewer quick start:

- Option A uses Docker and requires no `.env` file.
- Option B uses `.env.reviewer` for the synthetic reviewer database.
- This section uses `.env` for the full application, including database and optional API credentials.

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

## Database

The analytical pipeline expects MySQL tables including:

```text
t_basin_article
t_basin_comment
t_xhs_article
t_xhs_comment
t_zhihu_article
t_zhihu_comment
t_douyin_article
t_douyin_comment
```

The public repository does not include raw platform records, unredacted user data, database dumps, or API credentials. Provide your own lawfully collected and desensitized data. See `docs/DATA_SETUP.md`.

## Model assets

The video pipeline may use local model assets. Model weights are intentionally excluded from Git.

Expected local locations include:

```text
models/whisper/small
```

Install or download the corresponding models according to their licenses and the runtime configuration.

## Running the application

Start the standalone Yellow River service:

```powershell
python app.py
```

Default address:

```text
http://127.0.0.1:5001/page/dashboard
```

Health check:

```text
http://127.0.0.1:5001/healthz
```

Windows launcher:

```powershell
.\start.ps1
```

## Dashboard generation

Individual products can be regenerated with the scripts in `src/dashboard_gen/`. The main sequence is:

```text
build_hotword_data.py
build_sentiment_data.py
build_ip_data.py
build_feature_data.py
build_unified_data.py
build_basin_data.py
build_video_data.py
build_video_page.py
build_video_topic_data.py
build_jinan_map.py
build_unified_page.py
```

The final standalone output is:

```text
src/dashboard_gen/SOPRAS-黄河流域舆情.html
```

## Data-processing methods

- **Text tokenization**: jieba with stop-word and invalid-fragment filtering.
- **Event monitoring**: human-readable event dictionaries with explicit overlap warnings.
- **Sentiment**: SnowNLP baseline plus polarity-dictionary calibration.
- **Opinion clustering**: TF-IDF keyword bags followed by K-means.
- **Risk screening**: transparent expert-defined weights based on negative share, event volume, official-subject sensitivity, and diffusion.
- **Cross-platform comparison**: structural proportions only, not absolute interaction totals.

## Important limitations

- The current basin-specific Weibo comment table is below the clustering threshold.
- Cross-platform text coverage is incomplete for cultural tourism.
- SnowNLP is not calibrated for the current domain corpus.
- Temporal patterns are affected by acquisition time and quotas.
- Risk weights are expert-defined and have not been statistically validated.
- The video sample is non-random and covers Douyin only.

These limitations are displayed in the dashboard and should be preserved in downstream reports and publications.

## Privacy and compliance

Do not commit API keys, database passwords, raw platform responses, unredacted user identifiers, sensitive personal information, or model credentials. Verify that data collection and reuse comply with platform terms, applicable law, institutional policy, and research ethics requirements.

## Versioning and releases

The manuscript corresponds to the annotated tag `v1.0`. Release archives
exclude raw platform records, model weights, runtime logs, uploads, and
credentials. See `CHANGELOG.md` and `docs/SOFTWAREX_RELEASE_CHECKLIST.md`.

## Citation

If you use this software, cite the repository and the associated SoftwareX manuscript when available. See `CITATION.cff`.

## License

MIT License. See `LICENSE.txt`.

## Contact

Maintainer: Wujun Long
Email: 2715469798@qq.com

## English UI mode

The dashboard includes an optional English interface mode:

```text
http://127.0.0.1:5001/page/dashboard?lang=en
```

An `EN` / `中文` switch is also added to the top toolbar.

The translation layers are implemented in:

```text
src/static/js/basinscope-i18n.js
src/static/js/signaltrace-ui-en.js
```

It translates navigation, view titles, KPI labels, card titles, chart labels, legends, table headers, risk levels, and common interface terms before the dashboard is rendered.

Original platform posts, comments, article titles, and other source-language content are intentionally not rewritten. This preserves the original evidence and avoids changing data meaning during translation. For publication screenshots, crop or mask source-language passages where necessary.
