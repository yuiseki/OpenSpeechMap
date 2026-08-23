"""Apply a lens to transcripts, then ground the place names.

Three stages, each leaving a file behind, so a later stage can be re-run
without redoing the ones before it and you can look at what came out in
between.

The lens stage and the place stage are other programs. What is here is the
gate, the selection, the join that puts the time back on each place, and the
counting.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openspeechmap import jsonl
from openspeechmap.lens import Lens
from openspeechmap.tools import Tool, find


@dataclass(frozen=True)
class Result:
    """What a run produced, for reporting."""

    read: int
    gated_out: int
    labeled: int
    selected: int
    places: int
    resolved: int
    gate_keywords: int
    new: int = 0
    reused: int = 0


def transcript_files(source: str | Path) -> list[Path]:
    """One transcript file, or every one in a directory, in name order."""
    if str(source) == "-":
        raise jsonl.InputError(
            "this stage cannot read standard input: each input file gets an output "
            "file named after it, and standard input has no name. Write it to a "
            "file first."
        )
    p = Path(source).expanduser()
    if p.is_file():
        return [p]
    if not p.is_dir():
        raise jsonl.InputError(f"input not found: {source}")
    found = sorted(f for f in p.glob("*.jsonl") if f.is_file())
    if not found:
        raise jsonl.InputError(f"{p}: no .jsonl files")
    return found


def labeled_for(out_dir: Path, source: Path) -> Path:
    """Where one transcript file's labels go. The existence of this file is the
    only record that the transcript has been labelled; there is no state file to
    disagree with it. Deleting it relabels exactly that transcript."""
    return out_dir / "labeled" / source.name


def _write_atomically(target: Path, rows: list[jsonl.Record]) -> None:
    """Write to a sibling temporary name and rename over the target, so a
    reader sees the whole file or nothing. A run killed halfway must not leave a
    short file that the next run treats as finished."""
    import json as _json

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".partial")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(_json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(target)


def run(
    *,
    source: str | Path,
    lens: Lens,
    out_dir: Path,
    text_field: str = "text",
    id_field: str = "seg",
    place_field: str = "topic",
    time_field: str | None = "t",
    select: str = ".is_disaster",
    model: str = "gvt-llm",
    llm_url: str = "http://127.0.0.1:8080/v1",
    loci_url: str = "http://127.0.0.1:30101",
    concurrency: int = 6,
    redo: bool = False,
) -> Result:
    aiq = find("aiq")
    locitorium = find("locitorium")
    jq = find("jq")

    out_dir.mkdir(parents=True, exist_ok=True)
    labeled_path = out_dir / "labeled.jsonl"
    selected_path = out_dir / "selected.jsonl"
    places_path = out_dir / "places.geojson"

    inputs = transcript_files(source)
    todo = inputs if redo else [f for f in inputs if not labeled_for(out_dir, f).exists()]

    # Label the transcripts that have no labels yet, one output file each.
    keywords = lens.gate_keywords()
    read = gated_out = 0
    for path in todo:
        records = list(jsonl.read(path))
        for r in records:
            jsonl.require(r, text_field, where=str(path))
        read += len(records)
        kept = [r for r in records if lens.passes_gate(str(r.get(text_field) or ""))]
        gated_out += len(records) - len(kept)
        labeled = _label(
            aiq, kept, lens=lens, text_field=text_field, model=model,
            llm_url=llm_url, concurrency=concurrency,
        )
        _write_atomically(labeled_for(out_dir, path), labeled)

    # The aggregates are derived from every part, not from what this run did, so
    # a run that labelled one file still emits places for all of them. They can
    # be deleted at any time and cost only a concatenation to rebuild.
    all_labeled: list[jsonl.Record] = []
    for path in inputs:
        part = labeled_for(out_dir, path)
        if part.is_file():
            all_labeled.extend(jsonl.read(part))
    jsonl.write(all_labeled, labeled_path)

    selected = _select(
        jq, labeled_path, select=select, id_field=id_field, place_field=place_field
    )
    jsonl.write(selected, selected_path)

    features = _resolve(locitorium, selected, loci_url=loci_url, out_path=places_path)
    if time_field:
        features = _join_time(
            features, all_labeled, id_field=id_field, time_field=time_field,
            out_path=places_path,
        )

    return Result(
        read=read,
        gated_out=gated_out,
        new=len(todo),
        reused=len(inputs) - len(todo),
        labeled=len(all_labeled),
        selected=len(selected),
        places=len(features),
        resolved=sum(
            1 for f in features if f.get("properties", {}).get("status") == "resolved"
        ),
        gate_keywords=len(keywords),
    )


def _label(
    aiq: Tool,
    records: list[jsonl.Record],
    *,
    lens: Lens,
    text_field: str,
    model: str,
    llm_url: str,
    concurrency: int,
) -> list[jsonl.Record]:
    if not records:
        return []
    args = [
        "extract",
        "--schema-file", str(lens.schema),
        "--instruction-file", str(lens.instruction),
        "--input-type", "json",
        "--input-field", text_field,
        "--max-concurrency", str(concurrency),
        "--model", model,
        "--api-base-url", llm_url,
    ]
    if lens.system is not None:
        args += ["--system-file", str(lens.system)]
    return jsonl.loads(aiq.run(args, stdin=jsonl.dumps(records)))


def _select(
    jq: Tool,
    labeled_path: Path,
    *,
    select: str,
    id_field: str,
    place_field: str,
) -> list[jsonl.Record]:
    """Selection is a jq expression rather than a set of flags, so the cutoff
    lives in the caller's command and not in this program."""
    program = f"select({select}) | {{id: .{id_field}, text: .{place_field}}}"  # noqa: E501
    return jsonl.loads(jq.run(["-c", program, str(labeled_path)]))


def _resolve(
    locitorium: Tool,
    selected: list[jsonl.Record],
    *,
    loci_url: str,
    out_path: Path,
) -> list[dict]:
    """Spelling variants are absorbed here: locitorium returns OSM entities, so
    two spellings of the same place come back with the same osm_id. There is no
    normalisation dictionary in this repository on purpose."""
    if not selected:
        out_path.write_text(
            '{"type": "FeatureCollection", "features": []}\n', encoding="utf-8"
        )
        return []
    args = [
        "resolve",
        "--text-field", "text",
        "--id-field", "id",
        "--format", "geojson",
        "--quiet",
        "--server-url", loci_url,
    ]
    raw = locitorium.run(args, stdin=jsonl.dumps(selected))
    import json

    collection = json.loads(raw.decode("utf-8"))
    features = collection.get("features", [])
    out_path.write_bytes(raw)
    return features


def _join_time(
    features: list[dict],
    labeled: list[jsonl.Record],
    *,
    id_field: str,
    time_field: str,
    out_path: Path,
) -> list[dict]:
    """locitorium answers about text, so it has no idea when anything was said.
    The time is put back here, from the record each place came out of. Without
    it every consumer has to re-join against labeled.jsonl, which is how the
    original prototype ended up with its time series reading the map's output
    instead of the other way round."""
    import json

    when = {str(r.get(id_field)): r.get(time_field) for r in labeled}
    for f in features:
        props = f.setdefault("properties", {})
        props["t"] = when.get(str(props.get("input_id")))
    out_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features},
                   ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return features
