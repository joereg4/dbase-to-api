import os
import subprocess
import time

import pytest
import requests

from tests.conftest import PROJECT_ROOT, compose_test_env


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


def _compose(*args: str, env: dict) -> None:
    subprocess.run(["docker", "compose", *args], cwd=str(PROJECT_ROOT), check=True, env=env)


@pytest.mark.integration
@pytest.mark.skipif(not docker_available(), reason="Docker not available")
def test_dynamic_api_endpoints_end_to_end():
    env = compose_test_env()

    _compose("run", "--rm", "tools", "python", "scripts/make_sample_dbf.py", env=env)
    _compose("up", "-d", "db", env=env)
    time.sleep(5)
    _compose("run", "--rm", "importer", env=env)
    _compose("up", "-d", "api", env=env)

    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    wait_for(f"{base_url}/health", timeout_seconds=45)

    r = requests.get(f"{base_url}/db/tables", timeout=5)
    r.raise_for_status()
    tables = r.json()
    assert isinstance(tables, list) and "sample_people" in tables

    r = requests.get(f"{base_url}/db/tables/sample_people/columns", timeout=5)
    r.raise_for_status()
    col_names = {c["name"] for c in r.json()}
    assert {"id", "name", "active"} <= col_names

    r = requests.get(f"{base_url}/db/tables/sample_people/rows?limit=2&offset=0", timeout=5)
    r.raise_for_status()
    payload = r.json()
    assert {"items", "limit", "offset", "count"} <= set(payload)
    assert payload["limit"] == 2 and payload["offset"] == 0
    assert payload["count"] >= 1 and len(payload["items"]) >= 1
    assert {"id", "name", "active", "dbf_recno"} <= set(payload["items"][0])

    r = requests.get(f"{base_url}/db/tables/sample_people/rows?name=Alpha", timeout=5)
    r.raise_for_status()
    filtered = r.json()
    assert filtered["count"] == 1
    assert filtered["items"][0]["name"] == "Alpha"

    r = requests.get(f"{base_url}/db/tables/sample_people/rows?id=1", timeout=5)
    r.raise_for_status()
    by_id = r.json()
    assert by_id["count"] == 1
    assert by_id["items"][0]["name"] == "Alpha"

    r = requests.get(f"{base_url}/db/tables/sample_people/rows?id=nope", timeout=5)
    assert r.status_code == 400
    recno = filtered["items"][0]["dbf_recno"]

    r = requests.get(f"{base_url}/db/tables/sample_people/rows/{recno}", timeout=5)
    r.raise_for_status()
    assert r.json()["name"] == "Alpha"

    assert requests.get(f"{base_url}/db/tables/does_not_exist/rows", timeout=5).status_code == 404
    assert (
        requests.get(f"{base_url}/db/tables/sample_people/rows/999999", timeout=5).status_code
        == 404
    )

    _compose("down", env=env)
