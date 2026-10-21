# Architecture

BasinScope is a standalone Flask application with four connected parts.

## Acquisition

Platform adapters in `spider/` collect topic-targeted records from Weibo,
Xiaohongshu, Zhihu, and Douyin. Browser-based collection uses DrissionPage.

## Storage

MySQL stores platform-specific article and comment tables, along with basin and
topic labels, interaction metrics, geographic fields, event matches, and derived
video features. Raw records and database dumps are not included in the
repository.

## Analysis

Scripts in `dashboard_gen/` and `service/` clean records, segment Chinese text,
match event dictionaries, score sentiment, cluster comments, calculate risk
indicators, and prepare dashboard products. The data-generation pipeline records
dependencies and cache lifetimes.

## Presentation and interaction

`app.py` serves the dashboard and the question-answering endpoint. Interface
assets are organized under `templates/`, `static/`, and `view/`. Optional English
labels are provided by `static/js/basinscope-i18n.js`.

## Main source directories

| Path | Purpose |
|---|---|
| `app.py` | Flask entry point |
| `spider/` | Platform collectors and collection utilities |
| `dashboard_gen/` | Analytical products and dashboard generation |
| `service/` | Question answering, report generation, and video workflows |
| `dao/`, `entity/`, `util/` | Database access, models, and shared utilities |
| `view/`, `templates/`, `static/` | Pages, templates, and front-end assets |
| `docs/` | Setup, methods, architecture, and release documentation |
