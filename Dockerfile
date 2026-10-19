FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5001

WORKDIR /app
COPY requirements-review.txt .
RUN pip install --no-cache-dir -r requirements-review.txt
COPY . .

EXPOSE 5001
CMD ["python", "app.py"]