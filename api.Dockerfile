FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ ./src/

RUN pip install --no-cache-dir .

ENV PYTHONPATH=/app/src
EXPOSE 8000

CMD ["uvicorn", "semanticgraph.adapters.inbound.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
