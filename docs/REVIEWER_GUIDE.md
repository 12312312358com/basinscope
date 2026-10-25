# Reviewer Guide

This guide provides a reproducible reviewer path for the synthetic BasinScope demo. It does not require private platform records, API keys, local model weights, or original video files.

## What the demo verifies

The committed fixture contains only synthetic records. It verifies that:

- the Flask application starts;
- the required MySQL schema can be created;
- synthetic Weibo, Xiaohongshu, Zhihu, and Douyin records can be loaded;
- the Yellow River scope is selected correctly;
- the readiness endpoint sees the expected demo records;
- the dashboard can generate a non-empty HTML page;
- the fixture is deterministic and does not contain real platform URLs.

The demo does not reproduce the manuscript's research counts. Those counts come from platform records that cannot be redistributed. The purpose of the demo is to establish installability, data handling, scope selection, and output traceability.

## Docker path

```powershell
docker compose up --build
```

Open:

```text
http://127.0.0.1:5001/healthz
http://127.0.0.1:5001/readyz
http://127.0.0.1:5001/page/dashboard
```

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

6. Validate the fixture without starting the application:

```powershell
python scripts/verify_reviewer_demo.py --repo-root . --json
```

7. Start the application:

```powershell
python app.py
```

8. In another terminal, validate the database and HTTP endpoints:

```powershell
python scripts/verify_reviewer_demo.py --repo-root . --db --env-file .env.reviewer --url http://127.0.0.1:5001
```

## Expected fixture counts

The synthetic seed contains:

| Table | Total rows | Yellow River rows |
|---|---:|---:|
| `t_basin_article` | 210 | 120 |
| `t_basin_comment` | 210 | 120 |
| `t_xhs_article` | 70 | 50 |
| `t_xhs_comment` | 190 | 100 |
| `t_zhihu_article` | 70 | 50 |
| `t_zhihu_comment` | 190 | 100 |
| `t_douyin_article` | 18 | 12 |
| `t_douyin_comment` | 18 | 12 |

For `/readyz`, the expected counts are:

```json
{"article_count": 120, "comment_count": 120, "database": "ok"}
```

## Expected HTTP results

```text
/healthz          HTTP 200
/readyz           HTTP 200 and database=ok
/page/dashboard   HTTP 200 and HTML larger than 50 KB
```

## Optional features

Question answering, OCR, ASR, and original video features require their corresponding local models or API credentials. Their absence does not prevent the synthetic dashboard review path.

## Troubleshooting

### Database access denied

Check `DB_USER` and `DB_PASSWORD` in `.env.reviewer`. Do not use the production database for the reviewer demo.

### Dashboard generation fails

Run the application from the repository root and verify that `dashboard_gen/_unified_tpl.html` exists. The first dashboard request may take several minutes.

### Port already in use

Set `PORT` to another value in `.env.reviewer` and change the verification URL accordingly.
