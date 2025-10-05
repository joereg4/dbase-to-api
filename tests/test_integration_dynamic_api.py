import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )
        return True
    except Exception:
        return False


def wait_for(url: str, timeout_seconds: int = 30) -> None:
    deadline = time.time() + timeout_seconds
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return
        except Exception as e:
            last_err = e
        time.sleep(1)
    raise AssertionError(f"Service at {url} did not become ready: {last_err}")


@pytest.mark.integration
@pytest.mark.skipif(not docker_available(), reason="Docker not available")
def test_dynamic_api_endpoints_end_to_end():
    env = os.environ.copy()
    # Ensure compose inside container uses mounted /workspace compose file
    env.pop("COMPOSE_FILE", None)
    env.setdefault("POSTGRES_USER", "postgres")
    env.setdefault("POSTGRES_PASSWORD", "postgres")
    env.setdefault("POSTGRES_DB", "dbase")

    # Ensure a sample DBF exists via tools container
    subprocess.run(
        ["docker", "compose", "run", "--rm", "tools", "python", "scripts/make_sample_dbf.py"],
        cwd=str(PROJECT_ROOT),
        check=True,
        env=env,
    )

    # Start db
    subprocess.run(
        ["docker", "compose", "up", "-d", "db"], cwd=str(PROJECT_ROOT), check=True, env=env
    )
    time.sleep(5)

    # Run importer one-off
    subprocess.run(
        ["docker", "compose", "run", "--rm", "importer"], cwd=str(PROJECT_ROOT), check=True, env=env
    )

    # Start API
    subprocess.run(
        ["docker", "compose", "up", "-d", "api"], cwd=str(PROJECT_ROOT), check=True, env=env
    )

    # Determine base URL for API (inside Docker use service DNS)
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    # Wait for health
    wait_for(f"{base_url}/health", timeout_seconds=45)

    # List tables
    r = requests.get(f"{base_url}/db/tables", timeout=5)
    r.raise_for_status()
    tables = r.json()
    assert isinstance(tables, list) and len(tables) >= 1
    assert "sample_people" in tables

    # Columns
    r = requests.get(f"{base_url}/db/tables/sample_people/columns", timeout=5)
    r.raise_for_status()
    cols = r.json()
    col_names = [c["name"] for c in cols]
    for expected in ["id", "name", "active"]:
        assert expected in col_names

    # Rows
    r = requests.get(f"{base_url}/db/tables/sample_people/rows?limit=2&offset=0", timeout=5)
    r.raise_for_status()
    rows = r.json()
    assert isinstance(rows, list) and len(rows) >= 1
    assert set(rows[0].keys()).issuperset({"id", "name", "active"})

    # 404 for a missing table
    r = requests.get(f"{base_url}/db/tables/does_not_exist/rows", timeout=5)
    assert r.status_code == 404

    # Teardown API (keep db up for debug if needed)
    subprocess.run(["docker", "compose", "down"], cwd=str(PROJECT_ROOT), check=True, env=env)
