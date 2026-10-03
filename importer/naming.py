import re

_IDENT_RE = re.compile(r"[^a-z0-9_]+")


def sanitize_table_name(basename: str) -> str:
    name = basename.lower().strip()
    name = _IDENT_RE.sub("_", name)
    name = name.strip("_") or "table"
    if name[0].isdigit():
        name = f"t_{name}"
    return name[:63]


STAGING_SCHEMA = "import_staging"


def staging_location(dialect_name: str, table_name: str) -> tuple[str | None, str]:
    """Where to build a table before swapping it into place.

    PostgreSQL keeps the sanitized name (already ≤ 63 bytes) in another
    schema, so the staging identifier cannot truncate onto a live table.
    Other dialects use one quoted name containing a dot. ``sanitize_table_name``
    replaces that dot, so the staging name cannot be a live import.
    """
    if dialect_name == "postgresql":
        return STAGING_SCHEMA, table_name
    return None, f"{STAGING_SCHEMA}.{table_name}"
