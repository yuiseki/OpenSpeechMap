"""Doing only the new work, by looking at what is already there.

One output file per input file. If the output exists, the input is done. There
is no state file to get out of sync with reality: the output is the state, the
way it is in Make.

Deleting an output redoes exactly that input, which is the property that makes
this predictable enough to run on a timer.
"""
from __future__ import annotations

import json

from conftest import run_cli


def copy_segments(src, dst, names):
    dst.mkdir(parents=True, exist_ok=True)
    for n in names:
        (dst / n).write_bytes((src / n).read_bytes())


def rows_in(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def outputs(d):
    return sorted(p.name for p in d.glob("*.jsonl"))


def test_one_output_file_per_input_file(tmp_path, env, npr_segments):
    audio = tmp_path / "rec"
    copy_segments(npr_segments, audio, ["a.ts", "b.ts"])
    out = tmp_path / "transcripts"
    r = run_cli("transcribe", [str(audio), "--out", str(out), "--chunk-sec", "30",
                               "--language", "en"], env)
    assert r.returncode == 0, r.stderr
    assert outputs(out) == ["a.jsonl", "b.jsonl"]


def test_a_second_run_does_nothing(tmp_path, env, npr_segments):
    audio = tmp_path / "rec"
    copy_segments(npr_segments, audio, ["a.ts", "b.ts"])
    out = tmp_path / "transcripts"
    run_cli("transcribe", [str(audio), "--out", str(out), "--chunk-sec", "30",
                           "--language", "en"], env)
    before = {p.name: p.read_text() for p in out.glob("*.jsonl")}
    r = run_cli("transcribe", [str(audio), "--out", str(out), "--chunk-sec", "30",
                               "--language", "en"], env)
    assert r.returncode == 0, r.stderr
    assert "nothing to do" in r.stderr
    assert {p.name: p.read_text() for p in out.glob("*.jsonl")} == before


def test_only_the_new_file_is_transcribed(tmp_path, env, npr_segments):
    audio = tmp_path / "rec"
    copy_segments(npr_segments, audio, ["a.ts"])
    out = tmp_path / "transcripts"
    run_cli("transcribe", [str(audio), "--out", str(out), "--chunk-sec", "30",
                           "--language", "en"], env)
    first = (out / "a.jsonl").read_text()

    copy_segments(npr_segments, audio, ["b.ts"])
    r = run_cli("transcribe", [str(audio), "--out", str(out), "--chunk-sec", "30",
                               "--language", "en"], env)
    assert r.returncode == 0, r.stderr
    assert "1 file" in r.stderr
    assert outputs(out) == ["a.jsonl", "b.jsonl"]
    assert (out / "a.jsonl").read_text() == first, "the earlier output was rewritten"


def test_deleting_an_output_redoes_exactly_that_input(tmp_path, env, npr_segments):
    audio = tmp_path / "rec"
    copy_segments(npr_segments, audio, ["a.ts", "b.ts"])
    out = tmp_path / "transcripts"
    run_cli("transcribe", [str(audio), "--out", str(out), "--chunk-sec", "30",
                           "--language", "en"], env)
    kept = (out / "b.jsonl").read_text()
    (out / "a.jsonl").unlink()
    r = run_cli("transcribe", [str(audio), "--out", str(out), "--chunk-sec", "30",
                               "--language", "en"], env)
    assert r.returncode == 0, r.stderr
    assert "1 file" in r.stderr
    assert (out / "a.jsonl").exists()
    assert (out / "b.jsonl").read_text() == kept


def test_redo_ignores_what_is_there(tmp_path, env, npr_segments):
    audio = tmp_path / "rec"
    copy_segments(npr_segments, audio, ["a.ts", "b.ts"])
    out = tmp_path / "transcripts"
    run_cli("transcribe", [str(audio), "--out", str(out), "--chunk-sec", "30",
                           "--language", "en"], env)
    r = run_cli("transcribe", [str(audio), "--out", str(out), "--chunk-sec", "30",
                               "--language", "en", "--redo"], env)
    assert r.returncode == 0, r.stderr
    assert "2 file" in r.stderr
    assert outputs(out) == ["a.jsonl", "b.jsonl"]


def test_no_half_written_output_is_left_behind(tmp_path, env, npr_segments):
    """A crash must not leave a truncated file that looks finished. Written to a
    temporary name and renamed, so the output appears complete or not at all."""
    audio = tmp_path / "rec"
    copy_segments(npr_segments, audio, ["a.ts"])
    out = tmp_path / "transcripts"
    run_cli("transcribe", [str(audio), "--out", str(out), "--chunk-sec", "30",
                           "--language", "en"], env)
    assert not list(out.glob("*.tmp"))
    assert not list(out.glob(".*"))


def test_the_newest_input_can_be_left_for_next_time(tmp_path, env, npr_segments):
    """`speechmap-record` is probably still writing into it."""
    audio = tmp_path / "rec"
    copy_segments(npr_segments, audio, ["a.ts", "b.ts"])
    out = tmp_path / "transcripts"
    r = run_cli("transcribe", [str(audio), "--out", str(out), "--chunk-sec", "30",
                               "--language", "en", "--skip-newest"], env)
    assert r.returncode == 0, r.stderr
    assert outputs(out) == ["a.jsonl"]


def test_naming_one_file_still_writes_into_the_output_directory(tmp_path, env, npr_segments):
    audio = tmp_path / "rec"
    copy_segments(npr_segments, audio, ["a.ts"])
    out = tmp_path / "transcripts"
    r = run_cli("transcribe", [str(audio / "a.ts"), "--out", str(out),
                               "--chunk-sec", "30", "--language", "en"], env)
    assert r.returncode == 0, r.stderr
    assert outputs(out) == ["a.jsonl"]
    assert len(rows_in(out / "a.jsonl")) == 1


def test_no_state_file_is_created(tmp_path, env, npr_segments):
    """The output is the state. Anything else can disagree with it."""
    audio = tmp_path / "rec"
    copy_segments(npr_segments, audio, ["a.ts"])
    out = tmp_path / "transcripts"
    run_cli("transcribe", [str(audio), "--out", str(out), "--chunk-sec", "30",
                           "--language", "en"], env)
    assert outputs(out) == ["a.jsonl"]
    assert sorted(p.name for p in out.iterdir()) == ["a.jsonl"]
    assert not list(audio.glob("*.done"))
