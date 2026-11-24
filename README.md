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
- [Full application setup](docs/FULL_SETUP.md)
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

All commands below must be run from the repository root. Option A is recommended because it avoids Docker Desktop and WSL2 installation issues. Option B is optional and is tested by GitHub Actions when Docker is available.

### Clone the manuscript version

```text
git clone --branch v1.0 --depth 1 https://github.com/12312312358com/basinscope.git
cd basinscope
```

The `v1.0` tag corresponds to the submitted manuscript. Because this is an annotated tag, Git may print `is not a commit!` and report that the repository is in detached HEAD state. These messages are expected and do not indicate a failed clone. Confirm the checked-out version with:

```text
git describe --tags --exact-match
```

The expected output is `v1.0`.

## Option A: Local MySQL (recommended)

Use this option first. It does not depend on Docker Desktop, WSL2, or the Docker Engine, and it requires only Python 3.10+ and MySQL 8.0+.

### Step 1. Check Python and Git

```text
python --version
git --version
```

On Linux, use `python3 --version` if `python` is unavailable.

### Step 2. Create and edit the reviewer environment file

1. Create `.env.reviewer` from the example file.

Windows PowerShell:

```powershell
Copy-Item .env.reviewer.example .env.reviewer
```

Linux:

```bash
cp .env.reviewer.example .env.reviewer
```

2. Open the new file in a plain-text editor.

Windows PowerShell:

```powershell
notepad .env.reviewer
```

Linux:

```bash
nano .env.reviewer
```

3. In most cases, only the database password needs to be changed. Keep the other values unless your MySQL installation uses a different host, port, user, or database name:

```text
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=replace-with-your-database-password
DB_NAME=db_weibo_basin_review
```

For example, suppose the MySQL password is abc123456. The file should then contain:

```text
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=abc123456
DB_NAME=db_weibo_basin_review
```

If the password contains spaces or `#`, wrap it in quotes. If the account has no password, use `DB_PASSWORD=` with nothing after it.

4. Save the file and close the editor. Confirm that `.env.reviewer` is in the repository root.

Windows PowerShell:

```powershell
Get-Item .env.reviewer
```

Linux:

```bash
ls -l .env.reviewer
```

### Step 3. Install the reviewer dependencies

The commands below call the virtual environment's Python directly. This avoids Windows PowerShell execution-policy errors caused by `Activate.ps1`.

Windows PowerShell:

```powershell
python -m venv .venv-review
.\.venv-review\Scripts\python.exe -m pip install -r requirements-review.txt
```

Linux:

```bash
python3 -m venv .venv-review
.venv-review/bin/python -m pip install -r requirements-review.txt
```

Do not use a bare `pip` or `python` command after this step. Use the virtual environment commands shown below.

### Step 4. Initialize the reviewer database

Windows PowerShell:

```powershell
.\.venv-review\Scripts\python.exe scripts/init_demo_db.py
```

Linux:

```bash
.venv-review/bin/python scripts/init_demo_db.py
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

These counts cover the full synthetic basin tables. The reviewer dashboard and `/readyz` check are restricted to the Yellow River scope, which contains 1,097 articles and 59 comments. This scope difference explains why the initialization count and the `/readyz` count are not identical.

### Step 5. Run preflight checks

Windows PowerShell:

```powershell
.\.venv-review\Scripts\python.exe scripts/doctor.py
.\.venv-review\Scripts\python.exe scripts/verify_reviewer_demo.py --repo-root . --json
```

Linux:

```bash
.venv-review/bin/python scripts/doctor.py
.venv-review/bin/python scripts/verify_reviewer_demo.py --repo-root . --json
```

Both commands must exit successfully.

### Step 6. Start the application

Keep the terminal open and run:

Windows PowerShell:

```powershell
.\.venv-review\Scripts\python.exe app.py
```

Linux:

```bash
.venv-review/bin/python app.py
```

Open:

```text
http://127.0.0.1:5001/page/dashboard
```

Optional verification: in another terminal, run:

Windows PowerShell:

```powershell
.\.venv-review\Scripts\python.exe scripts/verify_reviewer_demo.py --repo-root . --db --env-file .env.reviewer --url http://127.0.0.1:5001
```

Linux:

```bash
.venv-review/bin/python scripts/verify_reviewer_demo.py --repo-root . --db --env-file .env.reviewer --url http://127.0.0.1:5001
```

This command is not required to start the system. It only checks the running database and HTTP endpoints. If the dashboard opens and `/readyz` reports the expected values, the system is already working.

The expected `/readyz` values are the same as in Option B.

### Step 7. Stop or restart

Stop the application with `Ctrl+C`. To start it again, use the same command from Step 6:

Windows PowerShell:

```powershell
.\.venv-review\Scripts\python.exe app.py
```

Linux:

```bash
.venv-review/bin/python app.py
```

### Common local MySQL problems

- `mysql` not found: install the MySQL client/server and add its `bin` directory to `PATH`.
- `Access denied`: check `DB_USER` and `DB_PASSWORD` in `.env.reviewer`.
- Unknown database: run the administrator database-creation command from Step 4.
- Port in use: change `PORT` in `.env.reviewer` and update the verification URL.
- Dashboard generation fails: confirm that `src/dashboard_gen/_unified_tpl.html` exists.
- Wrong database used: remove or rename `.env` when using `.env.reviewer`.


## Option B: Docker (optional)

Use this option only when Docker Desktop or Docker Engine is already working. No separate Python or MySQL installation is required. The repository's GitHub Actions workflow builds and tests this same Docker stack, but a local Docker installation problem (for example, WSL2 or virtualization) must be resolved on the reviewer's computer first.

### Step 1. Check Docker

Start Docker Desktop or the Docker service, then run:

```text
docker --version
docker compose version
docker info
```

All three commands must succeed. `docker info` must show a `Server Version`; this confirms that the Docker Engine is running. A successful `docker --version` alone is not enough.

If `docker info` returns `500 Internal Server Error`, `Cannot connect to the Docker daemon`, or a message containing `dockerDesktopLinuxEngine/_ping`, stop and fix Docker first. On Windows, start Docker Desktop and wait until it shows `Engine running`; Docker Desktop requires WSL2 and hardware virtualization to be enabled.

### Step 2. Validate, build, and start the system

```text
docker compose config
docker compose up --build -d
```

The first command validates `docker-compose.yml` without starting any container.

The first build may take several minutes while Docker downloads the required images.

Check the container status:

```text
docker compose ps
```

The `db` and `app` containers should be running. When the application is ready, `app` should be reported as `healthy`.

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

- `docker info` must succeed and show a `Server Version`.
- On Windows, Docker Desktop must show `Engine running`; enable WSL2 and hardware virtualization if it does not.
- Port `5001` must not be occupied by another application.
- Wait until the database and application health checks have completed.
- If the error contains `dockerDesktopLinuxEngine/_ping`, the Docker Engine is unavailable; `docker compose up` cannot start the project until that error is fixed.

### Step 5. Stop and clean up

```text
docker compose down -v
```

The Docker path is optional. If Docker cannot be made operational on the reviewer's computer, use Option A instead.

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
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

For development and browser tests:

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install
```

Linux:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m playwright install
```

## Full application setup

For a full local deployment using lawfully collected data and optional API services, see [docs/FULL_SETUP.md](docs/FULL_SETUP.md). The reviewer quick start above does not require this configuration.

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

Start the standalone Yellow River service.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe app.py
```

Linux:

```bash
.venv/bin/python app.py
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
