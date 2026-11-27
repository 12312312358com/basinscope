# Docker Setup

Docker is an optional alternative to the MySQL quick start in the repository README. Use it only when Docker Desktop or the Docker Engine is already working.

## 1. Check Docker

Start Docker Desktop and wait until it reports `Engine running`, then run:

```text
docker --version
docker compose version
docker info
```

`docker info` must show a `Server Version`. If it returns a 500 error or a message containing `dockerDesktopLinuxEngine/_ping`, fix the Docker/WSL2 environment before continuing.

## 2. Build and start

```text
docker compose config
docker compose up --build -d
docker compose ps
```

The `db` and `app` containers should be running, and `app` should become `healthy`.

## 3. Verify

Open:

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

## 4. Troubleshooting

Inspect logs:

```text
docker compose logs --tail=200
docker compose logs --tail=200 app
```

If the containers do not start, confirm that Docker Engine is running and that port `5001` is free.

Stop the stack with:

```text
docker compose down -v
```
