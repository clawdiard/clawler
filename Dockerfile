FROM python:3.12-slim

LABEL maintainer="Clawdia @ OpenClaw"
LABEL description="Clawler — Advanced news crawling service"

WORKDIR /app

# Install dependencies first for layer caching
COPY setup.py pyproject.toml README.md ./
COPY clawler/ clawler/
RUN pip install --no-cache-dir -e .

# Default: run clawler
ENTRYPOINT ["clawler"]
