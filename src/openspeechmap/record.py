"""Continuous capture, with retention.

ffmpeg does the recording. What is here is the part ffmpeg does not do: keep it
running when it dies, and delete old segments before the disk fills.

The filenames matter more than they look. Each segment is named
`<LABEL>-YYYYMMDD-HHMMSS.ts`, and that timestamp is how the time gets into the
rest of the pipeline: nothing downstream reads audio metadata. See
docs/ADR/0004-input-is-timestamped-text.md.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import os
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

# rtl_fm's wbfm output is 32k. Its own log line says "Output at 170000 Hz",
# which is an intermediate demodulation rate, not what comes out of the pipe.
# Measured by counting bytes.
SDR_AUDIO_RATE = 32000

SOURCES = ("sdr", "http")


class RecordError(Exception):
    """A request that cannot be honoured, with a message saying what to fix."""


def log(message: str) -> None:
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def segment_pattern(out_dir: str | Path, label: str) -> str:
    """Where ffmpeg writes, with strftime placeholders it fills in itself."""
    return str(Path(out_dir) / f"{label}-%Y%m%d-%H%M%S.ts")


def sdr_command(
    *,
    label: str,
    out_dir: str | Path,
    freq: str,
    gain: str,
    device: str,
    segment_sec: int,
    audio_bitrate: str,
) -> list[str]:
    """USB FM tuner (RTL-SDR): rtl_fm demodulates, ffmpeg segments.

    Run through a shell because it is a pipe, and with pipefail because rtl_fm
    dying has to fail the whole thing. Without it ffmpeg sits on a closed pipe
    and the supervisor never learns that the tuner went away.
    """
    pattern = segment_pattern(out_dir, label)
    pipeline = (
        "set -o pipefail; "
        f"rtl_fm -f {freq} -M wbfm -g {gain} -l 0 -d {device} - | "
        f"ffmpeg -hide_banner -loglevel error -f s16le -ar {SDR_AUDIO_RATE} -ac 1 -i - "
        f"-c:a aac -b:a {audio_bitrate} "
        f"-f segment -segment_time {segment_sec} -segment_format mpegts "
        f"-reset_timestamps 1 -strftime 1 '{pattern}'"
    )
    return ["bash", "-c", pipeline]


def http_command(
    *, label: str, out_dir: str | Path, url: str, segment_sec: int
) -> list[str]:
    """Any HTTP stream: SHOUTcast, Icecast, an HLS playlist.

    Copied rather than re-encoded. Most SHOUTcast streams are MP3 and there is
    nothing to gain by decoding and encoding them again; MP3 inside mpegts
    reads fine downstream. The reconnect flags are not optional: streaming
    hosts drop long connections, and without them a night's recording is ten
    minutes long.
    """
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-reconnect", "1", "-reconnect_streamed", "1",
        "-reconnect_delay_max", "30", "-rw_timeout", "30000000",
        "-i", url,
        "-c", "copy",
        "-f", "segment", "-segment_time", str(segment_sec),
        "-segment_format", "mpegts",
        "-reset_timestamps", "1", "-strftime", "1",
        segment_pattern(out_dir, label),
    ]


def build_starter(
    *,
    source: str,
    label: str,
    out_dir: str | Path,
    freq: str = "82.5M",
    gain: str = "19.7",
    device: str = "0",
    segment_sec: int = 300,
    audio_bitrate: str = "64k",
    url: str = "",
) -> Callable[[], subprocess.Popen]:
    """Return something that starts a capture, or explain why it cannot."""
    if source not in SOURCES:
        raise RecordError(
            f"--source must be one of {', '.join(SOURCES)}, not {source!r}"
        )
    if source == "http":
        if not url:
            raise RecordError("--source http needs --url")
        argv = http_command(label=label, out_dir=out_dir, url=url,
                            segment_sec=segment_sec)
        described = f"http: {label} from {url}"
    else:
        argv = sdr_command(label=label, out_dir=out_dir, freq=freq, gain=gain,
                           device=device, segment_sec=segment_sec,
                           audio_bitrate=audio_bitrate)
        described = f"sdr: {label} at {freq}, gain {gain}, device {device}"

    def start() -> subprocess.Popen:
        log(f"starting {described}")
        # Its own process group, so the supervisor can kill rtl_fm and ffmpeg
        # together rather than leaving one of them orphaned.
        return subprocess.Popen(
            argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    return start


def segments(out_dir: str | Path) -> list[Path]:
    """Recorded segments, oldest first. The name sorts chronologically because
    of how it is built, so no stat call is needed to order them."""
    return sorted(
        (p for p in Path(out_dir).glob("*.ts") if p.is_file()), key=lambda p: p.name
    )


def total_bytes(out_dir: str | Path) -> int:
    return sum(p.stat().st_size for p in segments(out_dir))


def sweep(out_dir: str | Path, retention_hours: float, max_gb: float) -> None:
    """Delete old segments, by age and then by total size.

    The newest is never touched: ffmpeg is still writing into it. Either limit
    can be set to 0 to switch it off.
    """
    files = segments(out_dir)
    if len(files) <= 1:
        return

    if retention_hours > 0:
        cutoff = time.time() - retention_hours * 3600
        for p in files[:-1]:
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
                    log(f"retention (age): deleted {p.name}")
            except OSError:
                pass

    if max_gb > 0:
        cap = int(max_gb * (1024**3))
        files = segments(out_dir)
        total = sum(p.stat().st_size for p in files)
        for p in files[:-1]:
            if total <= cap:
                break
            try:
                size = p.stat().st_size
                p.unlink()
                total -= size
                log(f"retention (size): deleted {p.name}")
            except OSError:
                pass


def stop(proc: subprocess.Popen) -> None:
    """Stop the whole process group. The SDR source is two processes in a pipe,
    so killing only the one we hold a handle to leaves the other running."""
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


def supervise(
    starter: Callable[[], subprocess.Popen],
    out_dir: str | Path,
    *,
    retention_hours: float,
    max_gb: float,
    sweep_sec: int,
    poll_sec: float = 3.0,
    restart_delay: float = 5.0,
    max_restarts: int | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> None:
    """Keep a capture running and keep the disk from filling.

    Restarting matters because the failure is common and silent: a USB glitch
    kills rtl_fm, ffmpeg exits with it, and nothing else notices. A recording
    that stopped three weeks ago looks exactly like one that is running.

    `max_restarts` exists for the tests; left as None it never gives up.
    `should_stop` lets a caller running this in a thread bring it down, since a
    thread cannot be interrupted the way the main one can.
    """
    asked_to_stop = should_stop or (lambda: False)
    proc = starter()
    restarts = 0
    last_sweep = 0.0
    try:
        while not asked_to_stop():
            if proc.poll() is not None:
                if max_restarts is not None and restarts >= max_restarts:
                    stop(proc)
                    return
                log(f"capture exited (rc={proc.returncode}), restarting")
                stop(proc)
                time.sleep(restart_delay)
                proc = starter()
                restarts += 1
                continue
            now = time.time()
            if now - last_sweep >= sweep_sec:
                sweep(out_dir, retention_hours, max_gb)
                last_sweep = now
                gigabytes = total_bytes(out_dir) / (1024**3)
                log(f"status: {len(segments(out_dir))} segments, {gigabytes:.2f} GB")
            # Broken into short waits so a stop is noticed promptly rather
            # than after a full poll interval.
            waited = 0.0
            while waited < poll_sec and not asked_to_stop():
                time.sleep(min(0.25, poll_sec - waited))
                waited += 0.25
    except KeyboardInterrupt:
        log("stopping")
    finally:
        stop(proc)
