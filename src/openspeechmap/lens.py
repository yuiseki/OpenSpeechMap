"""A lens: what turns speech into the thing you are looking for.

Three or four text files, not code. See docs/ADR/0002-lenses-as-data.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class LensError(Exception):
    """A lens directory that cannot be used, with a message saying why."""


@dataclass(frozen=True)
class Lens:
    """A loaded lens. Paths are absolute, because the programs this drives may
    run with a different working directory."""

    path: Path
    schema: Path
    instruction: Path
    system: Path | None
    gate: Path | None

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def fields(self) -> list[str]:
        """The field names the lens adds to each record."""
        return list(_read_schema(self.schema)["properties"])

    def gate_keywords(self) -> list[str]:
        """One keyword per line. A record must contain at least one of them to
        reach the model at all."""
        if self.gate is None:
            return []
        return [w for w in self.gate.read_text(encoding="utf-8").splitlines() if w.strip()]

    def passes_gate(self, text: str) -> bool:
        words = self.gate_keywords()
        return True if not words else any(w in text for w in words)


def load(directory: str | Path) -> Lens:
    """Load and validate a lens directory."""
    path = Path(directory).expanduser()
    if not path.is_dir():
        raise LensError(f"lens directory not found: {directory}")
    path = path.resolve()

    schema = path / "schema.json"
    instruction = path / "instruction.txt"
    if not schema.is_file():
        raise LensError(f"lens is missing schema.json: {schema}")
    if not instruction.is_file():
        raise LensError(f"lens is missing instruction.txt: {instruction}")
    _read_schema(schema)  # fail here rather than deep inside another program

    system = path / "system.txt"
    gate = path / "gate.txt"
    return Lens(
        path=path,
        schema=schema,
        instruction=instruction,
        system=system if system.is_file() else None,
        gate=gate if gate.is_file() else None,
    )


def _read_schema(schema: Path) -> dict:
    try:
        parsed = json.loads(schema.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise LensError(f"{schema}: not valid JSON ({e})") from e
    if not isinstance(parsed, dict) or parsed.get("type") != "object":
        raise LensError(
            f'{schema}: must be a JSON Schema object, i.e. {{"type": "object", '
            '"properties": {...}}'
        )
    if not parsed.get("properties"):
        raise LensError(f"{schema}: has no properties, so nothing would be extracted")
    return parsed
