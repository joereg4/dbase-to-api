import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


def docker_available() -> bool:
    try:
        subprocess.run(["docker", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not docker_available(), reason="Docker not available")
def test_importer_creates_table_and_rows(tmp_path: Path):
    # Ensure clean data dir
    if DATA_DIR.exists():
        for f in DATA_DIR.glob("*.dbf"):
            f.unlink()
    else:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Prepare env and generate a tiny sample DBF via tools container (self-contained)
    env = os.environ.copy()
    env.pop("COMPOSE_FILE", None)
    subprocess.run(["docker", "compose", "run", "--rm", "tools", "python", "scripts/make_sample_dbf.py"], cwd=str(PROJECT_ROOT), check=True, env=env)
    assert any(DATA_DIR.glob("*.dbf")), "Expected a sample .dbf created in data/"

    # Bring up db and run importer as one-off
    env = os.environ.copy()
    # Ensure .env defaults if not present; importer uses DATABASE_URL pointing to service 'db'
    env.setdefault("POSTGRES_USER", "postgres")
    env.setdefault("POSTGRES_PASSWORD", "postgres")
    env.setdefault("POSTGRES_DB", "dbase")

    # Start db
    subprocess.run(["docker", "compose", "up", "-d", "db"], cwd=str(PROJECT_ROOT), check=True, env=env)
    # Wait a bit for health (compose healthcheck covers this, but give an extra buffer)
    subprocess.run(["sleep", "5"], check=True)

    # Run importer once
    subprocess.run(["docker", "compose", "run", "--rm", "importer"], cwd=str(PROJECT_ROOT), check=True, env=env)

    # Verify rows via psql inside the db container
    # We know the sample file is 'sample_people.dbf' -> table 'sample_people'
    check_sql = "SELECT COUNT(*) FROM sample_people;"
    cmd = [
        "docker", "exec", "-i", "dbase_pg",
        "psql", "-U", env["POSTGRES_USER"], "-d", env["POSTGRES_DB"], "-tAc", check_sql,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    count = int(result.stdout.strip())
    assert count >= 3

    # Teardown containers but keep volume for debugging; CI could prune if desired
    subprocess.run(["docker", "compose", "down"], cwd=str(PROJECT_ROOT), check=True, env=env)

