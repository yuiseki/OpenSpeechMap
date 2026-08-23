"""Audio to timestamped transcripts.

whisper.cpp does the recognition, over HTTP. What is here is the part around
it: work out when a recording started, cut it into pieces the recogniser can
hold, and emit one record per piece with the time on it.

The time is the whole point. Nothing downstream reads audio metadata, so a
wrong timestamp here makes every later answer wrong in a way that still looks
plausible.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from openspeechmap.jsonl import Record
from openspeechmap.tools import Tool, find

# What `speechmap-record` writes: a label, then the date and time it started.
# The label may contain hyphens, so the two number groups are anchored to the
# end rather than counted from the start.
_NAME_TIME = re.compile(r"^(?P<label>.+)-(?P<date>\d{8})-(?P<time>\d{6})$")

# Shorter than this at the end of a file and there is nothing to recognise;
# whisper answers a fragment of silence with an invention.
_MIN_TAIL_SEC = 1.0

AUDIO_SUFFIXES = (".ts", ".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac", ".mp4")


class TranscribeError(Exception):
    """A request that cannot be honoured, with a message saying what to fix."""


@dataclass(frozen=True)
class Result:
    files: int
    chunks: int
    records: int
    empty: int
    skipped: int = 0


def output_for(out_dir: Path, source: Path) -> Path:
    """Where one input file's transcripts go.

    One output per input, named after it. The existence of the output is the
    only record that the input has been done: there is no state file, so there
    is nothing that can disagree with what is on disk. Deleting an output redoes
    exactly that input.
    """
    return out_dir / (source.stem + ".jsonl")


def started_at(path: str | Path, override: dt.datetime | None = None) -> dt.datetime:
    """When this recording started.

    In order of preference: what the caller said, what the filename says, when
    the file was last written. The filename is preferred over mtime because a
    copied or rsynced file keeps its name and loses its mtime.
    """
    if override is not None:
        return override
    p = Path(path)
    match = _NAME_TIME.match(p.stem)
    if match:
        try:
            return dt.datetime.strptime(
                match.group("date") + match.group("time"), "%Y%m%d%H%M%S"
            )
        except ValueError:
            # A name-shaped string that is not a date. Falling through to mtime
            # is better than guessing: a wrong timestamp puts records in the
            # wrong bucket and nothing downstream can tell.
            pass
    return dt.datetime.fromtimestamp(p.stat().st_mtime)


def offsets(duration: float, chunk_sec: int) -> list[int]:
    """Where each chunk starts. The last one may be short, but not a sliver."""
    if duration <= 0:
        return []
    out = []
    at = 0
    while at < duration:
        remaining = duration - at
        if out and remaining < _MIN_TAIL_SEC:
            break
        out.append(at)
        at += chunk_sec
    return out


def record(*, source: str, start: dt.datetime, offset: int, text: str) -> Record:
    """One transcript, with the time it was spoken and an id that says where it
    came from. The id is `<file>@<offset>`, so a record can always be traced
    back to a position in a recording."""
    return {
        "t": (start + dt.timedelta(seconds=offset)).strftime("%Y-%m-%dT%H:%M:%S"),
        "seg": f"{source}@{offset}",
        "text": text.strip(),
    }


def request_fields(*, language: str | None) -> dict[str, str]:
    """Form fields for the whisper.cpp server. Leaving the language out lets it
    detect one, which is worth doing only if you do not know."""
    fields = {"response_format": "json", "temperature": "0"}
    if language:
        fields["language"] = language
    return fields


def duration_of(ffprobe: Tool, path: Path) -> float:
    raw = ffprobe.run([
        "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ])
    try:
        return float(raw.decode().strip())
    except ValueError as e:
        raise TranscribeError(f"{path}: ffprobe could not read a duration") from e


def audio_files(source: str | Path) -> list[Path]:
    """One file, or every audio file in a directory, oldest first by name."""
    p = Path(source).expanduser()
    if p.is_file():
        return [p]
    if not p.is_dir():
        raise TranscribeError(f"input not found: {source}")
    found = sorted(
        f for f in p.iterdir() if f.is_file() and f.suffix.lower() in AUDIO_SUFFIXES
    )
    if not found:
        raise TranscribeError(
            f"{p}: no audio files. Looked for {', '.join(AUDIO_SUFFIXES)}"
        )
    return found


def _transcribe_chunk(
    ffmpeg: Tool,
    curl: Tool,
    path: Path,
    *,
    offset: int,
    chunk_sec: int,
    whisper_url: str,
    language: str | None,
    scratch: Path,
) -> str:
    """Cut one chunk out and ask whisper what it says.

    Converted to 16k mono PCM because that is what the recogniser wants, and
    written to a file rather than piped: the server needs a complete multipart
    upload, not a stream.
    """
    wav = scratch / "chunk.wav"
    ffmpeg.run([
        "-hide_banner", "-loglevel", "error",
        "-ss", str(offset), "-t", str(chunk_sec), "-i", str(path),
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", "-y", str(wav),
    ])
    args = ["-s", "-F", f"file=@{wav}"]
    for key, value in request_fields(language=language).items():
        args += ["-F", f"{key}={value}"]
    args.append(whisper_url)
    raw = curl.run(args)
    try:
        answer = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        head = raw.decode("utf-8", "replace")[:200]
        raise TranscribeError(
            f"{whisper_url} did not answer with JSON. It said: {head}"
        ) from e
    return str(answer.get("text") or "")


def run(
    *,
    source: str | Path,
    out_dir: Path,
    chunk_sec: int = 60,
    whisper_url: str = "http://127.0.0.1:30180/inference",
    language: str | None = None,
    start_override: dt.datetime | None = None,
    redo: bool = False,
    skip_newest: bool = False,
) -> Result:
    """Transcribe a file, or every audio file in a directory.

    Idempotent: an input whose output already exists is skipped, so this is safe
    to run on a timer over a directory that keeps growing. Each output is
    written to a temporary name and renamed, so a crash leaves an output that is
    complete or absent, never truncated and looking finished.

    Every chunk produces a record, including the silent ones. A quiet minute is
    a fact about that minute; dropping it leaves a hole the time series cannot
    tell from a minute that was never recorded.
    """
    ffmpeg = find("ffmpeg")
    ffprobe = find("ffprobe")
    curl = find("curl")

    found = audio_files(source)
    out_dir.mkdir(parents=True, exist_ok=True)

    if skip_newest and len(found) > 1:
        # `speechmap-record` is probably still writing into the newest one.
        # Transcribing a half-written segment gives a transcript that is
        # quietly short, which is worse than not having it yet.
        found = found[:-1]

    todo = found if redo else [f for f in found if not output_for(out_dir, f).exists()]
    skipped = len(found) - len(todo)

    chunks = records = empty = 0
    with tempfile.TemporaryDirectory(prefix="speechmap-") as tmp:
        scratch = Path(tmp)
        for path in todo:
            start = started_at(path, override=start_override)
            duration = duration_of(ffprobe, path)
            positions = offsets(duration, chunk_sec)
            if not positions:
                print(f"speechmap-transcribe: {path.name} is empty, skipped",
                      file=sys.stderr)
                continue
            rows = []
            for offset in positions:
                chunks += 1
                text = _transcribe_chunk(
                    ffmpeg, curl, path, offset=offset, chunk_sec=chunk_sec,
                    whisper_url=whisper_url, language=language, scratch=scratch,
                )
                row = record(source=path.name, start=start, offset=offset, text=text)
                if not row["text"]:
                    empty += 1
                rows.append(row)
                records += 1
            _write_atomically(output_for(out_dir, path), rows)

    return Result(files=len(todo), chunks=chunks, records=records, empty=empty,
                  skipped=skipped)


def _write_atomically(target: Path, rows: list[Record]) -> None:
    """Write to a sibling temporary file and rename over the target.

    The rename is atomic within a filesystem, so a reader either sees the whole
    output or sees nothing. Without this, a run killed halfway leaves a short
    file that the next run treats as finished.
    """
    tmp = target.with_name(target.name + ".partial")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(target)
