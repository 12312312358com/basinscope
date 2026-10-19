# Review database

`schema.sql` creates the eleven base tables required by the dashboard pipeline. `demo_seed.sql` then creates two synthetic safe-copy tables used by the compliance view. No platform records are included.

`demo_seed.sql` contains only synthetic records with `example.invalid` links. It is intended for reviewer smoke tests, not for research analysis.

For a local review database:

```powershell
Copy-Item .env.reviewer.example .env.reviewer
# Edit DB_PASSWORD and other values in .env.reviewer.
python scripts/init_demo_db.py
python scripts/doctor.py
python app.py
```

The check script refuses to reset a database named `db_weibo_basin` unless `--force` is explicitly supplied. Use `db_weibo_basin_review` for local testing.