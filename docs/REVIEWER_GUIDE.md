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

## Option A: Docker (recommended)

This option does not require a separate Python or MySQL installation.

### Prerequisites

- Git
- Docker Desktop on Windows, or Docker Engine with the Compose plugin on Linux
- Docker must be running before the commands below are executed

Verify the installation:

```text
git --version
docker --version
docker compose version
```

All three commands must return a version number.

### Step 1. Clone the manuscript version

Open PowerShell, Terminal, or a Linux shell and run:

```text
git clone --branch v1.0 --depth 1 https://github.com/12312312358com/basinscope.git
cd basinscope
```

The `v1.0` tag corresponds to the version submitted with the manuscript.

### Step 2. Build and start the containers

From the `basinscope` directory:

```text
docker compose up --build -d
```

The first build may take several minutes because Docker downloads the Python and MySQL images and installs dependencies.

Check the container status:

```text
docker compose ps
```

The `db` and `app` containers should be shown as running. If the application container is still starting, wait one or two minutes and run the command again.

### Step 3. Check that the system is ready

Open these addresses in a browser:

```text
http://127.0.0.1:5001/healthz
http://127.0.0.1:5001/readyz
http://127.0.0.1:5001/page/dashboard
```

The expected `/readyz` response contains:

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

You can also check the endpoints from the terminal.

Windows PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:5001/healthz
Invoke-RestMethod http://127.0.0.1:5001/readyz
```

Linux:

```bash
curl http://127.0.0.1:5001/healthz
curl http://127.0.0.1:5001/readyz
```

### Step 4. Open the reviewer dashboard

Open the following address and select any of the 17 views from the left sidebar:

```text
http://127.0.0.1:5001/page/dashboard
```

The page should display a banner beginning with `Synthetic reviewer demo`. This indicates that the public synthetic reviewer data are loaded correctly. The demo is for startup and interface verification and does not reproduce the manuscript's research statistics.

### Step 5. If something fails

Inspect the logs:

```text
docker compose logs --tail=200
```

Inspect only the application logs:

```text
docker compose logs --tail=200 app
```

Common problems:

- `docker` is not recognized: Docker is not installed, or the terminal was opened before Docker installation completed. Reopen the terminal.
- Docker daemon is not running: start Docker Desktop or the Docker service.
- Port 5001 is already in use: stop the process using that port, or change the port mapping in `docker-compose.yml`.
- The first build is slow: wait several minutes and check `docker compose ps` again.
- The page remains unavailable: run `docker compose logs --tail=200 app` and report the error shown there.

### Step 6. Stop the reviewer system

When testing is complete, stop and remove the containers and reviewer database volume:

```text
docker compose down -v
```

To start the same reviewer system again later:

```text
docker compose up -d
```

## Option B: Local MySQL

This option requires a local Python and MySQL installation. If Docker is available, Option A is simpler.

### Prerequisites

- Python 3.10 or later
- MySQL 8.0 or later, installed and running
- A MySQL account with permission to create tables in the reviewer database
- Git

Check that Python and Git are available:

```text
python --version
git --version
```

On Linux, use `python3 --version` if `python` is not available.

### Step 1. Clone the manuscript version

```text
git clone --branch v1.0 --depth 1 https://github.com/12312312358com/basinscope.git
cd basinscope
```

### Step 2. Create the reviewer environment file

Windows PowerShell:

```powershell
Copy-Item .env.reviewer.example .env.reviewer
```

Linux:

```bash
cp .env.reviewer.example .env.reviewer
```

The file must be created in the repository root, in the same directory as `README.md` and `app.py`, not in `src/` or `scripts/`.

### Step 2a. Open the file in an editor

Windows PowerShell:

```powershell
notepad .env.reviewer
```

Linux:

```bash
nano .env.reviewer
```

If `notepad` is unavailable, open the repository folder in VS Code or any plain-text editor and select `.env.reviewer` directly.

### Step 2b. Enter the local MySQL connection values

Replace the example values with the values for your own MySQL installation:

```text
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-mysql-password
DB_NAME=db_weibo_basin_review
```

Field meanings:

- `DB_HOST=localhost`: MySQL is running on the same computer.
- `DB_PORT=3306`: the default MySQL port; keep it unless MySQL was configured to use another port.
- `DB_USER=root`: the MySQL user name; another account with the required privileges can also be used.
- `DB_PASSWORD=your-mysql-password`: replace this placeholder with the real MySQL password.
- `DB_NAME=db_weibo_basin_review`: the reviewer database name. Keep a name ending in `_review`.

Example: suppose your MySQL password is abc123456. Change only the DB_PASSWORD value. The complete file should then contain:

```text
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=abc123456
DB_NAME=db_weibo_basin_review
```

Rules for editing:

- Change only the text after `=`.
- Do not keep the literal `your-mysql-password` placeholder.
- Do not add spaces around `=`.
- If the password contains spaces or `#`, wrap it in quotes, for example `DB_PASSWORD="abc#123456"`.
- If the account has no password, use `DB_PASSWORD=` with nothing after the equals sign.
- Do not rename the variables.

Save the file and close the editor.

If a `.env` file also exists in the repository root, it takes precedence over `.env.reviewer`. Remove or rename `.env` when using the reviewer configuration.

### Step 2c. Confirm the values without exposing the password

In the editor, confirm that the file is saved as exactly `.env.reviewer` and is located in the repository root. You can list the file without printing its contents:

Windows PowerShell:

```powershell
Get-Item .env.reviewer
```

Linux:

```bash
ls -l .env.reviewer
```

After this step, continue with dependency installation and database initialization.

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

After activation, the `python` command should refer to the virtual environment interpreter.

### Step 4. Initialize the synthetic database

From the repository root:

```text
python scripts/init_demo_db.py
```

The initializer creates the database if the configured account has `CREATE` privilege. If the account cannot create databases, create it first as a MySQL administrator:

```text
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS db_weibo_basin_review CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
```

The initialization creates the required tables and loads the synthetic reviewer records. A successful run ends with output similar to:

```text
Review database ready: db_weibo_basin_review
t_basin_article=2430, t_basin_comment=140
```

### Step 5. Run preflight checks

```text
python scripts/doctor.py
python scripts/verify_reviewer_demo.py --repo-root . --json
```

Both commands must exit successfully. The doctor output should include:

```text
database=ok articles=2430 comments=140
REVIEW CHECK PASSED
```

The verifier output should end with:

```json
{"status": "passed"}
```

### Step 6. Start the application

Keep this terminal open and run:

```text
python app.py
```

The application should report that it is serving on port `5001`. If the port is already occupied, set a different `PORT` in `.env.reviewer`.

### Step 7. Verify the running system

Open in a browser:

```text
http://127.0.0.1:5001/healthz
http://127.0.0.1:5001/readyz
http://127.0.0.1:5001/page/dashboard
```

Expected `/readyz` response:

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

From another terminal in the activated environment, run:

```text
python scripts/verify_reviewer_demo.py --repo-root . --db --env-file .env.reviewer --url http://127.0.0.1:5001
```

This checks the local database and the three HTTP endpoints. The dashboard should display the `Synthetic reviewer demo` banner and allow access to all 17 views.

### Step 8. Stop or restart

Stop the application with `Ctrl+C` in the application terminal.

To start it again, activate the environment and run:

```text
python app.py
```

### Common problems

- `mysql` command not found: install the MySQL client/server and add its `bin` directory to `PATH`.
- `Access denied`: verify `DB_USER` and `DB_PASSWORD` in `.env.reviewer`.
- `Unknown database`: create `db_weibo_basin_review` with the administrator command in Step 4.
- Port already in use: change `PORT` in `.env.reviewer` and use the new port in the verification URL.
- Dashboard generation fails: run from the repository root and confirm `src/dashboard_gen/_unified_tpl.html` exists.
- The wrong database is used: verify that `.env` is absent, or that `.env` points to the intended reviewer database.
- Optional OCR/ASR/model features do not start: these require separate model files or API credentials and do not block the synthetic reviewer dashboard.

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
