import logging
import os
import glob
import sys
from typing import Dict, Any, List

from dbfread import DBF
from sqlalchemy import create_engine, Table, Column, MetaData, text, types as satypes
from sqlalchemy.engine import Engine

try:
    from .naming import LIVE_SCHEMA, STAGING_SCHEMA, sanitize_table_name
except ImportError:
    from naming import LIVE_SCHEMA, STAGING_SCHEMA, sanitize_table_name


log = logging.getLogger("importer")

DBF_RECNO = "dbf_recno"
# Visual FoxPro stores type B as an IEEE double. Other versions store a memo pointer.
_VFP_DOUBLE_VERSIONS = frozenset({0x30, 0x31, 0x32})


def get_dbf_encoding() -> str:
    return os.getenv("DBF_ENCODING", "latin-1")


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        # Fallback aligns with .env.example
        url = "postgresql+psycopg://postgres:postgres@db:5432/dbase"
    return url


def _is_vfp_double(dbversion: int | None, size: int | None) -> bool:
    if dbversion in _VFP_DOUBLE_VERSIONS:
        return True
    # No header: an 8-byte B matches the Visual FoxPro double layout.
    return dbversion is None and size == 8


def map_dbase_type(field, dbversion: int | None = None) -> satypes.TypeEngine:
    ft = (field.type).upper()
    size = getattr(field, "length", None) or getattr(field, "size", None)
    deci = getattr(field, "decimal_count", None) or getattr(field, "decimal", 0) or 0

    if ft == "F":
        # dbfread parseF returns a binary float (fractions and scientific
        # notation). The N width ladder would round or overflow those values.
        return satypes.Numeric()
    if ft == "N":
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
    if ft in ("G", "P"):
        return satypes.LargeBinary()
    if ft == "B":
        if _is_vfp_double(dbversion, size):
            return satypes.Float()
        return satypes.LargeBinary()
    # Unrecognized types keep the declared character width instead of TEXT.
    return satypes.String(size or 255)


def deduplicate_column_name(name: str, seen: set[str]) -> str:
    candidate = name
    suffix = 2
    while candidate in seen:
        candidate = f"{name}_{suffix}"
        suffix += 1
    seen.add(candidate)
    return candidate


def _dbversion(dbf: DBF) -> int | None:
    header = getattr(dbf, "header", None)
    version = getattr(header, "dbversion", None)
    return version if isinstance(version, int) else None


def infer_sqlalchemy_table_from_dbf(
    dbf: DBF, metadata: MetaData, table_name: str, schema: str | None = None
) -> Table:
    columns: List[Column] = []
    seen_names: set[str] = {DBF_RECNO}
    dbversion = _dbversion(dbf)
    for f in dbf.fields:
        if f.name == "":
            continue
        coltype = map_dbase_type(f, dbversion=dbversion)
        colname = deduplicate_column_name(f.name.lower(), seen_names)
        columns.append(Column(colname, coltype))
    columns.append(Column(DBF_RECNO, satypes.Integer, primary_key=True))
    return Table(table_name, metadata, *columns, schema=schema)


def _quoted(preparer, name: str, schema: str | None = None) -> str:
    quoted = preparer.quote(name)
    if schema:
        return f"{preparer.quote(schema)}.{quoted}"
    return quoted


def physical_recnos(dbf: DBF) -> List[int]:
    """1-based file slots of records that are not deleted.

    xBase RECNO() counts every slot, including rows flagged ``*``. The values
    returned here are those numbers for the rows ``DBF`` yields.
    """
    header = dbf.header
    recnos: List[int] = []
    recno = 0
    with open(dbf.filename, "rb") as infile:
        infile.seek(header.headerlen)
        while True:
            sep = infile.read(1)
            if sep in (b"\x1a", b""):
                break
            recno += 1
            if sep == b" ":
                recnos.append(recno)
            infile.seek(header.recordlen - 1, 1)
    return recnos


def normalize_dbf_rows(
    rows: List[Dict[str, Any]], dbf: DBF, recnos: List[int] | None = None
) -> List[Dict[str, Any]]:
    if recnos is not None and len(recnos) != len(rows):
        raise ValueError(f"record numbers ({len(recnos)}) do not match rows ({len(rows)})")
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
        mapped[DBF_RECNO] = recnos[i - 1] if recnos is not None else i
        normalized.append(mapped)
    return normalized


def _rows_for_import(dbf: DBF) -> List[Dict[str, Any]]:
    raw = [dict(row) for row in dbf]
    # A physical slot exists only when the rows came from a file on disk.
    if getattr(dbf, "filename", None) and getattr(dbf, "header", None):
        return normalize_dbf_rows(raw, dbf, recnos=physical_recnos(dbf))
    return normalize_dbf_rows(raw, dbf)


def _field_needs_memo(field, dbversion: int | None) -> bool:
    ftype = (getattr(field, "type", "") or "").upper()
    if ftype in {"M", "G", "P"}:
        return True
    if ftype == "B":
        size = getattr(field, "length", None) or getattr(field, "size", None)
        return not _is_vfp_double(dbversion, size)
    return False


def _warn_if_memo_missing(dbf: DBF, dbf_path: str) -> None:
    # dbfread records the memo path on memofilename. It never sets .memo.
    dbversion = _dbversion(dbf)
    needs_memo = any(_field_needs_memo(field, dbversion) for field in dbf.fields)
    if needs_memo and getattr(dbf, "memofilename", None) is None:
        log.warning(
            "Memo file missing for %s; memo field values will be empty",
            dbf_path,
        )


def load_dbf_into_postgres(engine: Engine, dbf_path: str) -> None:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("imports require PostgreSQL")

    basename = os.path.splitext(os.path.basename(dbf_path))[0]
    table_name = sanitize_table_name(basename)
    dbf = DBF(dbf_path, encoding=get_dbf_encoding(), ignore_missing_memofile=True)
    _warn_if_memo_missing(dbf, dbf_path)

    # Build under the same 63-byte name in import_staging, then move it into
    # public. That name cannot truncate onto another table, and it cannot
    # collide with a file that used to sanitize to "{table}__loading".
    table = infer_sqlalchemy_table_from_dbf(dbf, MetaData(), table_name, schema=STAGING_SCHEMA)
    rows = _rows_for_import(dbf)

    preparer = engine.dialect.identifier_preparer
    live = _quoted(preparer, table_name, LIVE_SCHEMA)
    staging = _quoted(preparer, table_name, STAGING_SCHEMA)
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {preparer.quote(STAGING_SCHEMA)}"))
        conn.execute(text(f"DROP TABLE IF EXISTS {staging}"))
        table.create(conn, checkfirst=False)
        if rows:
            conn.execute(table.insert(), rows)
        conn.execute(text(f"DROP TABLE IF EXISTS {live}"))
        conn.execute(text(f"ALTER TABLE {staging} SET SCHEMA {preparer.quote(LIVE_SCHEMA)}"))


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
