import io
import os
import zipfile
from pathlib import Path

import requests


NATURAL_EARTH_URLS = [
    # Use the NACIS CDN (current, stable)
    (
        "ne_10m_admin_0_countries",
        "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip",
    ),
    (
        "ne_10m_populated_places",
        "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_populated_places.zip",
    ),
]


def ensure_data_dir() -> Path:
    data_dir = Path(__file__).resolve().parents[1] / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def download_and_extract_dbf(name: str, url: str, outdir: Path) -> None:
    print(f"Downloading {name} from {url} ...")
    r = requests.get(url, timeout=60, headers={"User-Agent": "curl/8 dbase-to-api"})
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for member in z.namelist():
            if member.lower().endswith(".dbf"):
                target = outdir / f"{name}.dbf"
                print(f"Extracting {member} -> {target}")
                with z.open(member) as src, open(target, "wb") as dst:
                    dst.write(src.read())


def main() -> None:
    outdir = ensure_data_dir()
    for name, url in NATURAL_EARTH_URLS:
        try:
            download_and_extract_dbf(name, url, outdir)
        except Exception as exc:
            print(f"Failed to fetch {name}: {exc}")


if __name__ == "__main__":
    main()
