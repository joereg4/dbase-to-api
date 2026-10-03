import logging
import os
import glob
import sys
from typing import Dict, Any, List

from dbfread import DBF
from sqlalchemy import create_engine, Table, Column, MetaData, text, types as satypes
from sqlalchemy.engine import Engine

try:
    from .naming import sanitize_table_name
except ImportError:
    from naming import sanitize_table_name


log = logging.getLogger("importer")

DBF_RECNO = "dbf_recno"


def get_dbf_encoding() -> str:
    return os.getenv("DBF_ENCODING", "latin-1")


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        # Fallback aligns with .env.example
        url = "postgresql+psycopg://postgres:postgres@db:5432/dbase"
    return url


def map_dbase_type(field) -> satypes.TypeEngine:
    ft = (field.type).upper()
    size = getattr(field, "length", None) or getattr(field, "size", None)
    deci = getattr(field, "decimal_count", None) or getattr(field, "decimal", 0) or 0

    if ft in ("N", "F"):
        # Whole-number dBASE fields can be up to 20 digits; only narrow
        # widths fit in INTEGER / BIGINT without overflow.
        if deci > 0 or not size:
            return satypes.Numeric(precision=size or 20, scale=deci)
        if size <= 9:
            return satypes.Integer()
        if size <= 18:
            return satypes.BigInteger()
        return satypes.Numeric(precision=size, scale=0)
    if ft == "D":
        return satypes.Date()
    if ft == "T":
        return satypes.DateTime()
    if ft == "L":
        return satypes.Boolean()
    if ft == "M":
        # Field length is the memo pointer width (usually 10), not text size.
        return satypes.Text()
    # Character fields and unrecognized types → VARCHAR
    return satypes.String(size or 255)


def deduplicate_column_name(name: str, seen: set[str]) -> str:
    candidate = name
    suffix = 2
    while candidate in seen:
        candidate = f"{name}_{suffix}"
        suffix += 1
    seen.add(candidate)
    return candidate


def infer_sqlalchemy_table_from_dbf(dbf: DBF, metadata: MetaData, table_name: str) -> Table:
    columns: List[Column] = []
    seen_names: set[str] = {DBF_RECNO}
    for f in dbf.fields:
        if f.name == "":
            continue
        coltype = map_dbase_type(f)
        colname = deduplicate_column_name(f.name.lower(), seen_names)
        columns.append(Column(colname, coltype))
    columns.append(Column(DBF_RECNO, satypes.Integer, primary_key=True))
    return Table(table_name, metadata, *columns)


def normalize_dbf_rows(rows: List[Dict[str, Any]], dbf: DBF) -> List[Dict[str, Any]]:
    seen_names: set[str] = {DBF_RECNO}
    name_map = {
        f.name: deduplicate_column_name(f.name.lower(), seen_names)
        for f in dbf.fields
        if f.name != ""
    }
    normalized: List[Dict[str, Any]] = []
    for i, row in enumerate(rows, start=1):
        mapped = {
            name_map.get(k, k.lower() if isinstance(k, str) else k): v for k, v in row.items()
        }
        mapped[DBF_RECNO] = i
        normalized.append(mapped)
    return normalized


def _warn_if_memo_missing(dbf: DBF, dbf_path: str) -> None:
    has_memo = any(getattr(f, "type", "").upper() == "M" for f in dbf.fields)
    if has_memo and getattr(dbf, "memo", None) is None:
        log.warning(
            "Memo file missing for %s; memo field values will be empty",
            dbf_path,
        )


def load_dbf_into_postgres(engine: Engine, dbf_path: str) -> None:
    basename = os.path.splitext(os.path.basename(dbf_path))[0]
    table_name = sanitize_table_name(basename)
    dbf = DBF(dbf_path, encoding=get_dbf_encoding(), ignore_missing_memofile=True)
    _warn_if_memo_missing(dbf, dbf_path)

    # Stage → rename keeps the live table if create/insert fails
    # (SQLite often does not roll back DDL).
    staging_name = f"{table_name}__loading"
    table = infer_sqlalchemy_table_from_dbf(dbf, MetaData(), staging_name)
    rows = normalize_dbf_rows([dict(r) for r in dbf], dbf)

    preparer = engine.dialect.identifier_preparer
    live = preparer.quote(table_name)
    staging = preparer.quote(staging_name)
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {staging}"))
        table.create(conn, checkfirst=False)
        if rows:
            conn.execute(table.insert(), rows)
        conn.execute(text(f"DROP TABLE IF EXISTS {live}"))
        conn.execute(text(f"ALTER TABLE {staging} RENAME TO {live}"))


def main() -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    engine = create_engine(get_database_url(), pool_pre_ping=True)
    dbf_paths = sorted(glob.glob("/data/**/*.dbf", recursive=True))

    if not dbf_paths:
        log.info("No .dbf files found in /data – importer will exit.")
        return 0

    failures: List[str] = []
    table_sources: Dict[str, str] = {}
    for path in dbf_paths:
        basename = os.path.splitext(os.path.basename(path))[0]
        table_name = sanitize_table_name(basename)
        if table_name in table_sources:
            log.error(
                "Table name collision: %s and %s both map to %r",
                table_sources[table_name],
                path,
                table_name,
            )
            failures.append(path)
            continue
        table_sources[table_name] = path
        log.info("Importing %s", path)
        try:
            load_dbf_into_postgres(engine, path)
            log.info("Done: %s", path)
        except Exception:
            # Keep going with other files, but record the failure so the
            # process exits non-zero and the traceback is visible for triage.
            failures.append(path)
            log.exception("Failed to import %s", path)

    if failures:
        log.error("Importer finished with %d failure(s): %s", len(failures), failures)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
