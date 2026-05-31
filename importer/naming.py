import re

_IDENT_RE = re.compile(r"[^a-z0-9_]+")


def sanitize_table_name(basename: str) -> str:
    name = basename.lower().strip()
    name = _IDENT_RE.sub("_", name)
    name = name.strip("_") or "table"
    if name[0].isdigit():
        name = f"t_{name}"
    return name[:63]
