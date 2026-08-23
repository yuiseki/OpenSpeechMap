"""Count labeled records over time and find the unusual stretches.

The analysis is detempus's. What is here is the reshaping into the counts it
expects, and keeping its answer verbatim -- including the `method` block that
says how the answer was produced, which is the only thing that makes a result
reproducible later.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from openspeechmap import jsonl
from openspeechmap.tools import Tool, find

BUCKETS = {"day": ("daily", 10), "hour": ("hourly", 13)}


class SeriesError(Exception):
    """Nothing to count, or a request that cannot be honoured."""


@dataclass(frozen=True)
class Result:
    counted: int
    series: int
    candidates: int
    change_points: int


def run(
    *,
    source: str | Path,
    out_dir: Path,
    select: str = ".is_disaster",
    key_field: str | None = "category",
    time_field: str = "t",
    bucket: str = "day",
    threshold: float | None = None,
    baseline: str | None = None,
    changepoint: str | None = None,
) -> Result:
    if bucket not in BUCKETS:
        raise SeriesError(
            f"--bucket must be one of {', '.join(BUCKETS)}, not {bucket!r}"
        )
    preset, cut = BUCKETS[bucket]

    detempus = find("detempus")
    jq = find("jq")

    out_dir.mkdir(parents=True, exist_ok=True)
    counts_path = out_dir / "counts.jsonl"
    series_path = out_dir / "series.json"

    counts = _reshape(
        jq, source, select=select, key_field=key_field, time_field=time_field, cut=cut
    )
    if not counts:
        raise SeriesError(
            f"the select expression {select!r} matched no records. Nothing to count."
        )
    jsonl.write(counts, counts_path)

    args = [str(counts_path), "--preset", preset, "--format", "jsonl", "--quiet"]
    if threshold is not None:
        args += ["--threshold", str(threshold)]
    if baseline:
        args += ["--baseline", baseline]
    if changepoint:
        args += ["--changepoint", changepoint]
    series = jsonl.loads(detempus.run(args))

    document = {
        "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bucket": bucket,
        "select": select,
        "key_field": key_field or None,
        "series": series,
    }
    series_path.write_text(
        json.dumps(document, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    counts_path.unlink(missing_ok=True)

    return Result(
        counted=len(counts),
        series=len(series),
        candidates=sum(len(s.get("anomalies", [])) for s in series),
        change_points=sum(len(s.get("change_points", [])) for s in series),
    )


def _reshape(
    jq: Tool,
    source: str | Path,
    *,
    select: str,
    key_field: str | None,
    time_field: str,
    cut: int,
) -> list[jsonl.Record]:
    """One line per counted record. detempus treats a missing value as one event
    at that time, which is the count wanted here, so nothing is summed."""
    key = f'(.{key_field} // "(none)")' if key_field else '"all"'
    program = f"select({select}) | {{t: (.{time_field}[0:{cut}]), key: {key}}}"
    if str(source) == "-":
        data = jsonl.dumps(list(jsonl.read(source)))
        return jsonl.loads(jq.run(["-c", program], stdin=data))
    return jsonl.loads(jq.run(["-c", program, str(Path(source).expanduser())]))
