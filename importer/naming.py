import re

_IDENT_RE = re.compile(r"[^a-z0-9_]+")


def sanitize_table_name(basename: str) -> str:
    name = basename.lower().strip()
    name = _IDENT_RE.sub("_", name)
    name = name.strip("_") or "table"
    if name[0].isdigit():
        name = f"t_{name}"
    return name[:63]


# Refresh builds here, then moves the table into LIVE_SCHEMA. A separate
# schema keeps the 63-byte name from colliding with a live table.
STAGING_SCHEMA = "import_staging"
LIVE_SCHEMA = "public"
