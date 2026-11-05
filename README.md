# SOPRAS

SOPRAS is a standalone Flask application for public-opinion analysis of ecological governance, cultural tourism, and healthcare disputes in the Yellow River Basin.

The software integrates topic-targeted acquisition, desensitized multi-source storage, Chinese-language text analytics, event monitoring, rule-based risk screening, cross-platform comment clustering, interactive visualization, and short-video analysis.

## Scope

This repository implements the Yellow River module only. The dashboard is restricted to the 17 `hh-*` views and their supporting acquisition, storage, analytical, and visualization components.

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

The repository includes a schema-only database and synthetic demo data for reviewers. The demo has no platform records, private identifiers, API keys, or model weights.

With Docker:

```powershell
docker compose up --build
```

Open:

```text
http://127.0.0.1:5001/healthz
http://127.0.0.1:5001/readyz
http://127.0.0.1:5001/page/dashboard
```

Without Docker, follow [docs/REVIEWER_GUIDE.md](docs/REVIEWER_GUIDE.md):

```powershell
Copy-Item .env.reviewer.example .env.reviewer
# Set DB_PASSWORD and other local values in .env.reviewer.
python -m venv .venv-review
.\.venv-review\Scripts\Activate.ps1
pip install -r requirements-review.txt
python scripts/init_demo_db.py
python scripts/doctor.py
python app.py
```


The application automatically loads `.env.reviewer` when no `.env` file is present.

`/healthz` checks that Flask is running. `/readyz` also checks the database, required tables, and demo data.
## Requirements

- Windows 10/11 or Linux.
- Python 3.10 or later.
- MySQL 8.0 or later.
- 16 GB RAM recommended for the complete local-model and video-processing stack.
- Optional CUDA GPU.
- ffmpeg or the bundled `imageio-ffmpeg` package for audio processing.
- Optional OpenAI-compatible credentials for language and vision services.

Install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For development and browser tests:

```powershell
pip install -r requirements-dev.txt
python -m playwright install
```

## Configuration

Copy the example environment file:

```powershell
Copy-Item .env.example .env
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

The manuscript corresponds to the annotated tag `v0.1.5`. Release archives
exclude raw platform records, model weights, runtime logs, uploads, and
credentials. See `CHANGELOG.md` and `docs/SOFTWAREX_RELEASE_CHECKLIST.md`.

## Citation

If you use this software, cite the repository and the associated SoftwareX manuscript when available. See `CITATION.cff`.

## License

MIT License. See `LICENCE.txt`.

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
