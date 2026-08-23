"""Continuous capture: retention, and the commands handed to ffmpeg.

No radio and no network here. What is worth testing is the part with decisions
in it: which files get deleted, and what ffmpeg is actually told to do. The
supervisor loop is exercised through a fake process rather than a real one.
"""
from __future__ import annotations

import time

import pytest

from openspeechmap import record


def seg(tmp_path, name, size=1024, age_hours=0.0):
    p = tmp_path / name
    p.write_bytes(b"x" * size)
    if age_hours:
        old = time.time() - age_hours * 3600
        import os
        os.utime(p, (old, old))
    return p


def names(tmp_path):
    return sorted(p.name for p in tmp_path.glob("*.ts"))


# --- retention ---------------------------------------------------------------

def test_the_newest_segment_is_never_deleted(tmp_path):
    """It is the one ffmpeg is still writing into."""
    seg(tmp_path, "S-20260101-000000.ts", age_hours=999)
    seg(tmp_path, "S-20260101-000500.ts", age_hours=999)
    record.sweep(tmp_path, retention_hours=1, max_gb=0)
    assert names(tmp_path) == ["S-20260101-000500.ts"]


def test_a_single_segment_is_left_alone(tmp_path):
    seg(tmp_path, "S-20260101-000000.ts", age_hours=999)
    record.sweep(tmp_path, retention_hours=1, max_gb=0)
    assert names(tmp_path) == ["S-20260101-000000.ts"]


def test_segments_older_than_the_retention_go(tmp_path):
    seg(tmp_path, "S-20260101-000000.ts", age_hours=10)
    seg(tmp_path, "S-20260101-000500.ts", age_hours=2)
    seg(tmp_path, "S-20260101-001000.ts", age_hours=0)
    record.sweep(tmp_path, retention_hours=5, max_gb=0)
    assert names(tmp_path) == ["S-20260101-000500.ts", "S-20260101-001000.ts"]


def test_a_retention_of_zero_disables_the_age_rule(tmp_path):
    seg(tmp_path, "S-20260101-000000.ts", age_hours=9999)
    seg(tmp_path, "S-20260101-000500.ts", age_hours=0)
    record.sweep(tmp_path, retention_hours=0, max_gb=0)
    assert len(names(tmp_path)) == 2


def test_the_size_cap_deletes_oldest_first(tmp_path):
    for i in range(4):
        seg(tmp_path, f"S-20260101-00{i}000.ts", size=1024 * 1024)
    record.sweep(tmp_path, retention_hours=0, max_gb=2 / 1024)  # 2 MiB
    left = names(tmp_path)
    assert len(left) == 2
    assert left == ["S-20260101-002000.ts", "S-20260101-003000.ts"]


def test_the_size_cap_also_keeps_the_newest(tmp_path):
    """Even a cap smaller than one segment must not delete what is being written."""
    for i in range(3):
        seg(tmp_path, f"S-20260101-00{i}000.ts", size=1024 * 1024)
    record.sweep(tmp_path, retention_hours=0, max_gb=0.0000001)
    assert names(tmp_path) == ["S-20260101-002000.ts"]


def test_files_that_are_not_segments_are_ignored(tmp_path):
    seg(tmp_path, "S-20260101-000000.ts", age_hours=999)
    seg(tmp_path, "S-20260101-000500.ts", age_hours=999)
    (tmp_path / "notes.txt").write_text("keep me")
    record.sweep(tmp_path, retention_hours=1, max_gb=0)
    assert (tmp_path / "notes.txt").exists()


# --- what ffmpeg is told ------------------------------------------------------

def test_the_filename_pattern_carries_the_label_and_the_time(tmp_path):
    """This is how the time gets into the pipeline at all: nothing downstream
    reads audio metadata, it reads the filename."""
    pattern = record.segment_pattern(tmp_path, "JOAK-FM")
    assert pattern.endswith("JOAK-FM-%Y%m%d-%H%M%S.ts")


def test_the_sdr_pipeline_passes_the_tuning_through():
    argv = record.sdr_command(
        label="JOAK-FM", out_dir="/tmp/x", freq="82.5M", gain="19.7",
        device="0", segment_sec=300, audio_bitrate="64k",
    )
    line = " ".join(argv)
    assert "rtl_fm -f 82.5M -M wbfm -g 19.7" in line
    assert "-d 0" in line
    # rtl_fm's wbfm output is 32k, whatever its log claims about 170000 Hz
    assert f"-ar {record.SDR_AUDIO_RATE}" in line
    assert "-segment_time 300" in line
    assert "set -o pipefail" in line, "a dead rtl_fm must fail the pipeline"


def test_the_http_command_copies_rather_than_re_encodes():
    argv = record.http_command(
        label="OKAPI", out_dir="/tmp/x", url="http://example.invalid:8000/",
        segment_sec=300,
    )
    assert "-c" in argv and "copy" in argv
    assert "-reconnect" in argv
    assert "libmp3lame" not in argv and "aac" not in argv


def test_the_http_command_survives_a_dropped_stream():
    argv = record.http_command(label="X", out_dir="/tmp/x",
                               url="http://example.invalid/", segment_sec=60)
    line = " ".join(argv)
    assert "-reconnect_streamed 1" in line
    assert "-reconnect_delay_max" in line
    assert "-rw_timeout" in line


def test_http_without_a_url_is_refused():
    with pytest.raises(record.RecordError, match="--url"):
        record.build_starter(source="http", label="X", out_dir="/tmp/x", url="")


def test_an_unknown_source_is_refused():
    with pytest.raises(record.RecordError, match="sdr"):
        record.build_starter(source="carrier-pigeon", label="X", out_dir="/tmp/x")


# --- the supervisor ----------------------------------------------------------

class FakeProc:
    """Pretends to be a Popen that dies after `alive_polls` polls."""

    def __init__(self, alive_polls: int):
        self.alive_polls = alive_polls
        self.returncode = 1
        self.pid = -1
        self.killed = False

    def poll(self):
        if self.alive_polls > 0:
            self.alive_polls -= 1
            return None
        return self.returncode


def test_a_dead_capture_is_restarted(monkeypatch, tmp_path):
    """The point of the supervisor. rtl_fm dies on a USB glitch and ffmpeg
    exits with it; nothing else notices."""
    started = []

    def starter():
        p = FakeProc(alive_polls=1)
        started.append(p)
        return p

    monkeypatch.setattr(record, "stop", lambda proc: setattr(proc, "killed", True))
    monkeypatch.setattr(record.time, "sleep", lambda s: None)
    record.supervise(starter, tmp_path, retention_hours=0, max_gb=0,
                     sweep_sec=0, max_restarts=3)
    assert len(started) == 4, "one initial start plus three restarts"
    assert all(p.killed for p in started[:-1])
