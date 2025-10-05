FROM python:3.12-alpine

# Install Docker CLI and Compose plugin
RUN apk add --no-cache docker-cli docker-cli-compose

WORKDIR /workspace

# Install test deps (pytest, httpx, requests, etc.) into a venv
COPY ./scripts/requirements.txt /tmp/requirements.txt
RUN python -m venv /venv \
    && . /venv/bin/activate \
    && pip install --no-cache-dir -r /tmp/requirements.txt

ENV PATH="/venv/bin:${PATH}"

# Default command runs integration tests; can be overridden
CMD ["pytest", "-q", "-m", "integration"]

