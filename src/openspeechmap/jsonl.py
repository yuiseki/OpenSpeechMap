"""Reading and writing the record stream.

One JSON object per line, everywhere. The one rule that matters is that a stage
emits exactly one record for every record it consumed, so results can be joined
back to inputs; the exception is a lens gate, which drops records on purpose
and says how many.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

Record = dict[str, Any]


class InputError(Exception):
    """Input that cannot be read, with a message saying what to fix."""


def read(source: str | Path) -> Iterator[Record]:
    """Read JSONL from a path, or from stdin when given "-"."""
    if str(source) == "-":
        yield from _parse(sys.stdin, "standard input")
        return
    path = Path(source).expanduser()
    if not path.is_file():
        raise InputError(f"input not found: {source}")
    with path.open(encoding="utf-8") as fh:
        yield from _parse(fh, str(path))


def _parse(fh: Iterable[str], where: str) -> Iterator[Record]:
    for n, line in enumerate(fh, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as e:
            raise InputError(f"{where} line {n}: not valid JSON ({e.msg})") from e
        if not isinstance(record, dict):
            kind = type(record).__name__
            raise InputError(f"{where} line {n}: expected a JSON object, got {kind}")
        yield record


def write(records: Iterable[Record], path: Path) -> int:
    """Write JSONL, returning how many records were written."""
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False))
            fh.write("\n")
            n += 1
    return n


def dumps(records: Iterable[Record]) -> bytes:
    """Serialise records for handing to another program on its stdin."""
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records).encode("utf-8")


def loads(data: bytes) -> list[Record]:
    """Parse what another program wrote to stdout."""
    out = []
    for n, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise InputError(f"output line {n} is not valid JSON: {e.msg}") from e
    return out


def require(record: Record, field: str, *, where: str) -> Any:
    """Fetch a field, saying which field is missing rather than raising KeyError
    from somewhere deeper."""
    if field not in record:
        raise InputError(
            f"{where}: a record has no {field!r} field. "
            f"Its fields are: {', '.join(sorted(record)) or '(none)'}"
        )
    return record[field]
