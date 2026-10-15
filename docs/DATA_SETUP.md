# Data Setup

This repository does not include raw platform data or database dumps.

## Required MySQL tables

The dashboard and analytical pipeline use platform-specific article and comment tables:

- `t_basin_article`
- `t_basin_comment`
- `t_xhs_article`
- `t_xhs_comment`
- `t_zhihu_article`
- `t_zhihu_comment`
- `t_douyin_article`
- `t_douyin_comment`

The main fields expected by the analytical code include:

- Article identifier and content ID.
- Article text.
- Like, comment, repost, favourite, and share counts.
- Publication time and collection time.
- Author identifier, nickname, gender, and profile fields.
- Author location or platform-reported region.
- Basin label.
- Topic label.
- Target province.
- Matched keyword or source keyword.

## Data governance

Users are responsible for ensuring that all data collection, storage, processing, and redistribution comply with platform terms, applicable law, institutional rules, and research ethics requirements.

Raw platform responses and identifiers must not be committed to Git. Use hashing or masking for person-related fields before use.

## Reproducing the Yellow River snapshot

1. Configure `.env`.
2. Import lawfully collected data into the required MySQL tables.
3. Run the data-generation pipeline described in `README.md`.
4. Start `app.py` and verify the `/healthz` endpoint.
5. Inspect the dashboard for missing-data warnings and sample gates before interpreting results.
