"""Shared pytest helpers."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def compose_test_env(base: dict | None = None) -> dict:
    """Build docker-compose env for integration tests from `.env.example` defaults."""
    env = dict(base or os.environ)
    env.pop("COMPOSE_FILE", None)
    example = PROJECT_ROOT / ".env.example"
    for line in example.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env.setdefault(key.strip(), value.strip())
    return env
