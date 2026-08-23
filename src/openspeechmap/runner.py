"""Running the stages a declaration names.

The stage functions are unchanged; this decides which of them to call and in
what order, and stops when one fails. It exists because the everyday use of
this pipeline is a pass over a directory that keeps growing, and asking someone
to write that out three times in a crontab is the binding work left undone.

Capture is not part of a pass. Recording never finishes, so it cannot be a step
in something that ends; a declaration naming a stream is telling you to start
`speechmap-record` separately and then run passes alongside it.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from openspeechmap import jsonl, pipeline, transcribe
from openspeechmap import series as series_module
from openspeechmap.config import Config
from openspeechmap.lens import LensError
from openspeechmap.tools import ToolError


class StageError(Exception):
    """A stage that could not finish, with a message saying which and why."""


@dataclass(frozen=True)
class Step:
    stage: str
    ok: bool
    message: str


def pass_stages(cfg: Config) -> list[str]:
    """The stages a single pass runs: everything the declaration implies except
    capture, which does not end."""
    return [s for s in cfg.stages() if s != "record"]


def once(cfg: Config) -> list[Step]:
    """Run one pass. Returns what happened, in order, stopping at the first
    failure.

    Each stage is idempotent, so a pass over unchanged input costs a directory
    listing. That is what makes running this on a timer reasonable.
    """
    done: list[Step] = []
    for stage in pass_stages(cfg):
        try:
            # Looked up by name at call time rather than held in the table, so a
            # test (or a caller) that replaces a stage function is actually
            # replacing what runs.
            message = globals()[f"_{stage}"](cfg)
        except NothingYet as e:
            # Not a failure, and the stages after it have nothing either.
            done.append(Step(stage=stage, ok=True, message=str(e)))
            return done
        except (StageError, ToolError, LensError, jsonl.InputError,
                series_module.SeriesError, transcribe.TranscribeError) as e:
            done.append(Step(stage=stage, ok=False, message=str(e)))
            return done
        done.append(Step(stage=stage, ok=True, message=message))
    return done


class NothingYet(Exception):
    """A stage that has nothing to work on, which is not a failure.

    On a fresh start the first pass happens before the first recording is
    finished. Reporting that as an error every time teaches whoever is watching
    that the exclamation mark means nothing.
    """


def _transcribe(cfg: Config) -> str:
    if cfg.recordings.is_dir() and not any(
        f.suffix.lower() in transcribe.AUDIO_SUFFIXES for f in cfg.recordings.iterdir()
    ):
        raise NothingYet("nothing recorded yet")
    result = transcribe.run(
        source=cfg.recordings,
        out_dir=cfg.transcripts,
        chunk_sec=cfg.transcribe.chunk_sec,
        whisper_url=cfg.transcribe.whisper_url,
        language=cfg.transcribe.language or None,
        skip_newest=cfg.transcribe.skip_newest,
    )
    if result.files == 0:
        return f"nothing new ({result.skipped} already done)"
    return (
        f"{result.files} file(s) -> {result.records} records "
        f"({result.empty} with no speech)"
    )


def _lens(cfg: Config) -> str:
    stage = cfg.lens_stage
    result = pipeline.run(
        source=cfg.transcripts,
        lens=cfg.lens,
        out_dir=cfg.out,
        text_field=stage.text_field,
        id_field=stage.id_field,
        place_field=stage.place_field,
        time_field=stage.time_field or None,
        select=stage.select,
        model=stage.model,
        llm_url=stage.llm_url,
        loci_url=stage.loci_url,
        concurrency=stage.concurrency,
    )
    head = (
        f"nothing new ({result.reused} already labelled)"
        if result.new == 0
        else f"{result.new} file(s) -> {result.read} records"
    )
    return (
        f"{head}; {result.labeled} labelled, {result.selected} selected, "
        f"{result.places} places ({result.resolved} resolved)"
    )


def _series(cfg: Config) -> str:
    labeled = cfg.out / "labeled.jsonl"
    if not labeled.is_file():
        raise StageError(f"series: {labeled} is missing; the lens stage did not run")
    try:
        result = series_module.run(
            source=labeled,
            out_dir=cfg.out,
            select=cfg.series.select,
            key_field=cfg.series.key_field or None,
            bucket=cfg.series.bucket,
            threshold=cfg.series.threshold,
        )
    except series_module.SeriesError as e:
        if "matched no records" not in str(e):
            raise
        # Most of any broadcast day is not about the thing you are looking for.
        # Reporting a failed pass every time the radio plays music teaches
        # whoever is watching to ignore the report.
        return "nothing to count yet"
    return (
        f"{result.counted} counted -> {result.series} series, "
        f"{result.candidates} candidates, {result.change_points} change points"
    )


def record_command(cfg: Config) -> list[str]:
    """The capture command a declaration implies, for printing rather than
    running. Whoever supervises long-running processes here should start it."""
    source = cfg.source
    argv = [
        "speechmap-record",
        "--out", str(cfg.recordings),
        "--source", source.kind,
        "--label", source.label,
        "--segment-sec", str(source.segment_sec),
        "--retention-hours", str(source.retention_hours),
        "--max-gb", str(source.max_gb),
    ]
    if source.kind == "http":
        argv += ["--url", source.url]
    else:
        argv += ["--freq", source.freq, "--gain", source.gain, "--device", source.device]
    return argv


def forever(
    *,
    cfg,
    interval: float,
    capture: Callable[[Callable[[], bool]], None] | None,
    stop: threading.Event,
    on_pass: Callable[[list[Step] | None], None] | None = None,
    on_capture_lost: Callable[[BaseException], None] | None = None,
) -> None:
    """Keep the capture running and keep taking passes over what it produces.

    The two are deliberately independent. A model endpoint going away for a
    minute must not end a run that has been recording for a week, and whatever
    is on the far end of a stream is not this program's fault: the transcripts
    already on disk are still worth processing. So a failed pass is reported and
    the loop continues, and a capture that dies is reported without stopping the
    passes.

    `capture` is called once, in a thread, and is expected to run until the
    function it is given returns true. Passing None runs passes alone, which is
    what a declaration reading from a directory or from transcripts wants.
    """
    thread = None
    if capture is not None:
        def run_capture() -> None:
            try:
                capture(stop.is_set)
            except BaseException as e:  # noqa: BLE001 - reported, not swallowed
                if on_capture_lost is not None:
                    on_capture_lost(e)

        thread = threading.Thread(target=run_capture, name="capture", daemon=True)
        thread.start()

    try:
        while not stop.is_set():
            try:
                result = once(cfg)
            except Exception as e:  # noqa: BLE001 - a pass may fail; the run does not
                if on_pass is not None:
                    on_pass(None)
                _ = e
            else:
                if on_pass is not None:
                    on_pass(result)
            if stop.is_set():
                break
            stop.wait(interval)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if thread is not None:
            thread.join(timeout=10)
