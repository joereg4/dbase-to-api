import os
import glob
from typing import Dict, Any, List

from dbfread import DBF
from sqlalchemy import create_engine, Table, Column, MetaData, types as satypes
from sqlalchemy.engine import Engine


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        # Fallback aligns with .env.example
        url = "postgresql+psycopg://postgres:postgres@db:5432/dbase"
    return url


def map_dbase_type(field) -> satypes.TypeEngine:
    ft = (field.type).upper()
    size = getattr(field, "length", None) or getattr(field, "size", None)
    deci = getattr(field, "decimal_count", None) or getattr(field, "decimal", 0)

    if ft in ("N", "F"):
        # Numeric/Float
        if deci and deci > 0:
            return satypes.Numeric(precision=size or 18, scale=deci)
        return satypes.Integer()
    if ft == "D":
        return satypes.Date()
    if ft == "T":
        return satypes.DateTime()
    if ft == "L":
        return satypes.Boolean()
    # Default to text
    length = size or 255
    return satypes.String(length)


def infer_sqlalchemy_table_from_dbf(dbf: DBF, metadata: MetaData, table_name: str) -> Table:
    columns: List[Column] = []
    for f in dbf.fields:
        if f.name == "":
            continue
        coltype = map_dbase_type(f)
        colname = f.name.lower()
        columns.append(Column(colname, coltype))
    return Table(table_name, metadata, *columns)


def load_dbf_into_postgres(engine: Engine, dbf_path: str) -> None:
    table_name = os.path.splitext(os.path.basename(dbf_path))[0].lower()
    dbf = DBF(dbf_path, encoding="latin-1", ignore_missing_memofile=True)

    metadata = MetaData()
    table = infer_sqlalchemy_table_from_dbf(dbf, metadata, table_name)
    metadata.create_all(engine, tables=[table])

    rows = [dict(r) for r in dbf]
    # Normalize keys to lowercase to match created columns
    rows = [{(k.lower() if isinstance(k, str) else k): v for k, v in r.items()} for r in rows]

    if not rows:
        return

    with engine.begin() as conn:
        conn.execute(table.insert(), rows)


def main() -> None:
    engine = create_engine(get_database_url(), pool_pre_ping=True)
    dbf_paths = glob.glob("/data/*.dbf")

    if not dbf_paths:
        print("No .dbf files found in /data – importer will exit.")
        return

    for path in dbf_paths:
        print(f"Importing {path} ...")
        try:
            load_dbf_into_postgres(engine, path)
            print(f"Done: {path}")
        except Exception as exc:
            # Keep going with other files
            print(f"Failed to import {path}: {exc}")


if __name__ == "__main__":
    main()

