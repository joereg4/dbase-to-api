from pathlib import Path

from dbf import Table, READ_WRITE


def ensure_data_dir() -> Path:
    data_dir = Path(__file__).resolve().parents[1] / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def create_sample_dbf(path: Path) -> None:
    # Very small sample using field spec string
    # id N(4), name C(20), active L
    table = Table(str(path), "id N(4,0); name C(20); active L")
    table.open(mode=READ_WRITE)
    try:
        table.append((1, "Alpha", True))
        table.append((2, "Beta", False))
        table.append((3, "Gamma", True))
    finally:
        table.close()


def main() -> None:
    data_dir = ensure_data_dir()
    out = data_dir / "sample_people.dbf"
    create_sample_dbf(out)
    print(f"Wrote sample DBF: {out}")


if __name__ == "__main__":
    main()

