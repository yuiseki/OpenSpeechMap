"""Running the stages a declaration names.

The stage commands stay; this drives them. Two properties matter more than the
convenience: a pass over an unchanged directory does nothing, and a stage that
fails stops the ones after it rather than letting them work on a half-built
input.
"""
from __future__ import annotations

import json

import pytest

from openspeechmap import config, runner


def declare(tmp_path, lenses, body):
    import shutil

    shutil.copytree(lenses, tmp_path / "lenses", dirs_exist_ok=True)
    p = tmp_path / "speechmap.yaml"
    p.write_text(body, encoding="utf-8")
    return p


TRANSCRIPTS = [
    {"t": "2026-08-13T19:00:00", "seg": "a0", "text": "柏市で猛烈な雨が降り警報が出ました"},
    {"t": "2026-08-13T19:01:00", "seg": "a1", "text": "次の曲をお送りします"},
]


@pytest.fixture
def from_transcripts(tmp_path, lenses):
    src = tmp_path / "transcripts"
    src.mkdir()
    (src / "a.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in TRANSCRIPTS),
        encoding="utf-8",
    )
    return declare(tmp_path, lenses, """
source:
  kind: transcripts
  path: ./transcripts
out: ./out
lens: ./lenses/ja-radio-disaster
""")


def test_a_transcripts_declaration_runs_the_lens_and_the_series(from_transcripts, env,
                                                                monkeypatch):
    monkeypatch.setenv("PATH", env["PATH"])
    monkeypatch.setenv("DETEMPUS", env["DETEMPUS"])
    cfg = config.load(from_transcripts)
    done = runner.once(cfg)
    assert [step.stage for step in done] == ["lens", "series"]
    assert all(step.ok for step in done), [s.message for s in done]
    assert (cfg.out / "labeled.jsonl").exists()
    assert (cfg.out / "series.json").exists()


def test_a_second_pass_over_unchanged_input_does_nothing_expensive(from_transcripts, env,
                                                                   monkeypatch):
    monkeypatch.setenv("PATH", env["PATH"])
    monkeypatch.setenv("DETEMPUS", env["DETEMPUS"])
    cfg = config.load(from_transcripts)
    runner.once(cfg)
    labels = (cfg.out / "labeled" / "a.jsonl").read_text()
    done = runner.once(cfg)
    assert all(step.ok for step in done)
    assert (cfg.out / "labeled" / "a.jsonl").read_text() == labels


def test_a_failing_stage_stops_the_ones_after_it(from_transcripts, env, monkeypatch):
    """A series built from a half-written labelled set is worse than no series."""
    monkeypatch.setenv("PATH", env["PATH"])
    monkeypatch.delenv("DETEMPUS", raising=False)
    cfg = config.load(from_transcripts)

    def explode(_cfg):
        raise runner.StageError("lens: pretend the model endpoint is down")

    monkeypatch.setattr(runner, "_lens", explode)
    done = runner.once(cfg)
    assert [step.stage for step in done] == ["lens"]
    assert not done[0].ok
    assert "endpoint is down" in done[0].message


def test_the_stages_run_in_the_order_the_declaration_implies(tmp_path, lenses):
    (tmp_path / "rec").mkdir()
    cfg = config.load(declare(tmp_path, lenses, """
source:
  kind: dir
  path: ./rec
out: ./out
lens: ./lenses/ja-radio-disaster
"""))
    assert cfg.stages() == ["transcribe", "lens", "series"]


def test_capture_is_not_run_by_a_single_pass(tmp_path, lenses):
    """Recording never finishes, so it cannot be a step in a pass that ends.
    A declaration that names a stream is telling you to start it separately."""
    cfg = config.load(declare(tmp_path, lenses, """
source:
  kind: http
  url: http://example.invalid/stream
  label: X
out: ./out
lens: ./lenses/ja-radio-disaster
"""))
    assert "record" in cfg.stages()
    assert "record" not in runner.pass_stages(cfg)


def test_no_matching_records_is_not_a_failed_pass(tmp_path, lenses, env, monkeypatch):
    """Nothing selected is the normal answer for most of any broadcast day. A
    pass that reports failure every time the radio plays music trains whoever
    is watching to ignore it."""
    import shutil

    shutil.copytree(lenses, tmp_path / "lenses", dirs_exist_ok=True)
    src = tmp_path / "transcripts"
    src.mkdir()
    (src / "a.jsonl").write_text(
        json.dumps({"t": "2026-08-13T19:00:00", "seg": "a0",
                    "text": "次の曲をお送りします"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    p = tmp_path / "speechmap.yaml"
    p.write_text("""
source:
  kind: transcripts
  path: ./transcripts
out: ./out
lens: ./lenses/ja-radio-disaster
""", encoding="utf-8")
    monkeypatch.setenv("PATH", env["PATH"])
    monkeypatch.setenv("DETEMPUS", env["DETEMPUS"])
    cfg = config.load(p)
    done = runner.once(cfg)
    assert [step.stage for step in done] == ["lens", "series"]
    assert all(step.ok for step in done), [s.message for s in done]
    assert "nothing" in done[-1].message.lower()
