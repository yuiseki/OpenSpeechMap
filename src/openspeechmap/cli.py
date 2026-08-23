"""The command line.

Two commands, because counting over time is a different question from putting
things on a map, wants a different shape of input, and gets asked again with
different settings without re-running any language model.

Expected failures print one line and exit non-zero. A caller -- often an agent
-- needs to know what to fix, and a traceback does not say that. Set
OPENSPEECHMAP_TRACEBACK=1 while developing to get the exception back.
"""
from __future__ import annotations

import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from openspeechmap import __version__, jsonl, pipeline
from openspeechmap import config as config_module
from openspeechmap import lens as lens_module
from openspeechmap import record as record_module
from openspeechmap import runner as runner_module
from openspeechmap import series as series_module
from openspeechmap import transcribe as transcribe_module
from openspeechmap.tools import ToolError, check

EXPECTED = (
    lens_module.LensError,
    jsonl.InputError,
    ToolError,
    series_module.SeriesError,
    record_module.RecordError,
    transcribe_module.TranscribeError,
    config_module.ConfigError,
    runner_module.StageError,
)

# What each stage drives. Grouping matters: "aiq is missing" only stops you if
# you were going to apply a lens, and a machine with no radio dongle is not
# missing anything required.
STAGES: list[tuple[str, list[str], list[str]]] = [
    # (stage, required, needed only in some mode)
    ("record", ["ffmpeg"], ["rtl_fm"]),
    ("transcribe", ["ffmpeg", "ffprobe", "curl"], []),
    ("lens", ["jq", "aiq", "locitorium"], []),
    ("series", ["jq", "detempus"], []),
]
# Why an optional one is optional, so the report can say.
OPTIONAL_BECAUSE = {"rtl_fm": "only for --source sdr; comes with librtlsdr"}


def _fail(message: str) -> None:
    print(f"speechmap: {message}", file=sys.stderr)
    raise typer.Exit(1)


def _guard(fn, *args, **kwargs):
    """Run the real work, turning the failures a caller can act on into one
    line. Anything else is a bug here and keeps its traceback."""
    try:
        return fn(*args, **kwargs)
    except EXPECTED as e:
        if os.environ.get("OPENSPEECHMAP_TRACEBACK"):
            raise
        _fail(str(e))
    except BrokenPipeError:
        # A downstream command closed the pipe. Stop quietly, like any filter.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        raise typer.Exit(141) from None


app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    invoke_without_command=True,
    help="Find the signals you care about in speech. Run with no arguments to "
    "start everything a speechmap.yaml declares and keep it running.",
)


@app.callback()
def _root(
    ctx: typer.Context,
    config_file: Annotated[
        str, typer.Option("--config", "-c", help="Declaration to read.")
    ] = "speechmap.yaml",
    interval: Annotated[
        float, typer.Option(help="Seconds between passes.")
    ] = 60.0,
    show_plan: Annotated[
        bool, typer.Option("--plan", help="Say what would run, and stop.")
    ] = False,
) -> None:
    """With no subcommand, run capture and passes until interrupted."""
    if ctx.invoked_subcommand is not None:
        return
    _forever(config_file=config_file, interval=interval, show_plan=show_plan)


@app.command("lens")
def lens_main(
    transcripts: Annotated[
        str,
        typer.Argument(
            help="A transcripts .jsonl, or a directory of them. A transcript whose "
            "labels are already in <out>/labeled/ is skipped."
        ),
    ] = "",
    lens: Annotated[str, typer.Option(help="A lens directory.")] = "",
    out: Annotated[str, typer.Option(help="Where to write the three output files.")] = "",
    text_field: Annotated[str, typer.Option(help="Field holding the text.")] = "text",
    id_field: Annotated[str, typer.Option(help="Field holding the record id.")] = "seg",
    place_field: Annotated[
        str, typer.Option(help="Field whose text is resolved to places.")
    ] = "topic",
    time_field: Annotated[
        str,
        typer.Option(
            help="Field holding the time, copied onto each resolved place. "
            'Empty string disables it.'
        ),
    ] = "t",
    select: Annotated[
        str, typer.Option(help="jq expression choosing which labeled records go on.")
    ] = ".is_disaster",
    model: Annotated[str, typer.Option(help="Model name passed to the endpoint.")] = "gvt-llm",
    llm_url: Annotated[
        str, typer.Option(help="OpenAI-compatible base URL.")
    ] = "http://127.0.0.1:8080/v1",
    loci_url: Annotated[
        str, typer.Option(help="locitorium server.")
    ] = "http://127.0.0.1:30101",
    concurrency: Annotated[int, typer.Option(help="Parallel model requests.")] = 6,
    redo: Annotated[
        bool,
        typer.Option(
            "--redo",
            help="Label every record again. Without this, records already in "
            "labeled.jsonl are reused, which is what makes repeated runs cheap.",
        ),
    ] = False,
) -> None:
    """Apply a lens to transcripts, then ground the place names in OpenStreetMap."""
    if not transcripts:
        _fail("no input given. Pass a JSONL file, or - for standard input (try --help)")
    if not lens:
        _fail("--lens is required (try --help)")
    if not out:
        _fail("--out is required (try --help)")

    loaded = _guard(lens_module.load, lens)
    result = _guard(
        pipeline.run,
        source=transcripts,
        lens=loaded,
        out_dir=Path(out),
        text_field=text_field,
        id_field=id_field,
        place_field=place_field,
        time_field=time_field or None,
        select=select,
        model=model,
        llm_url=llm_url,
        loci_url=loci_url,
        concurrency=concurrency,
        redo=redo,
    )
    if result.gate_keywords:
        print(
            f"speechmap: gate kept {result.labeled} of {result.read} records "
            f"({result.gate_keywords} keywords)",
            file=sys.stderr,
        )
    if result.reused:
        print(f"speechmap: {result.reused} already labelled", file=sys.stderr)
    if result.new == 0:
        print("speechmap: nothing to label; rebuilding the aggregates", file=sys.stderr)
    else:
        print(
            f"speechmap: {result.new} file(s) -> {result.read} records "
            f"({result.gated_out} gated out)",
            file=sys.stderr,
        )
    print(
        f"speechmap: {result.labeled} labeled -> {result.selected} selected "
        f"-> {result.places} places ({result.resolved} resolved)",
        file=sys.stderr,
    )
    print(
        f"speechmap: wrote {out}/{{labeled/,labeled.jsonl,selected.jsonl,places.geojson}}",
        file=sys.stderr,
    )


@app.command("series")
def series_main(
    labeled: Annotated[
        str, typer.Argument(help='Output of speechmap. "-" reads standard input.')
    ] = "",
    out: Annotated[str, typer.Option(help="Where to write series.json.")] = "",
    select: Annotated[
        str, typer.Option(help="jq expression choosing which records count.")
    ] = ".is_disaster",
    key_field: Annotated[
        str,
        typer.Option(help='One series per value of this field. "" for one combined series.'),
    ] = "category",
    time_field: Annotated[str, typer.Option(help="Field holding the time.")] = "t",
    bucket: Annotated[str, typer.Option(help="day or hour.")] = "day",
    threshold: Annotated[
        float | None, typer.Option(help="Score above which a point is a candidate.")
    ] = None,
    baseline: Annotated[
        str | None, typer.Option(help="stl, rolling_median or none. Passed to detempus.")
    ] = None,
    changepoint: Annotated[
        str | None, typer.Option(help="pelt or none. Passed to detempus.")
    ] = None,
) -> None:
    """Count labeled records over time, via detempus."""
    if not labeled:
        _fail("no input given. Pass labeled.jsonl, or - for standard input (try --help)")
    if not out:
        _fail("--out is required (try --help)")

    result = _guard(
        series_module.run,
        source=labeled,
        out_dir=Path(out),
        select=select,
        key_field=key_field or None,
        time_field=time_field,
        bucket=bucket,
        threshold=threshold,
        baseline=baseline,
        changepoint=changepoint,
    )
    print(
        f"speechmap-series: {result.counted} counted -> {result.series} series, "
        f"{result.candidates} candidates, {result.change_points} change points",
        file=sys.stderr,
    )
    print(f"speechmap-series: wrote {out}/series.json", file=sys.stderr)


@app.command("pass")
def pass_main(
    config_file: Annotated[
        str, typer.Argument(help="A speechmap.yaml. Defaults to ./speechmap.yaml.")
    ] = "speechmap.yaml",
    show_plan: Annotated[
        bool,
        typer.Option("--plan", help="Say what would run, and stop."),
    ] = False,
) -> None:
    """Run one pass over whatever the declaration points at.

    Every stage is idempotent, so a pass over unchanged input costs a directory
    listing. Run it on a timer beside a long-running `speechmap-record`.

    Capture is not part of a pass: recording never finishes, so it cannot be a
    step in something that ends. `--plan` prints the command to start it with.
    """
    cfg = _guard(config_module.load, config_file)
    stages = runner_module.pass_stages(cfg)

    if show_plan:
        print(f"  declaration  {cfg.path}", file=sys.stderr)
        print(f"  source       {cfg.source.kind}", file=sys.stderr)
        print(f"  out          {cfg.out}", file=sys.stderr)
        print(f"  lens         {cfg.lens.name}", file=sys.stderr)
        if "record" in cfg.stages():
            argv = runner_module.record_command(cfg)
            print("  capture      start this separately, it does not end:",
                  file=sys.stderr)
            print(f"                 {' '.join(argv)}", file=sys.stderr)
        print(f"  each pass    {' -> '.join(stages)}", file=sys.stderr)
        return

    if "record" in cfg.stages() and not cfg.recordings.exists():
        _fail(
            f"{cfg.recordings} does not exist. This declaration names a stream, so "
            f"start the capture first (speechmap pass --plan prints the command)."
        )

    done = runner_module.once(cfg)
    for step in done:
        mark = " " if step.ok else "!"
        print(f" {mark} {step.stage:11s} {step.message}", file=sys.stderr)
    if any(not step.ok for step in done):
        raise typer.Exit(1)


@app.command("transcribe")
def transcribe_main(
    source: Annotated[
        str, typer.Argument(help="An audio file, or a directory of them.")
    ] = "",
    out: Annotated[
        str,
        typer.Option(
            help="Directory for the transcripts. One .jsonl per input file, named "
            "after it. An input whose output is already there is skipped."
        ),
    ] = "",
    chunk_sec: Annotated[
        int,
        typer.Option(
            help="Seconds per transcript. About a minute is right: shorter and "
            "there are no place names in it, longer and the summary rounds them off."
        ),
    ] = 60,
    whisper_url: Annotated[
        str, typer.Option(help="whisper.cpp server inference endpoint.")
    ] = "http://127.0.0.1:30180/inference",
    language: Annotated[
        str,
        typer.Option(
            help="Language hint, e.g. ja or en. Empty lets the recogniser detect one, "
            "which is worth doing only if you do not know."
        ),
    ] = "",
    start: Annotated[
        str,
        typer.Option(
            help="ISO timestamp for when the recording began. Overrides the filename "
            "and the file's mtime."
        ),
    ] = "",
    redo: Annotated[
        bool,
        typer.Option(
            "--redo",
            help="Transcribe everything again, replacing the output. Without this, a "
            "directory is swept incrementally and only new files are done.",
        ),
    ] = False,
    skip_newest: Annotated[
        bool,
        typer.Option(
            "--skip-newest",
            help="Leave the newest file for the next run. Use this while "
            "speechmap-record is running: it is still writing into that one.",
        ),
    ] = False,
) -> None:
    """Transcribe recordings into one JSONL stream, one record per chunk.

    The time on each record comes from the filename if it looks like
    `<LABEL>-YYYYMMDD-HHMMSS`, otherwise from the file's mtime, otherwise from
    --start. Nothing downstream reads audio metadata, so this is where the time
    enters the pipeline.
    """
    if not source:
        _fail("no input given. Pass an audio file or a directory (try --help)")
    if not out:
        _fail("--out is required (try --help)")
    override = None
    if start:
        try:
            override = datetime.fromisoformat(start)
        except ValueError:
            _fail(f"--start is not an ISO timestamp: {start!r}")

    result = _guard(
        transcribe_module.run,
        source=source,
        out_dir=Path(out),
        chunk_sec=chunk_sec,
        whisper_url=whisper_url,
        language=language or None,
        start_override=override,
        redo=redo,
        skip_newest=skip_newest,
    )
    if result.skipped:
        print(
            f"speechmap-transcribe: {result.skipped} already transcribed",
            file=sys.stderr,
        )
    if result.files == 0:
        print("speechmap-transcribe: nothing to do", file=sys.stderr)
        return
    print(
        f"speechmap-transcribe: {result.files} file(s) -> {result.chunks} chunks -> "
        f"{result.records} records ({result.empty} with no speech)",
        file=sys.stderr,
    )
    print(f"speechmap-transcribe: wrote into {out}", file=sys.stderr)


@app.command("record")
def record_main(
    out: Annotated[str, typer.Option(help="Where to write segments.")] = "",
    source: Annotated[
        str, typer.Option(help="sdr (USB RTL-SDR tuner) or http (any stream URL).")
    ] = "sdr",
    label: Annotated[
        str,
        typer.Option(
            help="Goes in every filename, ahead of the timestamp. A station id, "
            "a room name, whatever identifies the source."
        ),
    ] = "REC",
    segment_sec: Annotated[int, typer.Option(help="Seconds per file.")] = 300,
    retention_hours: Annotated[
        float, typer.Option(help="Delete segments older than this. 0 disables it.")
    ] = 168,
    max_gb: Annotated[
        float, typer.Option(help="Delete oldest once the total exceeds this. 0 disables it.")
    ] = 50,
    sweep_sec: Annotated[int, typer.Option(help="How often to check the two limits.")] = 60,
    freq: Annotated[str, typer.Option(help="[sdr] Frequency, e.g. 82.5M.")] = "82.5M",
    gain: Annotated[str, typer.Option(help="[sdr] Tuner gain in dB.")] = "19.7",
    device: Annotated[str, typer.Option(help="[sdr] rtl device index or serial.")] = "0",
    audio_bitrate: Annotated[str, typer.Option(help="[sdr] AAC bitrate.")] = "64k",
    url: Annotated[str, typer.Option(help="[http] Stream URL.")] = "",
) -> None:
    """Record continuously into fixed-length segments, deleting old ones.

    Runs until interrupted. The timestamp in each filename is how the time
    reaches the rest of the pipeline; nothing downstream reads audio metadata.
    """
    if not out:
        _fail("--out is required (try --help)")
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not out_dir.is_dir():
        _fail(f"not a directory: {out_dir}")

    starter = _guard(
        record_module.build_starter,
        source=source, label=label, out_dir=out_dir, freq=freq, gain=gain,
        device=device, segment_sec=segment_sec, audio_bitrate=audio_bitrate, url=url,
    )
    record_module.log(
        f"recording into {out_dir}: {segment_sec}s segments, "
        f"keeping {retention_hours}h and {max_gb}GB"
    )
    _guard(
        record_module.supervise,
        starter, out_dir,
        retention_hours=retention_hours, max_gb=max_gb, sweep_sec=sweep_sec,
    )


@app.command("check")
def check_main() -> None:
    """Say which of the programs each stage drives are reachable."""
    _report_tools()


@app.command("version")
def version_main() -> None:
    """Print the version."""
    print(__version__)


def _forever(*, config_file: str, interval: float, show_plan: bool) -> None:
    """Start everything a declaration names and keep it running.

    Capture and passes are independent on purpose: a model endpoint going away
    for a minute must not end a run that has been recording for a week.
    """
    cfg = _guard(config_module.load, config_file)
    stages = runner_module.pass_stages(cfg)
    records = "record" in cfg.stages()

    if show_plan:
        print(f"  declaration  {cfg.path}", file=sys.stderr)
        print(f"  source       {cfg.source.kind}", file=sys.stderr)
        print(f"  out          {cfg.out}", file=sys.stderr)
        print(f"  lens         {cfg.lens.name}", file=sys.stderr)
        if records:
            print(f"  capture      {cfg.source.label} -> {cfg.recordings}",
                  file=sys.stderr)
        print(f"  each pass    {' -> '.join(stages)}", file=sys.stderr)
        print(f"  interval     {interval:g}s", file=sys.stderr)
        return

    capture = None
    if records:
        starter = _guard(
            record_module.build_starter,
            source=cfg.source.kind, label=cfg.source.label,
            out_dir=cfg.recordings, freq=cfg.source.freq, gain=cfg.source.gain,
            device=cfg.source.device, segment_sec=cfg.source.segment_sec,
            url=cfg.source.url,
        )
        cfg.recordings.mkdir(parents=True, exist_ok=True)

        def capture(should_stop):  # noqa: F811 - deliberately shadowing the None
            record_module.supervise(
                starter, cfg.recordings,
                retention_hours=cfg.source.retention_hours,
                max_gb=cfg.source.max_gb, sweep_sec=60,
                should_stop=should_stop,
            )

    stop = threading.Event()

    def report(result) -> None:
        if result is None:
            print(" ! pass       failed; carrying on", file=sys.stderr)
            return
        for step in result:
            mark = " " if step.ok else "!"
            print(f" {mark} {step.stage:11s} {step.message}", file=sys.stderr)

    def capture_lost(e: BaseException) -> None:
        print(f" ! capture    stopped: {e}", file=sys.stderr)
        print("              passes continue over what is already on disk",
              file=sys.stderr)

    what = "capture and passes" if records else "passes"
    print(f"speechmap: {what} every {interval:g}s; Ctrl-C to stop", file=sys.stderr)
    try:
        runner_module.forever(
            cfg=cfg, interval=interval, capture=capture, stop=stop,
            on_pass=report, on_capture_lost=capture_lost,
        )
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        print("speechmap: stopped", file=sys.stderr)


def _report_tools() -> None:
    """Say which of the programs this drives are reachable, stage by stage.

    Being able to ask this without running anything saves a caller from
    diagnosing a failure halfway through a long job. Missing something optional
    is not a failure: it narrows what you can do, and the report says what.
    """
    seen: dict[str, tuple[str | None, str | None]] = {}
    missing = 0
    for stage, required, optional in STAGES:
        print(f"  {stage}", file=sys.stderr)
        for name in required + optional:
            if name not in seen:
                seen[name] = next(
                    (source, problem) for n, source, problem in check([name]) if n == name
                )
            source, problem = seen[name]
            note = OPTIONAL_BECAUSE.get(name, "")
            if problem is None:
                tail = f"  ({note})" if note else ""
                print(f"    {name:12s} {source}{tail}", file=sys.stderr)
            elif name in optional:
                print(f"    {name:12s} not found, {note or 'optional'}", file=sys.stderr)
            else:
                missing += 1
                print(f"    {name:12s} NOT FOUND", file=sys.stderr)
                print(f"    {'':12s} {problem}", file=sys.stderr)
    if missing:
        raise typer.Exit(1)


def speechmap() -> None:
    app()
