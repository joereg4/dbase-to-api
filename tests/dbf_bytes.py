"""Minimal dBASE III writer for tests that need exact field bytes."""

import struct
from datetime import date
from pathlib import Path


def write_dbf(
    path: Path,
    fields: list[tuple[str, str, int, int]],
    rows: list[tuple[bool, list[str]]],
) -> None:
    """Write a version-0x03 file.

    ``fields`` is ``(name, type, length, decimals)``. ``rows`` is
    ``(deleted, values)``. Numeric and float values are right-justified.
    """
    header_len = 32 + 32 * len(fields) + 1
    record_len = 1 + sum(length for _, _, length, _ in fields)
    today = date.today()
    header = bytearray(32)
    header[0] = 0x03
    header[1] = max(today.year - 1900, 0)
    header[2] = today.month
    header[3] = today.day
    header[4:8] = struct.pack("<I", len(rows))
    header[8:10] = struct.pack("<H", header_len)
    header[10:12] = struct.pack("<H", record_len)

    descriptors = bytearray()
    for name, ftype, length, decimals in fields:
        desc = bytearray(32)
        encoded = name.encode("ascii")
        if not encoded or len(encoded) > 11:
            raise ValueError(f"field name must be 1..11 ASCII bytes: {name!r}")
        desc[: len(encoded)] = encoded
        desc[11] = ord(ftype)
        desc[16] = length
        desc[17] = decimals
        descriptors += desc

    records = bytearray()
    for deleted, values in rows:
        if len(values) != len(fields):
            raise ValueError("row width does not match fields")
        record = bytearray((0x2A if deleted else 0x20,))
        for (_, ftype, length, _), value in zip(fields, values):
            raw = value.encode("latin-1")
            if len(raw) > length:
                raise ValueError(f"{value!r} does not fit in {length} bytes")
            record += raw.rjust(length) if ftype in "NF" else raw.ljust(length)
        records += record

    path.write_bytes(bytes(header) + bytes(descriptors) + b"\r" + bytes(records) + b"\x1a")
