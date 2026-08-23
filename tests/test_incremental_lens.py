"""The lens stage over a directory of transcripts, run again.

Same rule as transcription: one output per input, and the output's existence is
the record that the input is done. The lens is the expensive stage, one model
call per record, so redoing finished work is the most wasteful thing here.

The aggregates that the viewer reads are rebuilt from the parts every time. They
are derived, not state: deleting them costs nothing but a concatenation.
"""
from __future__ import annotations

import json

from conftest import run_cli

ROWS = {
    "a": [{"t": "2026-08-13T19:00:00", "seg": "a0",
           "text": "柏市で猛烈な雨が降り警報が出ました"},
          {"t": "2026-08-13T19:01:00", "seg": "a1", "text": "次の曲をお送りします"}],
    "b": [{"t": "2026-08-13T19:05:00", "seg": "b0",
           "text": "市原市で氾濫の危険が高まっています"}],
}


def write_transcripts(d, keys):
    d.mkdir(parents=True, exist_ok=True)
    for k in keys:
        (d / f"{k}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ROWS[k]),
            encoding="utf-8",
        )


def rows_in(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(x) for x in lines if x.strip()]


def labelled(out):
    return sorted(p.name for p in (out / "labeled").glob("*.jsonl"))


def test_one_labelled_file_per_transcript_file(tmp_path, env, lenses):
    src = tmp_path / "transcripts"
    write_transcripts(src, ["a", "b"])
    out = tmp_path / "out"
    r = run_cli("lens", [str(src), "--lens", str(lenses / "ja-radio-disaster"),
                        "--out", str(out)], env)
    assert r.returncode == 0, r.stderr
    assert labelled(out) == ["a.jsonl", "b.jsonl"]


def test_a_second_run_labels_nothing(tmp_path, env, lenses):
    src = tmp_path / "transcripts"
    write_transcripts(src, ["a", "b"])
    out = tmp_path / "out"
    args = [str(src), "--lens", str(lenses / "ja-radio-disaster"), "--out", str(out)]
    run_cli("lens", args, env)
    before = {p.name: p.read_text() for p in (out / "labeled").glob("*.jsonl")}
    r = run_cli("lens", args, env)
    assert r.returncode == 0, r.stderr
    assert "nothing to label" in r.stderr
    assert {p.name: p.read_text() for p in (out / "labeled").glob("*.jsonl")} == before


def test_only_the_new_transcript_is_labelled(tmp_path, env, lenses):
    src = tmp_path / "transcripts"
    write_transcripts(src, ["a"])
    out = tmp_path / "out"
    args = [str(src), "--lens", str(lenses / "ja-radio-disaster"), "--out", str(out)]
    run_cli("lens", args, env)
    write_transcripts(src, ["b"])
    r = run_cli("lens", args, env)
    assert r.returncode == 0, r.stderr
    assert "1 file" in r.stderr
    assert labelled(out) == ["a.jsonl", "b.jsonl"]


def test_the_aggregates_cover_everything_not_only_the_new_part(tmp_path, env, lenses):
    """A run that labelled one file must still emit places for all of them."""
    src = tmp_path / "transcripts"
    write_transcripts(src, ["a"])
    out = tmp_path / "out"
    args = [str(src), "--lens", str(lenses / "ja-radio-disaster"), "--out", str(out)]
    run_cli("lens", args, env)
    write_transcripts(src, ["b"])
    run_cli("lens", args, env)
    ids = {x["seg"] for x in rows_in(out / "labeled.jsonl")}
    assert ids == {"a0", "a1", "b0"}
    selected = {x["id"] for x in rows_in(out / "selected.jsonl")}
    assert selected == {"a0", "b0"}


def test_deleting_a_labelled_file_redoes_that_one(tmp_path, env, lenses):
    src = tmp_path / "transcripts"
    write_transcripts(src, ["a", "b"])
    out = tmp_path / "out"
    args = [str(src), "--lens", str(lenses / "ja-radio-disaster"), "--out", str(out)]
    run_cli("lens", args, env)
    kept = (out / "labeled" / "b.jsonl").read_text()
    (out / "labeled" / "a.jsonl").unlink()
    r = run_cli("lens", args, env)
    assert r.returncode == 0, r.stderr
    assert "1 file" in r.stderr
    assert (out / "labeled" / "b.jsonl").read_text() == kept


def test_redo_relabels_everything(tmp_path, env, lenses):
    src = tmp_path / "transcripts"
    write_transcripts(src, ["a", "b"])
    out = tmp_path / "out"
    args = [str(src), "--lens", str(lenses / "ja-radio-disaster"), "--out", str(out)]
    run_cli("lens", args, env)
    r = run_cli("lens", [*args, "--redo"], env)
    assert r.returncode == 0, r.stderr
    assert "2 file" in r.stderr


def test_a_single_transcript_file_still_works(tmp_path, env, lenses):
    src = tmp_path / "transcripts"
    write_transcripts(src, ["a"])
    out = tmp_path / "out"
    r = run_cli("lens", [str(src / "a.jsonl"), "--lens", str(lenses / "ja-radio-disaster"),
                        "--out", str(out)], env)
    assert r.returncode == 0, r.stderr
    assert labelled(out) == ["a.jsonl"]
    assert len(rows_in(out / "labeled.jsonl")) == 2
