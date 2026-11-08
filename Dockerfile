FROM python:3.12-slim-bookworm

# Debian's bookworm build of Siege 4.0.7, available for amd64 and arm64.
RUN apt-get update \
    && apt-get install -y --no-install-recommends siege=4.0.7-1+b1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY main.py mock_api.py ./
COPY config/ config/
COPY utils/ utils/
COPY data/synthetic_locations.csv data/synthetic_locations.csv
COPY docker/run_demo.py docker/run_demo.py
CMD ["python", "mock_api.py", "--host", "0.0.0.0"]
